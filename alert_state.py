"""Avoid sending the same SELL/STOP/AVERAGE alert every 30 minutes (per symbol)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
ALERT_FILE = BASE_DIR / "data" / "last_alert.json"


def _load_all() -> dict:
    if not ALERT_FILE.exists():
        return {"by_symbol": {}}
    try:
        d = json.loads(ALERT_FILE.read_text(encoding="utf-8"))
        if "by_symbol" not in d:
            if d.get("symbol"):
                return {"by_symbol": {d["symbol"]: d}}
            return {"by_symbol": {}}
        return d
    except json.JSONDecodeError:
        return {"by_symbol": {}}


def should_send(symbol: str, signal: str, pnl_pct: float) -> bool:
    """Send if new signal, or SELL/STOP/AVERAGE reminder after 2 hours."""
    if signal not in ("SELL", "STOP", "AVERAGE"):
        return False

    symbol = (symbol or "").upper()
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().isoformat()
    store = _load_all()
    by = store.setdefault("by_symbol", {})
    last = by.get(symbol) or {}

    if last.get("signal") != signal or last.get("date") != today:
        _save(symbol, signal, pnl_pct, today, now)
        return True

    if signal in ("SELL", "STOP") and pnl_pct >= last.get("pnl_pct", 0) + 0.5:
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
    store = _load_all()
    store.setdefault("by_symbol", {})[symbol.upper()] = {
        "symbol": symbol.upper(),
        "signal": signal,
        "pnl_pct": pnl_pct,
        "date": date,
        "time": time,
    }
    ALERT_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALERT_FILE.write_text(json.dumps(store, indent=2), encoding="utf-8")


def clear_on_close() -> None:
    if ALERT_FILE.exists():
        ALERT_FILE.unlink()


def clear_symbol(symbol: str) -> None:
    store = _load_all()
    store.get("by_symbol", {}).pop((symbol or "").upper(), None)
    ALERT_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALERT_FILE.write_text(json.dumps(store, indent=2), encoding="utf-8")
