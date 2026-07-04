"""Price alerts for Vedant Swing."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from nse_data import nse_quote

BASE_DIR = Path(__file__).parent
FILE = BASE_DIR / "data" / "alerts.json"
LOG = BASE_DIR / "data" / "alert_log.json"


def _load() -> dict:
    if not FILE.exists():
        return {"alerts": []}
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"alerts": []}


def _save(data: dict) -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _log(entry: dict) -> None:
    try:
        data = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {"events": []}
    except json.JSONDecodeError:
        data = {"events": []}
    data["events"].insert(0, entry)
    data["events"] = data["events"][:100]
    LOG.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_alerts(active_only: bool = True) -> list[dict]:
    rows = _load().get("alerts", [])
    if active_only:
        return [a for a in rows if a.get("status") == "active"]
    return rows


def add_alert(symbol: str, condition: str, price: float, note: str = "") -> dict:
    symbol = symbol.upper().strip()
    condition = condition.lower().strip()
    if condition not in ("above", "below"):
        return {"ok": False, "error": "Condition must be above or below"}
    if price <= 0:
        return {"ok": False, "error": "Invalid price"}
    row = {
        "id": str(uuid.uuid4())[:8],
        "symbol": symbol,
        "condition": condition,
        "price": round(price, 2),
        "note": note,
        "status": "active",
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    data = _load()
    data.setdefault("alerts", []).append(row)
    _save(data)
    return {"ok": True, "alert": row}


def remove_alert(alert_id: str) -> dict:
    data = _load()
    before = len(data.get("alerts", []))
    data["alerts"] = [a for a in data.get("alerts", []) if a.get("id") != alert_id]
    if len(data["alerts"]) == before:
        return {"ok": False, "error": "Alert not found"}
    _save(data)
    return {"ok": True}


def _notify(message: str) -> None:
    try:
        from telegram_send import send_message
        if send_message(message):
            _log({"time": datetime.now().isoformat(timespec="seconds"), "message": message, "channel": "telegram"})
            return
    except Exception:
        pass
    _log({"time": datetime.now().isoformat(timespec="seconds"), "message": message, "channel": "log"})


def check_alerts() -> dict:
    triggered = []
    data = _load()
    for alert in data.get("alerts", []):
        if alert.get("status") != "active":
            continue
        quote = nse_quote(alert["symbol"])
        if not quote or quote.get("ltp", 0) <= 0:
            continue
        ltp = quote["ltp"]
        hit = (
            (alert["condition"] == "above" and ltp >= alert["price"])
            or (alert["condition"] == "below" and ltp <= alert["price"])
        )
        if not hit:
            continue
        alert["status"] = "triggered"
        alert["triggered_at"] = datetime.now().isoformat(timespec="seconds")
        alert["triggered_ltp"] = ltp
        msg = (
            f"Vedant Swing alert: {alert['symbol']} {alert['condition']} "
            f"Rs.{alert['price']} — LTP Rs.{ltp}"
        )
        _notify(msg)
        triggered.append(alert)
    _save(data)
    return {"ok": True, "triggered": len(triggered), "alerts": triggered}