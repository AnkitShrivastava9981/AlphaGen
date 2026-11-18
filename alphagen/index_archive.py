"""Daily close, P/E, P/B and dividend yield for every NSE index from the NSE archive file
ind_close_all_DDMMYYYY.csv (same source that worked for bhavcopies). Back-fills from Jan 2020,
one year-file at a time, then adds new days each week. Complements indices_pe (niftyindices.com),
which covered only 26 of 49 indices.

Output: data/indices/close_all/YYYY.csv (index, date, close, pe, pb, div_yield)
"""
import datetime as dt
import io
import time

import pandas as pd

from .common import DATA, ensure, get_with_retry, http_session, today_ist

DIR = DATA / "indices" / "close_all"
START = dt.date(2020, 1, 1)
URLS = ["https://nsearchives.nseindia.com/content/indices/ind_close_all_{d:%d%m%Y}.csv",
        "https://archives.nseindia.com/content/indices/ind_close_all_{d:%d%m%Y}.csv"]


def parse(raw: bytes, d: dt.date) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = [c.strip().lower() for c in df.columns]
    col = lambda *k: next((c for c in df.columns if any(x in c for x in k)), None)  # noqa: E731
    out = pd.DataFrame({
        "index": df[col("index name")].astype(str).str.strip().str.upper(),
        "date": d.isoformat(),
        "close": pd.to_numeric(df[col("closing", "close")], errors="coerce"),
        "pe": pd.to_numeric(df[col("p/e")], errors="coerce") if col("p/e") else None,
        "pb": pd.to_numeric(df[col("p/b")], errors="coerce") if col("p/b") else None,
        "div_yield": pd.to_numeric(df[col("div yield")], errors="coerce") if col("div yield") else None,
    })
    return out


def collect(budget_minutes=40):
    s = http_session()
    s.headers.update({"Referer": "https://www.nseindia.com/"})
    have = set()
    for f in DIR.glob("*.csv"):
        have |= set(pd.read_csv(f, usecols=["date"])["date"].astype(str))
    t0 = time.time()
    end = today_ist()
    days = [START + dt.timedelta(days=i) for i in range((end - START).days + 1)]
    todo = [d for d in days if d.weekday() < 5 and d.isoformat() not in have]
    # newest first so the weekly run always gets the latest days
    todo.sort(reverse=True)
    new, misses, errors = {}, 0, 0
    for d in todo:
        if time.time() - t0 > budget_minutes * 60:
            break
        got = None
        for u in URLS:
            try:
                r = get_with_retry(s, u.format(d=d), tries=1, timeout=20)
            except Exception:
                errors += 1
                r = None
            if r is not None:
                got = r
                break
        if got is None:
            misses += 1  # holiday or not published
            continue
        try:
            new.setdefault(d.year, []).append(parse(got.content, d))
        except Exception:
            errors += 1
        time.sleep(0.15)
        if errors > 40 and not new:
            raise RuntimeError("index archive downloads failing")
    rows = 0
    for y, frames in new.items():
        path = ensure(DIR / f"{y}.csv")
        df = pd.concat(frames + ([pd.read_csv(path)] if path.exists() else []))
        df = df.drop_duplicates(["index", "date"], keep="first").sort_values(["index", "date"])
        df.to_csv(path, index=False)
        rows += sum(len(f) for f in frames)
    left = len(todo) - sum(len(f) for f in new.values()) - misses
    return rows, f"{sum(len(f) for f in new.values())} new days, {max(left, 0)} days left, {misses} holidays/missing"
