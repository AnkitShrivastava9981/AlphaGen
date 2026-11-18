"""Quarterly results history (Jun-2019 quarter onward) from NSE XBRL filings.

Yahoo Finance only goes back to FY2023, which limited P/E history to mid-2023. This step
backfills quarterly revenue and net profit from the XBRL results every company files with NSE,
so trailing-12-month P/E can be built from mid-2020. It is slow (one XBRL per quarter per
company), so it is resumable: progress lives in _state.json and each run stops at a time budget.

Output: data/fundamentals/results_hist/SYMBOL.csv with one row per (period_end, nature).
"""
import datetime as dt
import io
import json
import re
import time
import xml.etree.ElementTree as ET

import pandas as pd

from .common import DATA, ensure, log
from .nse_api import NseApi
from .universe import load_universe

DIR = DATA / "fundamentals" / "results_hist"
STATE = DIR / "_state.json"
SAMPLES = DATA / "_samples"
FIRST_Q_END = dt.date(2019, 6, 30)

PROFIT_TAGS = ["ProfitOrLossAttributableToOwnersOfParent", "ProfitLossAttributableToOwnersOfParent",
               "ProfitLossForPeriod", "ProfitOrLossForPeriod", "ProfitLossForThePeriod",
               "NetProfitLossForThePeriod", "ProfitLossAfterTaxAndMinorityInterest",
               "ProfitLossFromOrdinaryActivitiesAfterTax", "NetProfitLossAfterTaxAndExtraordinaryItems"]
REVENUE_TAGS = ["RevenueFromOperations", "IncomeFromOperations", "TotalIncomeFromOperations",
                "InterestEarned", "TotalRevenueFromOperations", "Income"]
EPS_TAGS = ["BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations", "BasicEarningsPerShare",
            "BasicEarningsLossPerShareFromContinuingOperations", "BasicEPSBeforeExtraordinaryItems"]


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _date(s):
    try:
        return dt.date.fromisoformat(str(s).strip()[:10])
    except Exception:
        return None


def parse_results_xbrl(content: bytes) -> dict:
    """Namespace-agnostic extraction of one quarter's headline numbers from a results XBRL."""
    root = ET.fromstring(content)
    contexts = {}
    for c in root.iter():
        if _local(c.tag) != "context":
            continue
        start = end = inst = None
        has_dim = False
        for e in c.iter():
            n = _local(e.tag)
            if n == "startDate":
                start = _date(e.text)
            elif n == "endDate":
                end = _date(e.text)
            elif n == "instant":
                inst = _date(e.text)
            elif n in ("explicitMember", "typedMember"):
                has_dim = True
        contexts[c.get("id")] = (start, end or inst, has_dim)
    facts = {}
    for e in root.iter():
        n = _local(e.tag)
        if e.get("contextRef") and e.text and e.text.strip():
            facts.setdefault(n, []).append((e.get("contextRef"), e.text.strip()))

    # Older filings (2019-2022) often reference contexts ("OneD", "FourD") that the file never
    # defines; their period is carried by the DateOfStart/EndOfReportingPeriod facts instead.
    starts = {c: _date(v) for c, v in facts.get("DateOfStartOfReportingPeriod", [])}
    ends = {c: _date(v) for c, v in facts.get("DateOfEndOfReportingPeriod", [])}
    for ctx in set(starts) & set(ends):
        if ctx not in contexts and starts[ctx] and ends[ctx]:
            contexts[ctx] = (starts[ctx], ends[ctx], False)

    def first_text(*names):
        for name in names:
            for _, v in facts.get(name, []):
                return v
        return None

    q_start = _date(first_text("DateOfStartOfReportingPeriod"))
    q_end = _date(first_text("DateOfEndOfReportingPeriod"))
    nature = (first_text("NatureOfReportStandaloneConsolidated") or "").strip().lower()

    def pick(tags):
        cands = []
        for t in tags:
            for ctx, v in facts.get(t, []):
                st, en, dim = contexts.get(ctx, (None, None, True))
                if dim or not st or not en:
                    continue
                days = (en - st).days
                if days < 80 or days > 100:  # the quarter, not the year-to-date column
                    continue
                if q_end and en != q_end:
                    continue
                try:
                    cands.append((tags.index(t), en, float(v)))
                except ValueError:
                    continue
        if not cands:
            return None, None
        cands.sort(key=lambda x: x[0])
        return cands[0][2], cands[0][1]

    profit, end = pick(PROFIT_TAGS)
    revenue, _ = pick(REVENUE_TAGS)
    eps, _ = pick(EPS_TAGS)
    return {"period_start": q_start, "period_end": q_end or end,
            "nature": "consolidated" if "consol" in nature else ("standalone" if nature else ""),
            "revenue": revenue, "net_profit": profit, "eps": eps}


def _filings(api, symbol):
    """All quarterly results filings for one symbol (NSE lists ~10 years)."""
    ref = "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"
    base = f"/api/corporates-financial-results?index=equities&period=Quarterly&symbol={symbol}"
    for url in (base, base + "&from_date=01-04-2019&to_date=31-03-2025"):
        data = api.json(url, referer=ref)
        if isinstance(data, dict):
            data = data.get("data") or []
        if data:
            return data
    return []


def _period_end(f):
    for k in ("toDate", "to_date", "period"):
        v = f.get(k)
        if v:
            try:
                return pd.to_datetime(v, dayfirst=True).date()
            except Exception:
                pass
    return None


def backfill_symbol(api, symbol, last_q_end=dt.date(2024, 12, 31), save_sample=False):
    filings = _filings(api, symbol)
    wanted = {}
    for f in filings:
        pe = _period_end(f)
        url = f.get("xbrl") or f.get("xbrlFile")
        if not pe or not url or not url.lower().endswith((".xml", ".xbrl")):
            continue
        if not (FIRST_Q_END <= pe <= last_q_end):
            continue
        consol = str(f.get("consolidated", "")).lower().startswith("consol")
        key = (pe, "consolidated" if consol else "standalone")
        wanted.setdefault(key, url)  # first listed = latest filing (revisions come first)
    # prefer consolidated; fetch standalone only for quarters without a consolidated filing
    have_consol = {pe for pe, n in wanted if n == "consolidated"}
    jobs = [(k, u) for k, u in wanted.items() if k[1] == "consolidated" or k[0] not in have_consol]
    rows = []
    for (pe, nature), url in sorted(jobs):
        content = api.raw(url)
        if not content:
            continue
        if save_sample:
            ensure(SAMPLES / f"results_{symbol}_{pe}.xml").write_bytes(content)
            save_sample = False
        try:
            r = parse_results_xbrl(content)
        except ET.ParseError:
            continue
        r["period_end"] = r["period_end"] or pe
        r["nature"] = r["nature"] or nature
        r["symbol"] = symbol
        r["source"] = url
        rows.append(r)
    return pd.DataFrame(rows), len(filings)


def repair(budget_minutes=60):
    """Re-download and re-parse quarters stored without a profit figure (parser improvements)."""
    api = NseApi()
    t0 = time.time()
    fixed = tried = 0
    for path in sorted(DIR.glob("*.csv")):
        if time.time() - t0 > budget_minutes * 60:
            break
        df = pd.read_csv(path)
        bad = df["net_profit"].isna() & df["source"].notna() & (df.get("repaired", 0) != 1)
        if not bad.any():
            continue
        if "repaired" not in df:
            df["repaired"] = 0
        for i in df.index[bad]:
            tried += 1
            content = api.raw(df.at[i, "source"])
            df.at[i, "repaired"] = 1
            if not content:
                continue
            try:
                r = parse_results_xbrl(content)
            except ET.ParseError:
                continue
            for k in ("revenue", "net_profit", "eps"):
                df.at[i, k] = r[k]
            fixed += r["net_profit"] is not None
        df.to_csv(path, index=False)
    return fixed, tried


def collect(budget_minutes=60, max_symbols=None):
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    symbols = [s for s in load_universe()["symbol"] if not state.get(s, {}).get("done")]
    if max_symbols:
        symbols = symbols[:max_symbols]
    if not symbols:
        fixed, tried = repair(budget_minutes)
        return fixed, f"backfill complete; repair pass fixed {fixed}/{tried} quarters"
    api = NseApi()
    t0 = time.time()
    done = rows = fails = 0
    first_err = ""
    for i, sym in enumerate(symbols):
        if time.time() - t0 > budget_minutes * 60:
            break
        try:
            df, n_filings = backfill_symbol(api, sym, save_sample=(i < 2))
            if len(df):
                path = ensure(DIR / f"{sym}.csv")
                if path.exists():
                    df = pd.concat([pd.read_csv(path), df])
                df = df.drop_duplicates(["period_end", "nature"], keep="last").sort_values("period_end")
                df.to_csv(path, index=False)
            state[sym] = {"done": True, "quarters": int(len(df)), "filings": int(n_filings),
                          "at": dt.date.today().isoformat()}
            done += 1
            rows += len(df)
        except Exception as e:
            fails += 1
            first_err = first_err or str(e)[:160]
            st = state.setdefault(sym, {})
            st["tries"] = st.get("tries", 0) + 1
            st["done"] = st["tries"] >= 3  # give up after three runs
            if fails >= 15 and done == 0:
                break  # API blocked: stop early, keep the budget for other steps
        if i % 25 == 0:
            ensure(STATE).write_text(json.dumps(state, indent=1))
    ensure(STATE).write_text(json.dumps(state, indent=1))
    left = sum(1 for s in load_universe()["symbol"] if not state.get(s, {}).get("done"))
    if done == 0 and fails:
        raise RuntimeError(f"results API failing: {first_err}")
    return rows, f"{done} companies this run, {left} left, {fails} errors" + (f" ({first_err})" if first_err else "")
