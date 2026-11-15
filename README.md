# AlphaGen – weekly data collector

Every Friday at 8 PM IST, GitHub runs this code and saves fresh Indian market data into the `data/` folder.
The Saturday AlphaGen report reads it from here. Only free, public market data is stored – no personal
information and no recommendations.

**Check the latest run:** open `data/STATUS.md`.

**Run it manually:** Actions tab → *Weekly data collection* → *Run workflow*.

| Folder | What's inside | Source |
|---|---|---|
| `data/universe.csv` | ~750 stocks: Nifty 100 / Midcap 150 / Smallcap 250 / Microcap 250 | NSE |
| `data/prices/daily`, `weekly` | Prices: 2 years daily, 12 years weekly, plus indices, FX, crude, gold | Yahoo Finance |
| `data/fundamentals/snapshots` | Weekly valuation & quality snapshot per stock | Yahoo Finance |
| `data/fundamentals/statements` | Income statement, balance sheet, cash flow per company | Yahoo Finance |
| `data/nse/delivery` | Daily delivery % | NSE |
| `data/nse/fo` | F&O open interest, OI change, put-call ratio per stock | NSE |
| `data/nse/participant_oi` | FII / DII / Pro / Client derivatives positions | NSE |
| `data/nse/fii_dii.csv` | FII / DII cash-market buying & selling | NSE |
| `data/nse/deals` | Bulk and block deals | NSE |
| `data/mf` | Mutual fund master + weekly NAVs of sector, index funds and ETFs | AMFI, mfapi.in |
| `data/macro/fred.csv` | US & India yields, dollar, INR, Brent, India CPI | FRED |

The code lives in `alphagen/`. `.github/workflows/collect.yml` sets the schedule.
