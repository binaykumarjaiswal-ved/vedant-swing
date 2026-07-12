# Vedant Swing

India-focused **Nifty 500 swing recommendation system** — screener, confidence-gated BUY picks, paper trading, and model audit.

**Mode: RECOMMEND ONLY** — no broker API, no auto order placement.  
**Goals:** see [GOALS.md](GOALS.md)

**Live repo:** https://github.com/binaykumarjaiswal-ved/vedant-swing

## Features

| Feature | Description |
|---------|-------------|
| Daily BUY recommender | Top picks with entry / stop / target / qty / confidence |
| Regime filter | Blocks weak-market new BUYs |
| ATR risk | Volatility-based targets/stops + risk-sized qty |
| Safer exits | Hard stop + max **1** optional average (not 5×) |
| History DB | SQLite log of scans, predictions, outcomes |
| Model audit | Score predictions vs actual 5–7d results |
| Backtest engine | Historical score-bucket validation |
| Paper trade | Virtual portfolio (optional auto paper on high conf) |
| Charts / watchlist / alerts / journal | Full research UI |

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
- `webapp-morning-boost.yml` — morning research
- `alert-check.yml` — price alert checks
- `smoke-test.yml` — CI on push

Copy to `.github/workflows/` after `gh auth refresh -s workflow`.

## Local commands

```bat
RUN_RECOMMEND.bat     :: generate today's BUY recommendations
RUN_BACKTEST.bat      :: sample historical backtest
RUN_MODEL_AUDIT.bat   :: validate past predictions
```

```bash
python recommender.py
python backtest_engine.py 25
python model_audit.py
```

## API (webapp)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/recommendations` | Latest picks |
| `GET /api/recommendations/run?limit=40` | Fresh mini-scan + picks |
| `GET /api/performance` | Win rate / score buckets |
| `GET /api/model-audit` | Close pending predictions |
| `GET /api/regime` | Market health gate |
| `GET /api/backtest?engine=1&symbols=20` | Full backtest engine |

## Data

- **Yahoo Finance** via `yfinance`
- **NSE** live quotes as fallback
- **SQLite** `data/vedant_swing.db` for prediction history

## Disclaimer

Not SEBI-registered investment advice. No broker auto-trading. Trade at your own risk.