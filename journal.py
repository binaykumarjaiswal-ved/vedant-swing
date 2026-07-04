"""Trade journal with risk/reward for Vedant Swing."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
JOURNAL_FILE = BASE_DIR / "data" / "journal.json"


def _load() -> dict:
    try:
        from cloud_sync import sync_before_read
        sync_before_read()
    except Exception:
        pass
    if not JOURNAL_FILE.exists():
        return {"entries": []}
    try:
        return json.loads(JOURNAL_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"entries": []}


def _save(data: dict) -> None:
    JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    JOURNAL_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        from cloud_sync import push_user_data
        push_user_data("journal.json")
    except Exception:
        pass


def calc_rr(entry: float, stop: float, target: float) -> float:
    risk = entry - stop
    reward = target - entry
    if risk <= 0:
        return 0
    return round(reward / risk, 2)


def add_entry(
    symbol: str,
    entry: float,
    stop: float,
    target: float,
    strategy: str = "",
    notes: str = "",
    qty: int = 0,
) -> dict:
    rr = calc_rr(entry, stop, target)
    row = {
        "id": str(uuid.uuid4())[:8],
        "date": datetime.now().strftime("%Y-%m-%d"),
        "symbol": symbol.upper(),
        "entry": entry,
        "stop": stop,
        "target": target,
        "rr": rr,
        "strategy": strategy,
        "notes": notes,
        "qty": qty,
        "status": "open",
    }
    data = _load()
    data["entries"].insert(0, row)
    _save(data)
    return {"ok": True, "entry": row}


def list_entries(limit: int = 50) -> list[dict]:
    return _load().get("entries", [])[:limit]


def close_entry(entry_id: str, exit_price: float) -> dict:
    data = _load()
    for row in data["entries"]:
        if row["id"] == entry_id:
            row["status"] = "closed"
            row["exit"] = exit_price
            row["closed_at"] = datetime.now().isoformat(timespec="seconds")
            row["pnl_pct"] = round((exit_price / row["entry"] - 1) * 100, 2)
            _save(data)
            return {"ok": True, "entry": row}
    return {"ok": False, "error": "Entry not found"}