"""Watchlists for Vedant Swing."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
FILE = BASE_DIR / "data" / "watchlists.json"


def _load() -> dict:
    if not FILE.exists():
        return {"lists": {"default": {"name": "My Watchlist", "symbols": [], "notes": {}}}}
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"lists": {"default": {"name": "My Watchlist", "symbols": [], "notes": {}}}}


def _save(data: dict) -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_watchlists() -> dict:
    data = _load()
    out = []
    for key, wl in data.get("lists", {}).items():
        out.append({
            "id": key,
            "name": wl.get("name", key),
            "symbols": wl.get("symbols", []),
            "count": len(wl.get("symbols", [])),
        })
    return {"lists": out}


def get_watchlist(watchlist_id: str = "default") -> dict:
    data = _load()
    wl = data.get("lists", {}).get(watchlist_id)
    if not wl:
        return {"ok": False, "error": "Watchlist not found"}
    return {"ok": True, "id": watchlist_id, **wl}


def add_symbol(symbol: str, watchlist_id: str = "default", note: str = "") -> dict:
    symbol = symbol.upper().strip()
    if not symbol:
        return {"ok": False, "error": "Symbol required"}
    data = _load()
    wl = data.setdefault("lists", {}).setdefault(watchlist_id, {
        "name": "My Watchlist", "symbols": [], "notes": {},
    })
    if symbol not in wl["symbols"]:
        wl["symbols"].append(symbol)
    if note:
        wl.setdefault("notes", {})[symbol] = note
    wl["updated"] = datetime.now().isoformat(timespec="seconds")
    _save(data)
    return {"ok": True, "watchlist": get_watchlist(watchlist_id)}


def remove_symbol(symbol: str, watchlist_id: str = "default") -> dict:
    data = _load()
    wl = data.get("lists", {}).get(watchlist_id)
    if not wl:
        return {"ok": False, "error": "Watchlist not found"}
    symbol = symbol.upper().strip()
    wl["symbols"] = [s for s in wl.get("symbols", []) if s != symbol]
    wl.get("notes", {}).pop(symbol, None)
    _save(data)
    return {"ok": True, "watchlist": get_watchlist(watchlist_id)}