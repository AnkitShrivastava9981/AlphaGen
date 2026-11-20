# Data collection status

Last run: Fri 20 Nov 2026, 05:51 IST

| Step | Result | Rows | Note |
|---|---|---|---|
| index_pe_history | OK | 26 | 26/49 indices ok; missing: NIFTY SMALLCAP 250, NIFTY MICROCAP 250, NIFTY PRIVATE BANK, NIFTY FINANCIAL SERVICES, NIFTY FINANCIAL SERVICES EX-BANK, NIFTY CAPITAL MARKETS, NIFTY MIDSMALL FINANCIAL SERVICES, NIFTY HEALTHCARE INDEX |
| index_archive | OK | 169 | 1 new days, 0 days left, 96 holidays/missing |
| classification | OK | 753 | NSE quote API blocked (https://www.nseindia.com/api/quote-equity?symbol=AEGISLOG -> HTTP 403 [curl_cffi); used Yahoo industry for 753 |
| shareholding | OK | 0 | 0 new filings parsed, 0 errors |
| results_history | OK | 1,125 | backfill complete; repair fixed 1125/1894 quarters; failures download_failed_BANKING:140, download_failed_INDAS:394, download_failed_NBFC:40, no_profit_BANKING:193, no_profit_NONINDAS:2 |
