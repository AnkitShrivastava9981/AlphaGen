# Data collection status

Last run: Tue 17 Nov 2026, 17:44 IST

| Step | Result | Rows | Note |
|---|---|---|---|
| index_pe_history | OK | 33,750 | 26/49 indices ok; missing: NIFTY SMALLCAP 250, NIFTY MICROCAP 250, NIFTY PRIVATE BANK, NIFTY FINANCIAL SERVICES, NIFTY FINANCIAL SERVICES EX-BANK, NIFTY CAPITAL MARKETS, NIFTY MIDSMALL FINANCIAL SERVICES, NIFTY HEALTHCARE INDEX |
| classification | FAILED | 0 | RuntimeError: quote API blocked: https://www.nseindia.com/api/quote-equity?symbol=CIPLA -> HTTP 403 [curl_cffi] |
| shareholding | OK | 131,244 | 4353 new filings parsed, 0 errors |
| results_history | OK | 12,595 | 753 companies this run, 0 left, 0 errors |
