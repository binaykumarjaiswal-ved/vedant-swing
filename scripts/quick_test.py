"""Smoke test for Vedant Swing (morning-only, no evening scan)."""

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
    from watchlists import add_symbol, get_watchlist
    from alerts import add_alert, list_alerts
    from market_regime import market_health
    from history_db import init_db, performance_summary

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

    init_db()
    regime = market_health()
    assert "regime" in regime

    print(json.dumps({
        "ok": True,
        "regime": regime.get("regime"),
        "candles": len(chart.get("candles", [])),
        "score": tech.get("swing_score"),
        "performance": performance_summary(60).get("message"),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
