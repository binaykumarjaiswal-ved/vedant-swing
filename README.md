# Vedant Swing

India-focused Nifty 500 swing trading workstation: screener, paper trading, and trade journal.

Evolved from [stock-analyst-cloud](https://github.com/binaykumarjaiswal-ved/stock-analyst-cloud).

## Features (MVP)

- Nifty 500 universe
- 3 swing strategies (pullback, breakout, oversold bounce)
- Evening scan after market close (GitHub Actions)
- Paper trading portfolio
- Trade journal with risk/reward
- Mobile-friendly web dashboard

## Cloud-only workflow

1. Code lives on GitHub
2. GitHub Actions runs evening scan at 3:45 PM IST
3. Render hosts the free web app
4. Optional: develop in Google Cloud Shell via `gcp/bootstrap.sh`

## Local / Cloud Shell quick start

```bash
pip install -r requirements.txt
python evening_scan.py
python -m webapp.app
```

## Security

Never commit `secrets.env` or API keys. Use GitHub Secrets and Render environment variables only.

## Disclaimer

Not SEBI-registered investment advice. Trade at your own risk.