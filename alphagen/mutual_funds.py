"""Mutual funds: AMFI scheme master (all equity/index/ETF schemes) + weekly NAV history for
sectoral/thematic funds, index funds and ETFs (used to pick the fund for each sector idea).
"""
import time

import pandas as pd

from .common import DATA, ensure, first_week_of_month, get_with_retry, http_session

NAV_URLS = ["https://www.amfiindia.com/spages/NAVAll.txt", "https://portal.amfiindia.com/spages/NAVAll.txt"]
MF_DIR = DATA / "mf"
HIST = MF_DIR / "nav_weekly.parquet"


def parse_navall(text: str) -> pd.DataFrame:
    category = amc = None
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ";" in line:
            p = [x.strip() for x in line.split(";")]
            if len(p) >= 6 and p[0].isdigit():
                rows.append({"code": int(p[0]), "isin_growth": p[1], "isin_reinv": p[2], "name": p[3],
                             "nav": pd.to_numeric(p[4], errors="coerce"), "nav_date": p[5],
                             "category": category, "amc": amc})
        elif "Schemes(" in line.replace(" (", "("):
            category = line
        else:
            amc = line
    return pd.DataFrame(rows)


def tracked(df: pd.DataFrame) -> pd.DataFrame:
    """Funds we track history for: direct-growth sectoral/thematic and index funds, plus all ETFs."""
    cat = df["category"].fillna("")
    name = df["name"].str.lower()
    direct_growth = name.str.contains("direct") & name.str.contains("growth") & ~name.str.contains("idcw")
    sector_or_index = cat.str.contains("Sectoral|Thematic|Index Funds", case=False)
    etf = cat.str.contains("ETF", case=False)
    return df[(sector_or_index & direct_growth) | etf]


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
        mode = "appended latest NAVs"
    hist = hist.drop_duplicates(["code", "date"], keep="last").sort_values(["code", "date"])
    hist.to_parquet(ensure(HIST), index=False, compression="zstd")
    return len(track), f"{len(equityish)} schemes in master; {len(track)} tracked; {mode}"
