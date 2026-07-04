"""Paper trading portfolio for Vedant Swing."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
PORTFOLIO_FILE = BASE_DIR / "data" / "paper_portfolio.json"


def _load() -> dict:
    if not PORTFOLIO_FILE.exists():
        return {"cash": 500000.0, "positions": [], "closed": []}
    try:
        return json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"cash": 500000.0, "positions": [], "closed": []}


def _save(data: dict) -> None:
    PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_portfolio() -> dict:
    data = _load()
    return {
        "cash": round(data.get("cash", 0), 2),
        "positions": data.get("positions", []),
        "closed": data.get("closed", [])[-20:],
    }


def paper_buy(symbol: str, qty: int, price: float, stop: float = 0, target: float = 0) -> dict:
    data = _load()
    cost = qty * price
    if cost > data.get("cash", 0):
        return {"ok": False, "error": "Insufficient paper cash"}
    data["cash"] = round(data["cash"] - cost, 2)
    data["positions"].append({
        "id": str(uuid.uuid4())[:8],
        "symbol": symbol.upper(),
        "qty": qty,
        "entry": price,
        "stop": stop,
        "target": target,
        "opened": datetime.now().isoformat(timespec="seconds"),
    })
    _save(data)
    return {"ok": True, "portfolio": get_portfolio()}


def paper_sell(position_id: str, price: float) -> dict:
    data = _load()
    pos = next((p for p in data["positions"] if p["id"] == position_id), None)
    if not pos:
        return {"ok": False, "error": "Position not found"}
    proceeds = pos["qty"] * price
    pnl = proceeds - (pos["qty"] * pos["entry"])
    data["cash"] = round(data["cash"] + proceeds, 2)
    data["positions"] = [p for p in data["positions"] if p["id"] != position_id]
    data.setdefault("closed", []).append({
        **pos,
        "exit": price,
        "pnl": round(pnl, 2),
        "closed": datetime.now().isoformat(timespec="seconds"),
    })
    _save(data)
    return {"ok": True, "pnl": round(pnl, 2), "portfolio": get_portfolio()}