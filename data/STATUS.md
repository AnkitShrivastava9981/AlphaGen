# Data collection status

Last run: Wed 25 Nov 2026, 03:40 IST

| Step | Result | Rows | Note |
|---|---|---|---|
| index_pe_history | FAILED | 0 | RuntimeError: no index P/E data downloaded |
| index_archive | OK | 0 | 0 new days, 0 days left, 97 holidays/missing |
| classification | OK | 750 | NSE quote API blocked (https://www.nseindia.com/api/quote-equity?symbol=AEGISLOG -> HTTP 403 [curl_cffi); used Yahoo industry for 750 |
| shareholding | OK | 0 | 0 new filings parsed, 0 errors |
| results_history | OK | 0 | backfill complete; repair fixed 0/385 quarters; failures no_profit_BANKING:382, no_profit_NONINDAS:3 |
