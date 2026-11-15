"""Mutual funds: AMFI scheme master (all equity/index/ETF schemes) + weekly NAV history for
sectoral/thematic funds, index funds and ETFs (used to pick the fund for each sector idea).
"""
import time

import pandas as pd

from .common import DATA, ensure, first_week_of_month, get_with_retry, http_session

NAV_URLS = ["https://www.amfiindia.com/spages/NAVAll.txt", "https://portal.amfiindia.com/spages/NAVAll.txt"]
MF_DIR = DATA / "mf"
HIST = MF_DIR / "nav_weekly.parquet"


def _label(header: str) -> str:
    h = header.lower()
    if "scheme code" in h:
        return "code"
    if "scheme name" in h:
        return "name"
    if "net asset value" in h or h == "nav":
        return "nav"
    if h == "date" or h.endswith(" date") and "launch" not in h:
        return "nav_date"
    if "reinvest" in h:
        return "isin_reinv"
    if "isin" in h:
        return "isin_growth"
    return h.replace(" ", "_")


def parse_navall(text: str) -> pd.DataFrame:
    """Parse AMFI NAVAll.txt using its own header line, so added/moved columns don't break it."""
    category = amc = None
    header = None
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ";" in line:
            p = [x.strip() for x in line.split(";")]
            if p[0].lower() == "scheme code":
                header = [_label(x) for x in p]
                continue
            if not p[0].isdigit():
                continue
            if header and len(p) == len(header):
                rec = dict(zip(header, p))
            else:  # fallback: classic 6-column layout, NAV and date are always the last two fields
                rec = {"name": p[3], "nav": p[-2], "nav_date": p[-1]}
            rec.update({"code": int(p[0]), "category": category, "amc": amc})
            rows.append(rec)
        elif "Schemes(" in line.replace(" (", "("):
            category = line
        else:
            amc = line
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    # Detect plan (DIRECT/REGULAR) and option (GROWTH/IDCW) columns from their values
    for col in [c for c in df.columns if c not in ("code", "name", "nav", "nav_date", "category", "amc")]:
        vals = df[col].astype(str).str.upper()
        if vals.isin(["DIRECT", "REGULAR"]).mean() > 0.5:
            df = df.rename(columns={col: "plan"})
        elif vals.str.contains("GROWTH|IDCW|DIVIDEND|BONUS").mean() > 0.5:
            df = df.rename(columns={col: "option"})
    return df


def tracked(df: pd.DataFrame) -> pd.DataFrame:
    """Funds we track history for: one direct-growth plan per sectoral/thematic or index fund, plus ETFs.

    AMFI often lists the direct and regular plans under the same name. Among same-name growth plans the
    direct plan has the highest NAV (lower expenses compound over time), so we keep that one.
    """
    cat = df["category"].fillna("")
    name = df["name"].str.lower()
    payout = name.str.contains("idcw|dividend|bonus|payout|regular")
    if "option" in df.columns:  # newer AMFI layout has explicit columns
        payout |= ~df["option"].astype(str).str.upper().str.contains("GROWTH")
    if "plan" in df.columns:
        payout |= df["plan"].astype(str).str.upper().eq("REGULAR")
    sector_or_index = cat.str.contains("Sectoral|Thematic|Index Funds", case=False) & ~payout
    funds = df[sector_or_index].copy()
    funds["_key"] = (funds["name"].str.lower()
                     .str.replace(r"[-–]?\s*(direct plan|direct|growth option|growth plan|growth|plan|option)\b",
                                  "", regex=True)
                     .str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip())
    funds = funds.sort_values("nav", ascending=False).drop_duplicates(["amc", "_key"]).drop(columns="_key")
    etfs = df[cat.str.contains("ETF", case=False)]
    return pd.concat([funds, etfs]).drop_duplicates("code")


def weekly_from_mfapi(code: int, session) -> pd.DataFrame:
    r = get_with_retry(session, f"https://api.mfapi.in/mf/{code}", tries=2, timeout=30)
    data = (r.json() or {}).get("data", []) if r is not None else []
    if not data:
        return pd.DataFrame()
    h = pd.DataFrame(data)
    h["date"] = pd.to_datetime(h["date"], format="%d-%m-%Y")
    h["nav"] = pd.to_numeric(h["nav"], errors="coerce")
    w = h.set_index("date")["nav"].sort_index().resample("W-FRI").last().dropna().reset_index()
    w["code"] = code
    return w


def collect():
    s = http_session()
    text = None
    for url in NAV_URLS:
        try:
            r = get_with_retry(s, url, tries=2, timeout=60)
            if r is not None:
                text = r.text
                break
        except Exception:
            continue
    if text is None:
        raise RuntimeError("AMFI NAV file unavailable")

    allf = parse_navall(text)
    equityish = allf[allf["category"].fillna("").str.contains("Equity Scheme|Other Scheme", case=False)]
    equityish.sort_values("code").to_csv(ensure(MF_DIR / "schemes.csv"), index=False)
    track = tracked(equityish)

    if first_week_of_month() or not HIST.exists():
        frames = []
        for code in track["code"]:
            try:
                frames.append(weekly_from_mfapi(int(code), s))
            except Exception:
                pass
            time.sleep(0.2)
        hist = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date", "nav", "code"])
        mode = "full refresh"
    else:
        hist = pd.read_parquet(HIST)
        latest = track[["code", "nav", "nav_date"]].copy()
        latest["date"] = pd.to_datetime(latest["nav_date"], format="%d-%b-%Y", errors="coerce")
        # snap to the week's Friday so it lines up with the W-FRI history
        latest["date"] = latest["date"] + pd.to_timedelta((4 - latest["date"].dt.weekday) % 7, unit="D")
        hist = pd.concat([hist, latest[["date", "nav", "code"]].dropna()])
        # backfill full history for any newly tracked fund
        missing = sorted(set(track["code"].astype(int)) - set(hist["code"].astype(int).unique()))
        extra = []
        for code in missing:
            try:
                extra.append(weekly_from_mfapi(code, s))
            except Exception:
                pass
            time.sleep(0.2)
        if extra:
            hist = pd.concat([hist, *extra])
        mode = f"appended latest NAVs; backfilled {len(missing)} new funds"
    hist = hist[pd.to_datetime(hist["date"]) <= pd.Timestamp.today().normalize() + pd.Timedelta(days=6)]
    hist = hist.drop_duplicates(["code", "date"], keep="last").sort_values(["code", "date"])
    hist.to_parquet(ensure(HIST), index=False, compression="zstd")
    return len(track), f"{len(equityish)} schemes in master; {len(track)} tracked; {mode}"
