"""Nifty 500 universe for Vedant Swing."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent
CACHE = BASE_DIR / "data" / "nifty500_universe.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.nseindia.com/",
}

FALLBACK_N50 = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "ITC", "SBIN", "BHARTIARTL",
    "KOTAKBANK", "LT", "AXISBANK", "BAJFINANCE", "MARUTI", "TITAN", "SUNPHARMA",
    "WIPRO", "HCLTECH", "ULTRACEMCO", "POWERGRID", "NTPC", "ONGC", "COALINDIA",
    "TATASTEEL", "ADANIENT", "ADANIPORTS", "CIPLA", "DRREDDY", "EICHERMOT",
    "GRASIM", "HINDALCO", "HINDUNILVR", "INDUSINDBK", "JSWSTEEL", "M&M",
    "NESTLEIND", "BAJAJ-AUTO", "BAJAJFINSV", "BPCL", "BRITANNIA", "DIVISLAB",
    "HEROMOTOCO", "HDFCLIFE", "SBILIFE", "TATACONSUM", "TECHM", "APOLLOHOSP",
    "ASIANPAINT", "UPL",
]

FALLBACK_NN50 = [
    "GAIL", "VEDL", "IOC", "BANKBARODA", "PNB", "CANBK", "INDIGO", "DLF",
    "GODREJCP", "DABUR", "MARICO", "PIDILITIND", "HAVELLS", "SIEMENS", "ABB",
    "TRENT", "JINDALSTEL", "SAIL", "NMDC", "RECLTD", "LICI", "IRCTC", "NAUKRI",
    "MUTHOOTFIN", "CHOLAFIN", "BOSCHLTD", "SHREECEM", "SRF", "PIIND", "LUPIN",
    "AMBUJACEM", "BERGEPAINT", "COLPAL", "PETRONET", "ATGL", "ADANIGREEN",
    "AUROPHARMA", "BIOCON", "PERSISTENT", "OFSS", "PAGEIND", "SBICARD",
    "ICICIGI", "ICICIPRULI", "HDFCAMC", "MOTHERSON", "INDUSTOWER", "TATACOMM",
    "VBL",
]


def _fetch_index(name: str) -> list[str]:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get("https://www.nseindia.com", timeout=15)
    time.sleep(1)
    url = f"https://www.nseindia.com/api/equity-stockIndices?index={name.replace(' ', '%20')}"
    data = s.get(url, timeout=20).json()
    return [i["symbol"] for i in data.get("data", []) if i.get("symbol")]


def _pack_universe(n500: list[str], source: str) -> dict:
    n50 = [s for s in n500 if s in set(FALLBACK_N50)] or FALLBACK_N50[:]
    nn50 = [s for s in n500 if s in set(FALLBACK_NN50)] or FALLBACK_NN50[:]
    return {
        "nifty500": n500,
        "nifty50": n50,
        "niftynext50": nn50,
        "all": list(dict.fromkeys(n500)),
        "source": source,
        "count": len(n500),
    }


def get_universe() -> dict:
    if CACHE.exists():
        try:
            d = json.loads(CACHE.read_text(encoding="utf-8"))
            if datetime.now() - datetime.fromisoformat(d["updated"]) < timedelta(days=7):
                return _pack_universe(d["nifty500"], "NSE (cached)")
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    try:
        n500 = _fetch_index("NIFTY 500")
        if len(n500) < 400:
            raise ValueError("NIFTY 500 list too short")
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(
            json.dumps({"updated": datetime.now().isoformat(), "nifty500": n500}, indent=2),
            encoding="utf-8",
        )
        return _pack_universe(n500, "NSE live")
    except Exception:
        fallback = list(dict.fromkeys(FALLBACK_N50 + FALLBACK_NN50))
        return _pack_universe(fallback, "fallback list")