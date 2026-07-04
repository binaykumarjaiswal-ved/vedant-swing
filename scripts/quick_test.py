"""Smoke test for Vedant Swing."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("STOCK_SCAN_LIMIT", "10")


def main() -> int:
    from chart_data import get_chart_payload
    from stock_universe import get_universe
    from technical import analyze_technicals
    from evening_scan import run_evening_scan
    from watchlists import add_symbol, get_watchlist
    from alerts import add_alert, list_alerts

    uni = get_universe()
    print(f"universe={uni.get('count', len(uni.get('all', [])))} source={uni.get('source')}")

    tech = analyze_technicals("RELIANCE")
    assert tech.get("status") == "ok", tech

    chart = get_chart_payload("RELIANCE", days=60)
    assert chart.get("ok") and len(chart.get("candles", [])) > 20, chart

    add_symbol("RELIANCE", note="smoke test")
    wl = get_watchlist("default")
    assert wl.get("ok"), wl

    add_alert("RELIANCE", "above", 99999, note="smoke-never-trigger")
    assert len(list_alerts(active_only=True)) >= 1

    result = run_evening_scan(limit=10)
    assert result.get("ok"), result

    print(json.dumps({
        "ok": True,
        "scanned": result.get("scanned"),
        "hits": result.get("hits"),
        "candles": len(chart.get("candles", [])),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())