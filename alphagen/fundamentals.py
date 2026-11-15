"""Fundamentals from Yahoo Finance.

- Weekly snapshot of valuation/quality fields for every stock (one CSV per week).
- Financial statements kept per company (one CSV each). New periods are merged in, so the
  history grows over time beyond Yahoo's ~4-year window.
"""
import time

import pandas as pd
import yfinance as yf

from .common import DATA, ensure, log, today_ist
from .universe import load_universe

INFO_FIELDS = [
    "longName", "sector", "industry", "marketCap", "enterpriseValue", "currentPrice", "trailingPE", "forwardPE",
    "priceToBook", "trailingEps", "forwardEps", "bookValue", "pegRatio", "trailingPegRatio", "enterpriseToEbitda",
    "enterpriseToRevenue", "returnOnEquity", "returnOnAssets", "profitMargins", "operatingMargins", "grossMargins",
    "revenueGrowth", "earningsGrowth", "earningsQuarterlyGrowth", "debtToEquity", "totalDebt", "totalCash",
    "totalRevenue", "ebitda", "freeCashflow", "operatingCashflow", "dividendYield", "payoutRatio", "beta",
    "heldPercentInsiders", "heldPercentInstitutions", "sharesOutstanding", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
    "targetMeanPrice", "recommendationMean", "numberOfAnalystOpinions",
]
STATEMENT_ITEMS = {
    "income": ["Total Revenue", "Operating Income", "EBITDA", "Pretax Income", "Net Income",
               "Net Income Common Stockholders", "Diluted EPS", "Basic EPS", "Interest Expense"],
    "balance": ["Total Assets", "Stockholders Equity", "Total Debt", "Net Debt",
                "Cash And Cash Equivalents", "Ordinary Shares Number"],
    "cashflow": ["Operating Cash Flow", "Capital Expenditure", "Free Cash Flow"],
}
STMT_DIR = DATA / "fundamentals" / "statements"
SNAP_DIR = DATA / "fundamentals" / "snapshots"
STMT_COLS = ["symbol", "freq", "statement", "item", "period_end", "value"]


def statement_rows(df, symbol, freq, kind):
    rows = []
    if df is None or getattr(df, "empty", True):
        return rows
    for item in STATEMENT_ITEMS[kind]:
        if item in df.index:
            for col, val in df.loc[item].items():
                if pd.notna(val):
                    rows.append((symbol, freq, kind, item, pd.Timestamp(col).date().isoformat(), float(val)))
    return rows


def merge_statements(symbol, rows) -> None:
    path = ensure(STMT_DIR / f"{symbol.replace('/', '_')}.csv")
    new = pd.DataFrame(rows, columns=STMT_COLS)
    if path.exists():
        new = pd.concat([pd.read_csv(path), new])
    key = ["freq", "statement", "item", "period_end"]
    new = new.drop_duplicates(key, keep="last").sort_values(key)
    new.to_csv(path, index=False)


def _retry(fn, tries=3):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if i == tries - 1:
                raise
            wait = 60 if "rate" in str(e).lower() or "too many" in str(e).lower() else 5
            time.sleep(wait * (i + 1))


def collect(max_tickers=None):
    uni = load_universe()
    syms = uni["symbol"].tolist()[: max_tickers or None]
    snap, ok, consecutive_fail = [], 0, 0
    for i, sym in enumerate(syms):
        t = yf.Ticker(f"{sym}.NS")
        rec = {"symbol": sym}
        got_any = False
        try:
            info = _retry(lambda: t.info) or {}
            rec.update({k: info.get(k) for k in INFO_FIELDS})
            got_any = bool(info.get("marketCap"))
        except Exception as e:
            rec["error"] = str(e)[:120]
        rows = []
        for freq, kind, getter in (
            ("A", "income", lambda: t.income_stmt),
            ("Q", "income", lambda: t.quarterly_income_stmt),
            ("A", "balance", lambda: t.balance_sheet),
            ("A", "cashflow", lambda: t.cashflow),
        ):
            try:
                rows += statement_rows(_retry(getter), sym, freq, kind)
            except Exception:
                pass
        if rows:
            merge_statements(sym, rows)
            got_any = True
        snap.append(rec)
        ok += got_any
        consecutive_fail = 0 if got_any else consecutive_fail + 1
        if consecutive_fail >= 30:
            log.error("30 stocks in a row failed - Yahoo is probably blocking; stopping early")
            break
        if i % 50 == 0:
            log.info("fundamentals %s/%s", i, len(syms))
        time.sleep(0.4)

    pd.DataFrame(snap).to_csv(ensure(SNAP_DIR / f"{today_ist().isoformat()}.csv"), index=False)
    if ok == 0:
        raise RuntimeError("no fundamentals retrieved")
    return ok, f"{ok}/{len(syms)} stocks"
