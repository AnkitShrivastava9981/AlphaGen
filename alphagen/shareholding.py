"""Quarterly shareholding: category totals and every named holder above 1% (incl. each FII).

Source: the shareholding-pattern XBRL each company files with NSE every quarter, parsed with
jugaad-xbrl. Feeds two report sections: QoQ FII/DII/MF change per stock (factor 5) and
"what the top-10 FIIs bought" (holders matched to FII families in fii_families.py).

Outputs (append-only, one row per symbol x quarter [x holder]):
  data/shareholding/categories.csv   symbol, quarter_end, category_path, percentage
  data/shareholding/holders.csv      symbol, quarter_end, category_path, name, shares, percentage
Each run fetches only quarters not already stored; time-budgeted like results_history.
"""
import datetime as dt
import time

import pandas as pd

from .common import DATA, ensure, log
from .nse_api import NseApi
from .universe import load_universe

DIR = DATA / "shareholding"
CAT = DIR / "categories.csv"
HOLD = DIR / "holders.csv"
SAMPLES = DATA / "_samples"
KEEP_QUARTERS = 6  # first fill: last six quarters, then one new quarter at a time


def quarter_of(filing_date) -> str:
    """NSE lists the submission date; the holding date is the last quarter-end before it."""
    d = pd.Timestamp(filing_date)
    if d.is_quarter_end:
        return d.date().isoformat()
    return (d.to_period("Q") - 1).end_time.date().isoformat()


def walk(node, path, cats, holders):
    """Flatten jugaad-xbrl's nested shareholding dict."""
    if not isinstance(node, dict):
        return
    if "percentage" in node:
        cats.append((path, node.get("percentage")))
    for r in node.get("rows", []) or []:
        if isinstance(r, dict) and r.get("name"):
            holders.append((path, str(r.get("name")).strip(), r.get("shares"), r.get("percentage")))
    for k, v in node.items():
        if isinstance(v, dict):
            walk(v, f"{path}.{k}" if path else k, cats, holders)


def parse_shp(content: bytes):
    from jugaad_xbrl import parse_shareholding  # imported here so other steps work without it
    d = parse_shareholding(content).to_dict()
    cats, holders = [], []
    walk(d.get("shareholding", {}), "", cats, holders)
    for t in d.get("details", []) or []:  # tables the library could not place in the tree
        for r in t.get("rows", []):
            if r.get("name"):
                holders.append((f"other.{t.get('table')}", str(r["name"]).strip(), r.get("shares"),
                                r.get("percentage")))
    return cats, holders


def _filings(api, symbol):
    data = api.json(f"/api/corporate-share-holdings-master?index=equities&symbol={symbol}",
                    referer="https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern")
    if isinstance(data, dict):
        data = data.get("data") or []
    out = []
    for f in data or []:
        q = pd.to_datetime(f.get("date"), dayfirst=True, errors="coerce")
        if pd.notna(q) and f.get("xbrl"):
            out.append((q.date(), f["xbrl"]))
    # one filing per quarter (latest submission listed first)
    seen, uniq = set(), []
    for q, u in out:
        if q not in seen:
            seen.add(q)
            uniq.append((q, u))
    return sorted(uniq, reverse=True)


def collect(budget_minutes=45):
    have_c = pd.read_csv(CAT) if CAT.exists() else pd.DataFrame(columns=["symbol", "quarter_end"])
    done_keys = set(zip(have_c["symbol"], have_c["quarter_end"].astype(str).map(quarter_of)))
    api = NseApi()
    t0 = time.time()
    cats_new, hold_new = [], []
    n_ok = fails = 0
    first_err = ""
    sample_saved = False
    for sym in load_universe()["symbol"]:
        if time.time() - t0 > budget_minutes * 60:
            break
        try:
            filings = _filings(api, sym)[:KEEP_QUARTERS]
        except Exception as e:
            fails += 1
            first_err = first_err or str(e)[:160]
            if fails >= 15 and n_ok == 0:
                break
            continue
        for q, url in filings:
            if (sym, quarter_of(q)) in done_keys:
                continue
            content = api.raw(url)
            if not content:
                continue
            if not sample_saved:
                ensure(SAMPLES / f"shp_{sym}_{q}.xml").write_bytes(content)
                sample_saved = True
            try:
                cats, holders = parse_shp(content)
            except Exception as e:
                log.warning("SHP parse failed %s %s: %s", sym, q, e)
                continue
            qe = quarter_of(q)
            done_keys.add((sym, qe))
            cats_new += [(sym, qe, p, v) for p, v in cats]
            hold_new += [(sym, qe, p, n, s_, v) for p, n, s_, v in holders]
            n_ok += 1
    if cats_new:
        c = pd.DataFrame(cats_new, columns=["symbol", "quarter_end", "category_path", "percentage"])
        h = pd.DataFrame(hold_new, columns=["symbol", "quarter_end", "category_path", "name", "shares", "percentage"])
        have_c["quarter_end"] = have_c["quarter_end"].astype(str).map(quarter_of)
        pd.concat([have_c, c]).to_csv(ensure(CAT), index=False)
        h0 = pd.read_csv(HOLD) if HOLD.exists() else None
        if h0 is not None:
            h0["quarter_end"] = h0["quarter_end"].astype(str).map(quarter_of)
        (pd.concat([h0, h]) if h0 is not None else h).to_csv(ensure(HOLD), index=False)
    if n_ok == 0 and fails:
        raise RuntimeError(f"shareholding API failing: {first_err}")
    return len(cats_new), f"{n_ok} new filings parsed, {fails} errors"


def sast(days=10):
    """SEBI takeover-code disclosures (crossing 5%, or 2% changes) — catches big FII moves early."""
    api = NseApi()
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    for path in (f"/api/corporate-sast-reg29?index=equities&from_date={start:%d-%m-%Y}&to_date={end:%d-%m-%Y}",
                 f"/api/corporates-sast?index=equities&from_date={start:%d-%m-%Y}&to_date={end:%d-%m-%Y}"):
        try:
            data = api.json(path, tries=2)
        except Exception:
            continue
        if isinstance(data, dict):
            data = data.get("data") or []
        if data:
            df = pd.DataFrame(data)
            df.to_csv(ensure(DATA / "nse" / "sast" / f"{end.isoformat()}.csv"), index=False)
            return len(df), path.split("?")[0]
    raise RuntimeError("SAST endpoints returned nothing")
