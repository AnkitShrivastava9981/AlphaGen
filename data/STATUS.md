# Data collection status

Last run: Sat 21 Nov 2026, 05:29 IST

| Step | Result | Rows | Note |
|---|---|---|---|
| index_pe_history | FAILED | 0 | RuntimeError: no index P/E data downloaded |
| index_archive | OK | 0 | 0 new days, 95 days left, 0 holidays/missing |
| classification | OK | 750 | NSE quote API blocked (https://www.nseindia.com/api/quote-equity?symbol=AEGISLOG -> HTTP 403 [curl_cffi); used Yahoo industry for 750 |
| shareholding | OK | 0 | 0 new filings parsed, 0 errors |
| results_history | OK | 692 | backfill complete; repair fixed 692/1554 quarters; failures download_failed_BANKING:34, download_failed_INDAS:460, download_failed_NBFC:17, no_profit_BANKING:348, no_profit_NONINDAS:3 |
