"""Rank sectors by 20-day momentum — filter to strong sectors only."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from sector_map import SECTOR_ETF, get_sector
from technical import fetch_ohlcv

BASE_DIR = Path(__file__).parent
CACHE = BASE_DIR / "data" / "cache" / "sector_strength.json"


def _sector_20d_change(etf_symbol: str) -> float:
    df = fetch_ohlcv(etf_symbol, days=60)
    if df is None or len(df) < 21:
        return 0.0
    return float((df["Close"].iloc[-1] / df["Close"].iloc[-21] - 1) * 100)


def get_sector_rankings() -> list[dict]:
    """Return sectors sorted by 20d momentum."""
    if CACHE.exists():
        try:
            d = json.loads(CACHE.read_text(encoding="utf-8"))
            if datetime.now() - datetime.fromisoformat(d["updated"]) < timedelta(hours=6):
                return d["rankings"]
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    seen_etfs: dict[str, float] = {}
    rankings = []

    for sector, etf in SECTOR_ETF.items():
        if etf not in seen_etfs:
            seen_etfs[etf] = _sector_20d_change(etf)
        rankings.append({
            "sector": sector,
            "etf": etf,
            "change_20d": round(seen_etfs[etf], 2),
        })

    # Dedupe by sector name, keep unique sectors
    by_name: dict[str, dict] = {}
    for r in rankings:
        if r["sector"] not in by_name:
            by_name[r["sector"]] = r

    unique = sorted(by_name.values(), key=lambda x: x["change_20d"], reverse=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(
        json.dumps({"updated": datetime.now().isoformat(), "rankings": unique}, indent=2),
        encoding="utf-8",
    )
    return unique


def strong_sectors(top_n: int = 5) -> set[str]:
    ranks = get_sector_rankings()
    return {r["sector"] for r in ranks[:top_n]}


def sector_filter_pass(symbol: str, top_n: int = 5) -> tuple[bool, str]:
    sector = get_sector(symbol)
    if sector == "Other":
        return True, sector
    strong = strong_sectors(top_n)
    ok = sector in strong
    return ok, sector


def format_sector_report(top_n: int = 8) -> str:
    lines = ["── SECTOR STRENGTH (20-day) ──"]
    for i, r in enumerate(get_sector_rankings()[:top_n], 1):
        tag = "STRONG" if i <= 5 else ""
        lines.append(f"  #{i} {r['sector']}: {r['change_20d']:+.1f}% 20d {tag}")
    return "\n".join(lines)