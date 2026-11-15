"""Macro series from FRED (free, no key): US yields, dollar, INR, crude, India 10y yield and CPI."""
import io

import pandas as pd

from .common import DATA, ensure, get_with_retry, http_session

FRED_SERIES = {
    "DGS10": "us_10y_yield",
    "DTWEXBGS": "usd_broad_index",
    "DEXINUS": "inr_per_usd",
    "DCOILBRENTEU": "brent_usd",
    "FEDFUNDS": "us_fed_funds",
    "INDIRLTLT01STM": "india_10y_yield_monthly",
    "INDCPIALLMINMEI": "india_cpi_index_monthly",
}


def collect():
    s = http_session()
    frames, failed = [], []
    for sid, name in FRED_SERIES.items():
        try:
            r = get_with_retry(s, f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", tries=2)
            df = pd.read_csv(io.StringIO(r.text))
            df.columns = ["date", name]
            df["date"] = pd.to_datetime(df["date"])
            df[name] = pd.to_numeric(df[name], errors="coerce")
            frames.append(df.set_index("date"))
        except Exception:
            failed.append(sid)
    if not frames:
        # FRED blocks some cloud servers. Not critical: US 10y, dollar index, USD/INR and Brent
        # are already collected from Yahoo in the prices step.
        return 0, "FRED not reachable from GitHub - skipped (Yahoo covers yields, dollar, INR, crude)"
    wide = pd.concat(frames, axis=1).sort_index()
    wide = wide[wide.index >= "2010-01-01"]
    wide.to_csv(ensure(DATA / "macro" / "fred.csv"))
    return len(wide), ("failed: " + ",".join(failed)) if failed else "ok"
