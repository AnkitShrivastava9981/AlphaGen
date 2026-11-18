# Data collection status

Last run: Wed 18 Nov 2026, 20:04 IST

| Step | Result | Rows | Note |
|---|---|---|---|
| index_pe_history | FAILED | 0 | RuntimeError: no index P/E data downloaded |
| index_archive | OK | 190,219 | 1701 new days, 0 days left, 95 holidays/missing |
| classification | OK | 753 | NSE quote API blocked (https://www.nseindia.com/api/quote-equity?symbol=AEGISLOG -> HTTP 403 [curl_cffi); used Yahoo industry for 753 |
| shareholding | OK | 0 | 0 new filings parsed, 0 errors |
| results_history | OK | 2,115 | backfill complete; repair pass fixed 2115/2822 quarters |
