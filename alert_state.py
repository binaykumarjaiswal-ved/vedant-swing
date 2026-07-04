"""Avoid sending the same SELL/AVERAGE alert every 30 minutes."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
ALERT_FILE = BASE_DIR / "data" / "last_alert.json"


def should_send(symbol: str, signal: str, pnl_pct: float) -> bool:
    """Send if new signal, or SELL/AVERAGE reminder after 2 hours."""
    if signal not in ("SELL", "AVERAGE"):
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().isoformat()

    if not ALERT_FILE.exists():
        _save(symbol, signal, pnl_pct, today, now)
        return True

    try:
        last = json.loads(ALERT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        _save(symbol, signal, pnl_pct, today, now)
        return True

    if last.get("symbol") != symbol or last.get("signal") != signal or last.get("date") != today:
        _save(symbol, signal, pnl_pct, today, now)
        return True

    if signal == "SELL" and pnl_pct >= last.get("pnl_pct", 0) + 0.5:
        _save(symbol, signal, pnl_pct, today, now)
        return True

    try:
        last_time = datetime.fromisoformat(last.get("time", now))
        hours = (datetime.now() - last_time).total_seconds() / 3600
        if hours >= 2:
            _save(symbol, signal, pnl_pct, today, now)
            return True
    except ValueError:
        _save(symbol, signal, pnl_pct, today, now)
        return True

    return False


def _save(symbol: str, signal: str, pnl_pct: float, date: str, time: str) -> None:
    ALERT_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALERT_FILE.write_text(
        json.dumps({"symbol": symbol, "signal": signal, "pnl_pct": pnl_pct, "date": date, "time": time}, indent=2),
        encoding="utf-8",
    )


def clear_on_close() -> None:
    if ALERT_FILE.exists():
        ALERT_FILE.unlink()