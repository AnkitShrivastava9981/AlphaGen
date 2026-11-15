"""Stock universe = Nifty 100 (large) + Midcap 150 (mid) + Smallcap 250 (small) + Microcap 250 (micro).

These index lists line up closely with the AMFI large/mid/small cap definitions.
"""
import io

import pandas as pd

from .common import DATA, ensure, get_with_retry, http_session

INDEX_FILES = {
    "large": "ind_nifty100list.csv",
    "mid": "ind_niftymidcap150list.csv",
    "small": "ind_niftysmallcap250list.csv",
    "micro": "ind_niftymicrocap250_list.csv",
}
BASES = [
    "https://nsearchives.nseindia.com/content/indices/",
    "https://archives.nseindia.com/content/indices/",
    "https://www.niftyindices.com/IndexConstituent/",
]
RENAME = {"Company Name": "name", "Industry": "industry", "Symbol": "symbol", "Series": "series", "ISIN Code": "isin"}
OUT = DATA / "universe.csv"


def load_universe() -> pd.DataFrame:
    return pd.read_csv(OUT)


def clean_index_list(df: pd.DataFrame, bucket: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns=RENAME)
    for c in ("symbol", "name", "industry", "isin"):
        df[c] = df[c].astype(str).str.strip()
    df["cap_bucket"] = bucket
    return df[["symbol", "name", "industry", "isin", "cap_bucket"]]


def collect():
    s = http_session()
    frames, failed = [], []
    for bucket, fname in INDEX_FILES.items():
        df = None
        for base in BASES:
            try:
                r = get_with_retry(s, base + fname, tries=2)
                if r is not None:
                    df = pd.read_csv(io.BytesIO(r.content))
                    break
            except Exception:
                continue
        if df is None:
            failed.append(bucket)
        else:
            frames.append(clean_index_list(df, bucket))

    if not frames:
        if OUT.exists():
            return 0, "all index downloads failed; kept previous universe"
        raise RuntimeError("could not download any index list and no previous universe exists")

    uni = pd.concat(frames).drop_duplicates("symbol", keep="first")
    if failed and OUT.exists():  # keep last good copy of any bucket that failed this week
        prev = pd.read_csv(OUT)
        uni = pd.concat([uni, prev[prev.cap_bucket.isin(failed)]]).drop_duplicates("symbol", keep="first")
    uni["is_bfsi"] = uni["industry"].str.contains("Financial", case=False, na=False)
    uni["yahoo"] = uni["symbol"] + ".NS"
    order = {b: i for i, b in enumerate(INDEX_FILES)}
    uni = uni.sort_values(["cap_bucket", "symbol"], key=lambda c: c.map(order) if c.name == "cap_bucket" else c)
    uni.to_csv(ensure(OUT), index=False)
    return len(uni), ("failed buckets: " + ",".join(failed)) if failed else "ok"
