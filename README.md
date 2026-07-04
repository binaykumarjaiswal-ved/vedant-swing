# Vedant Swing

India-focused **Nifty 500 swing trading** web app — screener, charts, watchlist, alerts, paper trading, and journal.

**Live repo:** https://github.com/binaykumarjaiswal-ved/vedant-swing

## Features

| Feature | Description |
|---------|-------------|
| Evening scan | 3 strategies across Nifty 500 after market close |
| Charts | Daily candles + EMA 21/50 (Lightweight Charts) |
| Analysis | RSI, MACD, trend, support/resistance |
| Watchlist | Save symbols from scan or search |
| Alerts | Price above/below triggers (Telegram optional) |
| Paper trade | Virtual Rs.5,00,000 portfolio |
| Journal | Entry/stop/target with R:R calculator |

## Quick start (Cloud Shell)

```bash
git clone https://github.com/binaykumarjaiswal-ved/vedant-swing.git
cd vedant-swing
pip install -r requirements.txt
python -m webapp.app
```

Open http://127.0.0.1:5050

## Deploy free (Render)

1. https://dashboard.render.com → **New → Blueprint**
2. Connect `binaykumarjaiswal-ved/vedant-swing`
3. Uses `render.yaml` automatically

## GitHub automation

Workflow templates in `setup/workflows/`:
- `evening-scan.yml` — 3:45 PM IST Nifty 500 scan
- `alert-check.yml` — price alert checks
- `smoke-test.yml` — CI on push

Copy to `.github/workflows/` after `gh auth refresh -s workflow`.

## Data

- **Yahoo Finance** via `yfinance` (not Google Finance — no developer API for NSE)
- **NSE** live quotes as fallback

## Disclaimer

Not SEBI-registered investment advice. Trade at your own risk.