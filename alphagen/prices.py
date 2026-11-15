"""Daily (2 years) and weekly (12 years) prices from Yahoo Finance for all stocks + key indices.

Stored in small partitions (daily by month, weekly by year) so each week's commit only
changes a few files and the repo stays small.
"""
import datetime as dt
import time

import pandas as pd
import yfinance as yf

from .common import DATA, ensure, first_week_of_month, log, today_ist
from .universe import load_universe

INDEX_TICKERS = {
    "NIFTY50": "^NSEI", "NIFTY500": "^CRSLDX", "NIFTYBANK": "^NSEBANK", "NIFTYFINSERV": "NIFTY_FIN_SERVICE.NS",
    "NIFTYIT": "^CNXIT", "NIFTYPHARMA": "^CNXPHARMA", "NIFTYAUTO": "^CNXAUTO", "NIFTYMETAL": "^CNXMETAL",
    "NIFTYFMCG": "^CNXFMCG", "NIFTYENERGY": "^CNXENERGY", "NIFTYINFRA": "^CNXINFRA", "NIFTYREALTY": "^CNXREALTY",
    "NIFTYPSUBANK": "^CNXPSUBANK", "NIFTYMEDIA": "^CNXMEDIA", "NIFTYPSE": "^CNXPSE",
    "NIFTYMIDCAP150": "NIFTYMIDCAP150.NS", "NIFTYSMALLCAP250": "NIFTYSMLCAP250.NS", "INDIAVIX": "^INDIAVIX",
    "SP500": "^GSPC", "NASDAQ": "^IXIC", "HANGSENG": "^HSI", "USDINR": "INR=X", "DXY": "DX-Y.NYB",
    "US10Y": "^TNX", "BRENT": "BZ=F", "GOLD": "GC=F", "COPPER": "HG=F",
}
DAILY_DIR = DATA / "prices" / "daily"
WEEKLY_DIR = DATA / "prices" / "weekly"
COLS = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Adj Close": "adj_close", "Volume": "volume"}


def to_long(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance wide multi-ticker frame -> long rows (date, ticker, open, high, low, close, adj_close, volume)."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "ticker", *COLS.values()])
    if not isinstance(df.columns, pd.MultiIndex):
        raise ValueError("expected multi-ticker columns")
    # Work out which column level holds the tickers (the other holds Open/High/...)
    lvl = 0 if not set(df.columns.get_level_values(0)) & set(COLS) else 1
    long = df.stack(level=lvl, future_stack=True)
    long.index.names = ["date", "ticker"]
    long = long.reset_index().rename(columns=COLS)
    long = long.dropna(subset=["close"])
    long["date"] = pd.to_datetime(long["date"]).dt.tz_localize(None).dt.normalize()
    keep = ["date", "ticker"] + [c for c in COLS.values() if c in long.columns]
    return long[keep].sort_values(["ticker", "date"]).reset_index(drop=True)


def _download(tickers, batch=50, **kw) -> pd.DataFrame:
    out = []
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        for attempt in range(3):
            try:
                df = yf.download(chunk, group_by="ticker", auto_adjust=False, actions=False,
                                 threads=True, progress=False, **kw)
                out.append(to_long(df))
                break
            except Exception as e:  # rate limit or network blip
                log.warning("price batch %s failed (%s), retrying", i, e)
                time.sleep(30 * (attempt + 1))
        time.sleep(2)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def write_partitions(df: pd.DataFrame, folder, key_fmt, full_refresh: bool) -> int:
    if df.empty:
        return 0
    df = df.copy()
    df["_key"] = df["date"].dt.strftime(key_fmt)
    for key, part in df.groupby("_key"):
        path = ensure(folder / f"{key}.parquet")
        part = part.drop(columns="_key")
        if path.exists() and not full_refresh:
            part = pd.concat([pd.read_parquet(path), part])
        part = part.drop_duplicates(["date", "ticker"], keep="last").sort_values(["ticker", "date"])
        part.to_parquet(path, index=False, compression="zstd")
    return len(df)


def collect():
    uni = load_universe()
    tickers = uni["yahoo"].tolist() + list(INDEX_TICKERS.values())
    full = first_week_of_month() or not any(DAILY_DIR.glob("*.parquet"))

    daily = _download(tickers, period="2y" if full else "1mo", interval="1d")
    n_daily = write_partitions(daily, DAILY_DIR, "%Y-%m", full)

    start = (today_ist() - dt.timedelta(days=365 * 12)) if full else (today_ist() - dt.timedelta(days=90))
    weekly = _download(tickers, start=start.isoformat(), interval="1wk")
    n_weekly = write_partitions(weekly, WEEKLY_DIR, "%Y", full)

    got = daily["ticker"].nunique() if not daily.empty else 0
    if got == 0:
        raise RuntimeError("Yahoo returned no prices")
    return n_daily + n_weekly, f"{got}/{len(tickers)} tickers; {'full refresh' if full else 'incremental'}"
