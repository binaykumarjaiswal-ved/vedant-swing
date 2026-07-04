"""Live NSE India data + yfinance fallback."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import requests
import yfinance as yf

BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

YAHOO_MAP = {
    "TATAMOTORS": "TMPV.NS",
    "ZOMATO": "ETERNAL.NS",
    "ADANITRANS": "ADANIENSOL.NS",
}


_SESSION: requests.Session | None = None


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is not None:
        return _SESSION
    s = requests.Session()
    s.headers.update(NSE_HEADERS)
    s.get("https://www.nseindia.com", timeout=15)
    time.sleep(0.8)
    _SESSION = s
    return s


def nse_quote(symbol: str) -> dict | None:
    cache = CACHE_DIR / f"quote_{symbol}.json"
    if cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if (datetime.now() - datetime.fromisoformat(data["ts"])).total_seconds() < 300:
                return data["quote"]
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    try:
        s = _session()
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        resp = s.get(url, timeout=20)
        resp.raise_for_status()
        raw = resp.json()
        price_info = raw.get("priceInfo", {})
        quote = {
            "symbol": symbol,
            "ltp": float(price_info.get("lastPrice") or 0),
            "open": float(price_info.get("open") or 0),
            "high": float(price_info.get("intraDayHighLow", {}).get("max") or 0),
            "low": float(price_info.get("intraDayHighLow", {}).get("min") or 0),
            "prev_close": float(price_info.get("previousClose") or 0),
            "change_pct": float(price_info.get("pChange") or 0),
            "source": "nse",
        }
        cache.write_text(
            json.dumps({"ts": datetime.now().isoformat(), "quote": quote}),
            encoding="utf-8",
        )
        return quote
    except Exception:
        return _yahoo_quote(symbol)


def _yahoo_quote(symbol: str) -> dict | None:
    ticker = YAHOO_MAP.get(symbol, f"{symbol}.NS")
    if not ticker.endswith(".NS"):
        ticker = f"{ticker}.NS"
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        ltp = float(getattr(info, "last_price", 0) or 0)
        prev = float(getattr(info, "previous_close", 0) or ltp)
        if ltp <= 0:
            return None
        chg = ((ltp / prev) - 1) * 100 if prev else 0
        return {
            "symbol": symbol,
            "ltp": ltp,
            "open": ltp,
            "high": ltp,
            "low": ltp,
            "prev_close": prev,
            "change_pct": round(chg, 2),
            "source": "yahoo",
        }
    except Exception:
        return None


def get_history(symbol: str, days: int = 60):
    if symbol.startswith("^"):
        ticker = symbol
    else:
        ticker = YAHOO_MAP.get(symbol, f"{symbol}.NS")
        if not ticker.endswith(".NS"):
            ticker = f"{ticker}.NS"
    period = "6mo" if days <= 120 else "1y"
    for attempt in range(2):
        try:
            df = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
            if df is None or df.empty:
                if attempt == 0:
                    time.sleep(1)
                    continue
                return None
            if hasattr(df.columns, "levels"):
                df.columns = df.columns.get_level_values(0)
            return df.rename(columns=str.title)
        except Exception:
            if attempt == 0:
                time.sleep(1)
            else:
                return None
    return None