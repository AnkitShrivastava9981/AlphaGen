# Data collection status

Last run: Tue 24 Nov 2026, 03:34 IST

| Step | Result | Rows | Note |
|---|---|---|---|
| index_pe_history | OK | 26 | 26/49 indices ok; missing: NIFTY SMALLCAP 250, NIFTY MICROCAP 250, NIFTY PRIVATE BANK, NIFTY FINANCIAL SERVICES, NIFTY FINANCIAL SERVICES EX-BANK, NIFTY CAPITAL MARKETS, NIFTY MIDSMALL FINANCIAL SERVICES, NIFTY HEALTHCARE INDEX |
| index_archive | OK | 169 | 1 new days, 0 days left, 96 holidays/missing |
| classification | OK | 750 | NSE quote API blocked (https://www.nseindia.com/api/quote-equity?symbol=AEGISLOG -> HTTP 403 [curl_cffi); used Yahoo industry for 750 |
| shareholding | OK | 0 | 0 new filings parsed, 0 errors |
| results_history | OK | 0 | backfill complete; repair fixed 0/385 quarters; failures no_profit_BANKING:382, no_profit_NONINDAS:3 |
