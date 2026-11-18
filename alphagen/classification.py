"""AMFI/NSE 4-level industry classification for every stock in the universe.

NSE's quote API carries the classification NSE and AMFI share: macro-economic sector (12) >
sector (22) > industry (~59, the "sub-sector" level used in the report) > basic industry (~190).
Refreshed in the first week of each month, and for any new symbol.
"""
import pandas as pd

from .common import DATA, ensure, first_week_of_month
from .nse_api import NseApi
from .universe import load_universe

OUT = DATA / "classification.csv"
COLS = ["symbol", "macro", "sector", "industry", "basic_industry"]


def _unwrap(payload):
    """GetQuoteApi wraps the quote in a list or under 'equityResponse'."""
    if isinstance(payload, list) and payload:
        payload = payload[0]
    if isinstance(payload, dict) and "equityResponse" in payload:
        er = payload["equityResponse"]
        payload = er[0] if isinstance(er, list) and er else er
    if isinstance(payload, dict) and "industryInfo" not in payload:
        for k in ("secInfo", "info", "metaData"):
            if isinstance(payload.get(k), dict) and payload[k].get("basicIndustry"):
                payload = {"industryInfo": payload[k]}
    return payload


def yahoo_fallback(symbols):
    import glob
    snaps = sorted(glob.glob(str(DATA / "fundamentals" / "snapshots" / "*.csv")))
    if not snaps:
        return []
    y = pd.read_csv(snaps[-1]).set_index("symbol")
    out = []
    for s in symbols:
        if s in y.index:
            out.append({"symbol": s, "macro": None, "sector": y.at[s, "sector"], "industry": y.at[s, "industry"],
                        "basic_industry": None, "source": "yahoo"})
    return out


def parse_quote(symbol, payload) -> dict:
    info = (payload or {}).get("industryInfo") or {}
    meta = (payload or {}).get("metadata") or {}
    return {
        "source": "nse",
        "symbol": symbol,
        "macro": info.get("macro"),
        "sector": info.get("sector"),
        "industry": info.get("industry") or meta.get("industry"),
        "basic_industry": info.get("basicIndustry"),
    }


def collect(budget_symbols=None):
    uni = load_universe()
    have = pd.read_csv(OUT) if OUT.exists() else pd.DataFrame(columns=COLS + ["source"])
    nse_done = set(have[have.get("source", pd.Series(dtype=str)) == "nse"]["symbol"]) if "source" in have else set()
    todo = list(uni["symbol"]) if first_week_of_month() else sorted(set(uni["symbol"]) - nse_done)
    if budget_symbols:
        todo = todo[:budget_symbols]
    if not todo:
        return 0, "up to date"
    api = NseApi()
    rows, errors, last = [], 0, ""
    routes = [lambda s: (f"/api/quote-equity?symbol={s}", f"https://www.nseindia.com/get-quotes/equity?symbol={s}"),
              lambda s: (f"/api/NextApi/apiClient/GetQuoteApi?functionName=getSymbolData&marketType=N&series=EQ&symbol={s}",
                         f"https://www.nseindia.com/get-quotes/equity?symbol={s}")]
    for sym in todo:
        got = None
        for route in routes:
            url, ref = route(sym)
            try:
                r = parse_quote(sym, _unwrap(api.json(url, tries=1, referer=ref)))
                if r["industry"]:
                    got = r
                    break
            except Exception as e:
                last = str(e)
        if got:
            rows.append(got)
        else:
            errors += 1
            if errors >= 25 and not rows:
                break
    note = ""
    if not rows:  # NSE blocked: fall back to Yahoo's industry so the report still has sub-sectors
        rows = yahoo_fallback(todo)
        note = f"NSE quote API blocked ({last[:80]}); used Yahoo industry for {len(rows)}"
    new = pd.DataFrame(rows, columns=COLS + ["source"])
    out = pd.concat([have, new]).drop_duplicates("symbol", keep="last").sort_values("symbol")
    out.to_csv(ensure(OUT), index=False)
    return len(new), note or f"{len(new)} classified from NSE, {errors} errors"
