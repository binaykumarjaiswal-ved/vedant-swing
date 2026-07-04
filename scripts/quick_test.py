"""Smoke test for Vedant Swing — runs on GitHub Actions or Cloud Shell."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("STOCK_SCAN_LIMIT", "15")


def main() -> int:
    from stock_universe import get_universe
    from technical import analyze_technicals
    from evening_scan import run_evening_scan

    uni = get_universe()
    print(f"universe: {uni.get('source')} count={uni.get('count', len(uni.get('all', [])))}")

    tech = analyze_technicals("RELIANCE")
    assert tech.get("status") == "ok", tech
    print(f"reliance: score={tech.get('swing_score')} rsi={tech.get('rsi')}")

    result = run_evening_scan(limit=15)
    assert result.get("ok"), result
    print(json.dumps({
        "ok": True,
        "scanned": result.get("scanned"),
        "hits": result.get("hits"),
        "top_symbol": (result.get("top") or [{}])[0].get("symbol"),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())