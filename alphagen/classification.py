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


def parse_quote(symbol, payload) -> dict:
    info = (payload or {}).get("industryInfo") or {}
    meta = (payload or {}).get("metadata") or {}
    return {
        "symbol": symbol,
        "macro": info.get("macro"),
        "sector": info.get("sector"),
        "industry": info.get("industry") or meta.get("industry"),
        "basic_industry": info.get("basicIndustry"),
    }


def collect(budget_symbols=None):
    uni = load_universe()
    have = pd.read_csv(OUT) if OUT.exists() else pd.DataFrame(columns=COLS)
    todo = list(uni["symbol"]) if first_week_of_month() or have.empty else \
        sorted(set(uni["symbol"]) - set(have.dropna(subset=["industry"])["symbol"]))
    if budget_symbols:
        todo = todo[:budget_symbols]
    if not todo:
        return 0, "up to date"
    api = NseApi()
    rows, errors, last = [], 0, ""
    for sym in todo:
        try:
            rows.append(parse_quote(sym, api.json(f"/api/quote-equity?symbol={sym}", tries=2)))
        except Exception as e:
            errors += 1
            last = str(e)
            if errors >= 25 and not rows:
                raise RuntimeError(f"quote API blocked: {last[:150]}")
    new = pd.DataFrame(rows, columns=COLS)
    out = pd.concat([have, new]).drop_duplicates("symbol", keep="last").sort_values("symbol")
    out.to_csv(ensure(OUT), index=False)
    return len(new), f"{len(new)} classified, {errors} errors"
