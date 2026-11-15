# Data collection status

Last run: Sun 15 Nov 2026, 14:47 IST

| Step | Result | Rows | Note |
|---|---|---|---|
| universe | OK | 753 | ok |
| prices | OK | 27,143 | 777/780 tickers; incremental |
| nse_delivery | OK | 0 | 0 new day files |
| nse_fo | OK | 0 | 0 new day files |
| nse_participant_oi | OK | 0 | 0 new day files |
| nse_fii_dii | OK | 2 | running history |
| nse_deals | OK | 162 | bulk-deals API failed; used today's file; block-deals API failed; used today's file |
| mutual_funds | OK | 223 | 4162 schemes in master; 223 tracked; appended latest NAVs |
| macro | FAILED | 0 | RuntimeError: all FRED series failed |
| fundamentals | OK | 750 | 750/753 stocks |
