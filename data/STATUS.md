# Data collection status

Last run: Fri 20 Nov 2026, 22:48 IST

| Step | Result | Rows | Note |
|---|---|---|---|
| universe | OK | 750 | ok |
| prices | OK | 27,144 | 776/777 tickers; incremental |
| nse_delivery | OK | 3,715 | 5 new day files |
| nse_fo | OK | 1,120 | 5 new day files |
| nse_participant_oi | OK | 25 | 5 new day files |
| nse_fii_dii | OK | 4 | running history |
| nse_deals | OK | 140 | bulk-deals: 7-day API ok; block-deals: 7-day API ok |
| mutual_funds | OK | 743 | 4146 schemes in master; 743 tracked; appended latest NAVs; backfilled 0 new funds |
| macro | OK | 0 | FRED not reachable from GitHub - skipped (Yahoo covers yields, dollar, INR, crude) |
| fundamentals | OK | 749 | 749/750 stocks |
| index_pe_history | OK | 26 | 26/49 indices ok; missing: NIFTY SMALLCAP 250, NIFTY MICROCAP 250, NIFTY PRIVATE BANK, NIFTY FINANCIAL SERVICES, NIFTY FINANCIAL SERVICES EX-BANK, NIFTY CAPITAL MARKETS, NIFTY MIDSMALL FINANCIAL SERVICES, NIFTY HEALTHCARE INDEX |
| index_archive | OK | 146 | 1 new days, 53 days left, 42 holidays/missing |
| classification | OK | 750 | NSE quote API blocked (https://www.nseindia.com/api/quote-equity?symbol=AEGISLOG -> HTTP 403 [curl_cffi); used Yahoo industry for 750 |
| shareholding | OK | 0 | 0 new filings parsed, 0 errors |
| sast | OK | 161 | /api/corporate-sast-reg29 |
| results_history | OK | 322 | backfill complete; repair fixed 322/843 quarters; failures download_failed_BANKING:55, download_failed_INDAS:177, download_failed_NBFC:9, download_failed_NONINDAS:1, no_profit_BANKING:278, no_profit_NONINDAS:1 |
