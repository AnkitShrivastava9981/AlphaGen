# Data collection status

Last run: Sun 15 Nov 2026, 14:15 IST

| Step | Result | Rows | Note |
|---|---|---|---|
| universe | OK | 753 | ok |
| prices | OK | 731,814 | 776/780 tickers; full refresh |
| nse_delivery | OK | 3,715 | 5 new day files |
| nse_fo | OK | 896 | 4 new day files |
| nse_participant_oi | OK | 20 | 4 new day files |
| nse_fii_dii | OK | 2 | running history |
| nse_deals | OK | 162 | bulk-deals API failed; used today's file; block-deals API failed; used today's file |
| mutual_funds | OK | 223 | 4162 schemes in master; 223 tracked; full refresh |
| macro | FAILED | 0 | RuntimeError: all FRED series failed |
| fundamentals | OK | 20 | 20/20 stocks |
