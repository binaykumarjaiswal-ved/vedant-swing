"""Evening Nifty 500 swing scan — runs after market close."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pa_config import STOCK_SCAN_LIMIT
from stock_universe import get_universe
from swing_strategies import classify_symbol
from technical import fetch_ohlcv

BASE_DIR = Path(__file__).parent
OUT_DIR = BASE_DIR / "data" / "reports"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def run_evening_scan(limit: int | None = None) -> dict:
    universe = get_universe()
    symbols = universe["all"]
    scan_limit = limit or STOCK_SCAN_LIMIT
    if scan_limit > 0:
        symbols = symbols[:scan_limit]

    nifty100 = set(universe.get("nifty50", []) + universe.get("niftynext50", []))
    nifty_df = fetch_ohlcv("NIFTYBEES", days=60)
    if nifty_df is None:
        nifty_df = fetch_ohlcv("^NSEI", days=60)

    all_hits: list[dict] = []
    for i, sym in enumerate(symbols):
        print(f"[Evening] {i + 1}/{len(symbols)} {sym}", flush=True)
        for row in classify_symbol(sym, nifty100, nifty_df):
            row["index_group"] = (
                "Nifty 50" if sym in set(universe.get("nifty50", []))
                else "Nifty Next 50" if sym in set(universe.get("niftynext50", []))
                else "Nifty 500"
            )
            all_hits.append(row)

    all_hits.sort(key=lambda x: x.get("swing_score", 0), reverse=True)
    by_strategy: dict[str, list] = {}
    for row in all_hits:
        by_strategy.setdefault(row["strategy"], []).append(row)

    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "universe": universe.get("source", "Nifty 500"),
        "scanned": len(symbols),
        "hits": len(all_hits),
        "top": all_hits[:30],
        "by_strategy": {k: v[:15] for k, v in by_strategy.items()},
    }

    day = datetime.now().strftime("%Y-%m-%d")
    path = OUT_DIR / f"evening_scan_{day}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"ok": True, "file": str(path), **payload}


if __name__ == "__main__":
    result = run_evening_scan()
    print(json.dumps({"ok": result.get("ok"), "hits": result.get("hits"), "file": result.get("file")}))