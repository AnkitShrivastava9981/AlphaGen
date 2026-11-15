"""NSE market data: delivery %, F&O open interest, participant-wise OI, FII/DII cash flows, bulk/block deals.

NSE sometimes blocks cloud servers. Every function fails on its own without stopping the
others, and the weekly STATUS.md shows what worked.
"""
import datetime as dt
import io
import zipfile

import pandas as pd

from .common import DATA, ensure, get_with_retry, http_session, recent_weekdays, today_ist
from .universe import load_universe

ARCH = "https://nsearchives.nseindia.com"
NSE_DIR = DATA / "nse"


def nse_session():
    s = http_session()
    s.headers.update({"Referer": "https://www.nseindia.com/"})
    try:  # picks up the cookies NSE's API expects
        s.get("https://www.nseindia.com", timeout=20)
    except Exception:
        pass
    return s


def _fetch_days(url_fn, out_dir, parse_fn):
    """Download one file per recent trading day that we don't already have."""
    s = nse_session()
    rows = files = errors = 0
    last_err = ""
    for d in recent_weekdays(8):
        out = out_dir / f"{d.isoformat()}.csv"
        if out.exists():
            continue
        try:
            r = get_with_retry(s, url_fn(d), tries=2)
        except Exception as e:
            errors += 1
            last_err = str(e)
            continue
        if r is None:  # holiday / not published
            continue
        df = parse_fn(r.content, d)
        df.to_csv(ensure(out), index=False)
        rows += len(df)
        files += 1
    if files == 0 and errors:
        raise RuntimeError(f"all downloads failed, e.g. {last_err[:150]}")
    return rows, f"{files} new day files"


# ---------- delivery % (security-wise full bhavcopy) ----------
DELIV_KEEP = ["SYMBOL", "DATE1", "CLOSE_PRICE", "AVG_PRICE", "TTL_TRD_QNTY", "TURNOVER_LACS",
              "NO_OF_TRADES", "DELIV_QTY", "DELIV_PER"]


def clean_delivery(raw: bytes, symbols) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = [c.strip() for c in df.columns]
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]):
            df[c] = df[c].astype(str).str.strip()
    df = df[(df["SERIES"] == "EQ") & df["SYMBOL"].isin(symbols)][DELIV_KEEP].copy()
    for c in DELIV_KEEP[2:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values("SYMBOL")


def delivery():
    symbols = set(load_universe()["symbol"])
    return _fetch_days(
        lambda d: f"{ARCH}/products/content/sec_bhavdata_full_{d:%d%m%Y}.csv",
        NSE_DIR / "delivery",
        lambda raw, d: clean_delivery(raw, symbols),
    )


# ---------- F&O bhavcopy (UDiFF format) -> per-symbol OI summary ----------
def summarise_fo(raw_zip: bytes, d: dt.date) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as z:
        df = pd.read_csv(z.open(z.namelist()[0]))
    df.columns = [c.strip() for c in df.columns]
    for c in ("OpnIntrst", "ChngInOpnIntrst", "TtlTradgVol", "ClsPric", "UndrlygPric"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    fut = df[df["FinInstrmTp"].isin(["STF", "IDF"])]
    opt = df[df["FinInstrmTp"].isin(["STO", "IDO"])]
    g = fut.groupby("TckrSymb").agg(fut_oi=("OpnIntrst", "sum"), fut_oi_chg=("ChngInOpnIntrst", "sum"),
                                    fut_volume=("TtlTradgVol", "sum"))
    near = (fut.sort_values("XpryDt").groupby("TckrSymb").first()[["ClsPric", "UndrlygPric", "XpryDt"]]
            .rename(columns={"ClsPric": "fut_close", "UndrlygPric": "spot", "XpryDt": "near_expiry"}))
    call_oi = opt[opt["OptnTp"] == "CE"].groupby("TckrSymb")["OpnIntrst"].sum().rename("call_oi")
    put_oi = opt[opt["OptnTp"] == "PE"].groupby("TckrSymb")["OpnIntrst"].sum().rename("put_oi")
    out = pd.concat([g, near, call_oi, put_oi], axis=1)  # outer join: keep option-only symbols too
    out.index.name = "TckrSymb"
    out["pcr_oi"] = (out["put_oi"] / out["call_oi"]).round(3)
    out.insert(0, "date", d.isoformat())
    return out.reset_index().rename(columns={"TckrSymb": "symbol"}).sort_values("symbol")


def fo():
    return _fetch_days(
        lambda d: f"{ARCH}/content/fo/BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip",
        NSE_DIR / "fo",
        summarise_fo,
    )


# ---------- participant-wise open interest (FII / DII / Pro / Client) ----------
def parse_participant(raw: bytes, d: dt.date) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw), skiprows=1)
    df.columns = [c.strip() for c in df.columns]
    df.insert(0, "date", d.isoformat())
    return df


def participant_oi():
    return _fetch_days(
        lambda d: f"{ARCH}/content/nsccl/fao_participant_oi_{d:%d%m%Y}.csv",
        NSE_DIR / "participant_oi",
        parse_participant,
    )


# ---------- FII / DII cash market flows (appended to one running file) ----------
def fii_dii():
    s = nse_session()
    r = get_with_retry(s, "https://www.nseindia.com/api/fiidiiTradeReact", tries=3)
    if r is None:
        raise RuntimeError("FII/DII endpoint not found")
    new = pd.DataFrame(r.json())
    path = ensure(NSE_DIR / "fii_dii.csv")
    if path.exists():
        new = pd.concat([pd.read_csv(path), new])
    new = new.drop_duplicates(["date", "category"], keep="last")
    new.to_csv(path, index=False)
    return len(new), "running history"


# ---------- bulk and block deals for the past week ----------
def deals():
    s = nse_session()
    end = today_ist()
    start = end - dt.timedelta(days=7)
    rows, notes = 0, []
    for kind in ("bulk-deals", "block-deals"):
        url = (f"https://www.nseindia.com/api/historical/{kind}"
               f"?from={start:%d-%m-%Y}&to={end:%d-%m-%Y}")
        try:
            r = get_with_retry(s, url, tries=2)
            data = r.json().get("data", []) if r is not None else []
            df = pd.DataFrame(data)
        except Exception as e:
            notes.append(f"{kind} API failed")
            fallback = f"{ARCH}/content/equities/{'bulk' if kind == 'bulk-deals' else 'block'}.csv"
            try:
                r = get_with_retry(s, fallback, tries=2)
                df = pd.read_csv(io.BytesIO(r.content)) if r is not None else pd.DataFrame()
                notes.append("used today's file")
            except Exception:
                raise RuntimeError(f"{kind}: {e}")
        df.to_csv(ensure(NSE_DIR / "deals" / f"{end.isoformat()}_{kind}.csv"), index=False)
        rows += len(df)
    return rows, "; ".join(notes) or "ok"
