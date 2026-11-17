"""Official daily P/E, P/B and dividend yield of NSE sectoral and thematic indices since 2020.

Source: NSE Indices (niftyindices.com), the same numbers printed in its monthly Index Dashboard.
Stored as data/indices/pepb.csv (index, date, pe, pb, div_yield); each run only fetches what
is new. These give the 6-year sector valuation history the stock data cannot.
"""
import datetime as dt
import json

import pandas as pd

from .common import DATA, UA, ensure, log, today_ist

OUT = DATA / "indices" / "pepb.csv"
START = dt.date(2020, 1, 1)
INDICES = [
    # broad
    "NIFTY 50", "NIFTY 500", "NIFTY MIDCAP 150", "NIFTY SMALLCAP 250", "NIFTY MICROCAP 250",
    # financials
    "NIFTY BANK", "NIFTY PRIVATE BANK", "NIFTY PSU BANK", "NIFTY FINANCIAL SERVICES",
    "NIFTY FINANCIAL SERVICES EX-BANK", "NIFTY CAPITAL MARKETS", "NIFTY HOUSING",
    "NIFTY MIDSMALL FINANCIAL SERVICES",
    # sectors
    "NIFTY IT", "NIFTY AUTO", "NIFTY PHARMA", "NIFTY HEALTHCARE INDEX", "NIFTY FMCG", "NIFTY METAL",
    "NIFTY REALTY", "NIFTY ENERGY", "NIFTY OIL & GAS", "NIFTY MEDIA", "NIFTY CONSUMER DURABLES",
    "NIFTY CHEMICALS", "NIFTY MIDSMALL HEALTHCARE", "NIFTY MIDSMALL IT & TELECOM",
    # themes that map to industries
    "NIFTY INDIA DEFENCE", "NIFTY INFRASTRUCTURE", "NIFTY COMMODITIES", "NIFTY INDIA CONSUMPTION",
    "NIFTY NON-CYCLICAL CONSUMER", "NIFTY CPSE", "NIFTY PSE", "NIFTY INDIA MANUFACTURING",
    "NIFTY INDIA DIGITAL", "NIFTY INDIA TOURISM", "NIFTY MNC", "NIFTY SERVICES SECTOR",
    "NIFTY TRANSPORTATION & LOGISTICS", "NIFTY EV & NEW AGE AUTOMOTIVE", "NIFTY MOBILITY",
    "NIFTY RURAL", "NIFTY INDIA RAILWAYS PSU", "NIFTY CORE HOUSING", "NIFTY INDIA INTERNET",
    "NIFTY CEMENT", "NIFTY POWER", "NIFTY CAPITAL GOODS",
]
HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/json; charset=UTF-8",
    "Origin": "https://www.niftyindices.com",
    "Referer": "https://www.niftyindices.com/reports/historical-data",
    "User-Agent": UA,
    "X-Requested-With": "XMLHttpRequest",
}
ENDPOINTS = ["https://www.niftyindices.com/BackPage/getpepbHistoricaldataDBtoString",
             "https://www.niftyindices.com/Backpage.aspx/getpepbHistoricaldataDBtoString"]


def _session():
    try:
        from curl_cffi import requests as creq  # type: ignore
        s = creq.Session(impersonate="chrome")
    except Exception:
        import requests
        s = requests.Session()
    try:
        s.get("https://www.niftyindices.com/reports/historical-data", headers=HEADERS, timeout=20)
    except Exception:
        pass
    return s


def parse_payload(payload) -> pd.DataFrame:
    if isinstance(payload, dict) and "d" in payload:
        payload = json.loads(payload["d"])
    df = pd.DataFrame.from_records(payload or [])
    if df.empty:
        return df
    cols = {c.lower(): c for c in df.columns}
    date_col = next((cols[k] for k in ("historicaldate", "date", "indexdate") if k in cols), None)
    pick = lambda *names: next((cols[n] for n in names if n in cols), None)  # noqa: E731
    out = pd.DataFrame({
        "date": pd.to_datetime(df[date_col], errors="coerce", dayfirst=True).dt.date if date_col else None,
        "pe": pd.to_numeric(df[pick("pe", "p/e")], errors="coerce") if pick("pe", "p/e") else None,
        "pb": pd.to_numeric(df[pick("pb", "p/b")], errors="coerce") if pick("pb", "p/b") else None,
        "div_yield": pd.to_numeric(df[pick("divyield", "div yield", "dy")], errors="coerce")
        if pick("divyield", "div yield", "dy") else None,
    })
    return out.dropna(subset=["date"])


def fetch(s, name, start, end) -> pd.DataFrame:
    frames, cur = [], start
    while cur <= end:  # one calendar year per request keeps responses small
        stop = min(dt.date(cur.year, 12, 31), end)
        info = (f"{{'name':'{name}','startDate':'{cur:%d-%b-%Y}','endDate':'{stop:%d-%b-%Y}',"
                f"'indexName':'{name}'}}")
        got = None
        for url in ENDPOINTS:
            try:
                r = s.post(url, headers=HEADERS, json={"cinfo": info}, timeout=30)
                text = r.text.strip()
                if r.status_code == 200 and text and not text.startswith("<"):
                    got = parse_payload(r.json())
                    break
            except Exception:
                continue
        if got is not None and not got.empty:
            frames.append(got)
        cur = stop + dt.timedelta(days=1)
    return pd.concat(frames) if frames else pd.DataFrame()


def collect():
    have = pd.read_csv(OUT, parse_dates=["date"]) if OUT.exists() else pd.DataFrame(columns=["index", "date"])
    s = _session()
    end = today_ist()
    new, ok, failed = [], 0, []
    for name in INDICES:
        sub = have[have["index"] == name]
        start = (sub["date"].max().date() + dt.timedelta(days=1)) if len(sub) else START
        if start > end:
            ok += 1
            continue
        try:
            df = fetch(s, name, start, end)
        except Exception as e:
            log.warning("index %s failed: %s", name, e)
            df = pd.DataFrame()
        if df.empty:
            if not len(sub):
                failed.append(name)
            continue
        df.insert(0, "index", name)
        new.append(df)
        ok += 1
    if new:
        out = pd.concat([have] + new)
        out["date"] = pd.to_datetime(out["date"]).dt.date
        out = out.drop_duplicates(["index", "date"], keep="last").sort_values(["index", "date"])
        out.to_csv(ensure(OUT), index=False)
    if ok == 0:
        raise RuntimeError("no index P/E data downloaded")
    rows = sum(len(x) for x in new)
    return rows, f"{ok}/{len(INDICES)} indices ok" + (f"; missing: {', '.join(failed[:8])}" if failed else "")
