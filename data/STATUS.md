# Data collection status

Last run: Fri 27 Nov 2026, 21:42 IST

| Step | Result | Rows | Note |
|---|---|---|---|
| universe | OK | 751 | ok |
| prices | OK | 27,140 | 777/778 tickers; incremental |
| nse_delivery | OK | 3,715 | 5 new day files |
| nse_fo | OK | 896 | 4 new day files |
| nse_participant_oi | OK | 20 | 4 new day files |
| nse_fii_dii | OK | 6 | running history |
| nse_deals | OK | 140 | bulk-deals: 7-day API ok; block-deals: 7-day API ok |
| mutual_funds | OK | 743 | 4146 schemes in master; 743 tracked; appended latest NAVs; backfilled 0 new funds |
| macro | OK | 0 | FRED not reachable from GitHub - skipped (Yahoo covers yields, dollar, INR, crude) |
| fundamentals | OK | 749 | 749/751 stocks |
| index_pe_history | OK | 26 | 26/49 indices ok; missing: NIFTY SMALLCAP 250, NIFTY MICROCAP 250, NIFTY PRIVATE BANK, NIFTY FINANCIAL SERVICES, NIFTY FINANCIAL SERVICES EX-BANK, NIFTY CAPITAL MARKETS, NIFTY MIDSMALL FINANCIAL SERVICES, NIFTY HEALTHCARE INDEX |
| index_archive | OK | 146 | 1 new days, 0 days left, 96 holidays/missing |
| classification | OK | 751 | NSE quote API blocked (https://www.nseindia.com/api/quote-equity?symbol=AEGISLOG -> HTTP 403 [curl_cffi); used Yahoo industry for 751 |
| shareholding | OK | 31 | 1 new filings parsed, 0 errors |
| sast | OK | 174 | /api/corporate-sast-reg29 |
| results_history | OK | 0 | 1 companies this run, 0 left, 0 errors |
