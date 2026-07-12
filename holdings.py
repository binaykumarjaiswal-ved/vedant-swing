"""
Multi-stock holdings for Vedant Swing.

Storage: data/holdings.json
Also migrates legacy single data/position.json on first load.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent
HOLDINGS_FILE = BASE_DIR / "data" / "holdings.json"
LEGACY_POSITION = BASE_DIR / "data" / "position.json"
CONFIG = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))


def _cfg() -> dict:
    global CONFIG
    try:
        CONFIG = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    return CONFIG


@dataclass
class Position:
    active: bool
    symbol: str
    initial_amount: float
    lots: list
    average_count: int
    opened: str
    notes: str = ""

    @property
    def total_qty(self) -> int:
        return sum(int(l.get("qty") or 0) for l in self.lots)

    @property
    def total_invested(self) -> float:
        return sum(float(l.get("amount") or 0) for l in self.lots)

    @property
    def avg_price(self) -> float:
        tq = self.total_qty
        return self.total_invested / tq if tq else 0

    def pnl_pct(self, ltp: float) -> float:
        if self.avg_price <= 0:
            return 0
        return ((ltp / self.avg_price) - 1) * 100

    def sell_target(self) -> float:
        c = _cfg()
        for lot in self.lots:
            if lot.get("target"):
                return round(float(lot["target"]), 2)
        return round(self.avg_price * (1 + c.get("profit_target_pct", 3.0) / 100), 2)

    def hard_stop(self) -> float:
        c = _cfg()
        for lot in self.lots:
            if lot.get("stop"):
                return round(float(lot["stop"]), 2)
        return round(self.avg_price * (1 - c.get("hard_stop_pct", 4.0) / 100), 2)

    def next_avg_trigger(self) -> float:
        c = _cfg()
        return round(self.avg_price * (1 - c.get("loss_trigger_pct", 3.0) / 100), 2)

    def can_average(self) -> bool:
        c = _cfg()
        return self.average_count < int(c.get("max_averages", 1))

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _empty_store() -> dict:
    return {"version": 2, "positions": []}


def _load_store() -> dict:
    HOLDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if HOLDINGS_FILE.exists():
        try:
            d = json.loads(HOLDINGS_FILE.read_text(encoding="utf-8"))
            if "positions" in d:
                return d
        except (json.JSONDecodeError, TypeError):
            pass

    # Migrate legacy single position
    if LEGACY_POSITION.exists():
        try:
            legacy = json.loads(LEGACY_POSITION.read_text(encoding="utf-8"))
            if legacy.get("active") and legacy.get("symbol"):
                store = _empty_store()
                store["positions"].append({
                    "active": True,
                    "symbol": legacy["symbol"].upper(),
                    "initial_amount": float(legacy.get("initial_amount") or _cfg().get("default_investment", 30000)),
                    "lots": legacy.get("lots") or [],
                    "average_count": int(legacy.get("average_count") or 0),
                    "opened": legacy.get("opened") or datetime.now().strftime("%Y-%m-%d"),
                    "notes": "migrated from position.json",
                })
                _save_store(store)
                return store
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    store = _empty_store()
    _save_store(store)
    return store


def _save_store(store: dict) -> None:
    HOLDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    HOLDINGS_FILE.write_text(json.dumps(store, indent=2), encoding="utf-8")
    # Keep legacy file as primary position snapshot for older cloud tools
    positions = [p for p in store.get("positions", []) if p.get("active")]
    if positions:
        primary = positions[0]
        LEGACY_POSITION.write_text(json.dumps(primary, indent=2), encoding="utf-8")
    else:
        LEGACY_POSITION.write_text(json.dumps({"active": False}, indent=2), encoding="utf-8")


def _pos_from_dict(d: dict) -> Position:
    return Position(
        active=bool(d.get("active", True)),
        symbol=str(d.get("symbol", "")).upper(),
        initial_amount=float(d.get("initial_amount") or 0),
        lots=list(d.get("lots") or []),
        average_count=int(d.get("average_count") or 0),
        opened=str(d.get("opened") or ""),
        notes=str(d.get("notes") or ""),
    )


def list_positions() -> list[Position]:
    store = _load_store()
    out = []
    for d in store.get("positions", []):
        if d.get("active") and d.get("symbol"):
            out.append(_pos_from_dict(d))
    return out


def get_position(symbol: str) -> Position | None:
    symbol = (symbol or "").upper().strip()
    for p in list_positions():
        if p.symbol == symbol:
            return p
    return None


def load_position() -> Position | None:
    """Backward compatible: first open position (or None)."""
    positions = list_positions()
    return positions[0] if positions else None


def max_holdings() -> int:
    return int(_cfg().get("max_holdings", 10))


def open_position(
    symbol: str,
    price: float,
    amount: float | None = None,
    stop: float | None = None,
    target: float | None = None,
    qty: int | None = None,
    notes: str = "",
) -> Position:
    from strategy import calc_buy_order

    symbol = symbol.upper().strip()
    if get_position(symbol):
        raise ValueError(f"Already holding {symbol}")

    store = _load_store()
    active = [p for p in store.get("positions", []) if p.get("active")]
    if len(active) >= max_holdings():
        raise ValueError(f"Max holdings ({max_holdings()}) reached. Sell one first.")

    c = _cfg()
    budget = amount or c.get("default_investment", 30000)
    if qty and qty > 0 and price > 0:
        order = {
            "qty": int(qty),
            "price": round(price, 2),
            "amount": round(qty * price, 2),
            "budget": budget,
        }
    else:
        order = calc_buy_order(budget, price)

    if stop is None:
        stop = round(order["price"] * (1 - c.get("hard_stop_pct", 4.0) / 100), 2)
    if target is None:
        target = round(order["price"] * (1 + c.get("profit_target_pct", 3.0) / 100), 2)

    lot = {
        "price": order["price"],
        "qty": order["qty"],
        "amount": order["amount"],
        "kind": "initial",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "stop": stop,
        "target": target,
    }
    pos = Position(
        active=True,
        symbol=symbol,
        initial_amount=float(budget),
        lots=[lot],
        average_count=0,
        opened=lot["date"],
        notes=notes or "",
    )
    store.setdefault("positions", []).append(pos.to_dict())
    _save_store(store)
    return pos


def add_average(pos: Position, price: float) -> Position:
    from strategy import calc_buy_order

    c = _cfg()
    if not pos.can_average():
        return pos
    add_budget = pos.initial_amount * c.get("average_fraction", 0.30)
    order = calc_buy_order(add_budget, price)
    pos.lots.append({
        "price": order["price"],
        "qty": order["qty"],
        "amount": order["amount"],
        "kind": "average",
        "date": datetime.now().strftime("%Y-%m-%d"),
    })
    pos.average_count += 1
    _upsert(pos)
    return pos


def close_position(symbol: str | None = None) -> bool:
    """Close one symbol, or all if symbol is None and only one open."""
    store = _load_store()
    positions = store.get("positions") or []
    if not positions:
        return False

    if symbol:
        symbol = symbol.upper().strip()
        found = False
        for p in positions:
            if p.get("active") and p.get("symbol", "").upper() == symbol:
                p["active"] = False
                p["closed"] = datetime.now().strftime("%Y-%m-%d")
                found = True
        if found:
            _save_store(store)
        return found

    active = [p for p in positions if p.get("active")]
    if len(active) == 1:
        active[0]["active"] = False
        active[0]["closed"] = datetime.now().strftime("%Y-%m-%d")
        _save_store(store)
        return True
    if len(active) > 1:
        raise ValueError("Multiple holdings — use /sell SYMBOL")
    return False


def _upsert(pos: Position) -> None:
    store = _load_store()
    updated = False
    for i, p in enumerate(store.get("positions") or []):
        if p.get("symbol", "").upper() == pos.symbol and p.get("active"):
            store["positions"][i] = pos.to_dict()
            updated = True
            break
    if not updated:
        store.setdefault("positions", []).append(pos.to_dict())
    _save_store(store)


def evaluate_all(quotes: dict[str, float] | None = None) -> list[dict[str, Any]]:
    """Evaluate every open holding. quotes: {symbol: ltp} optional."""
    from strategy import evaluate_position
    from nse_data import nse_quote

    results = []
    for pos in list_positions():
        ltp = 0.0
        if quotes and pos.symbol in quotes:
            ltp = float(quotes[pos.symbol] or 0)
        if ltp <= 0:
            q = nse_quote(pos.symbol)
            ltp = float(q["ltp"]) if q and q.get("ltp") else 0
        if ltp <= 0:
            results.append({
                "symbol": pos.symbol,
                "signal": "ERROR",
                "reason": "No price",
                "position": pos,
            })
            continue
        sig = evaluate_position(ltp, pos)
        sig["symbol"] = pos.symbol
        sig["position"] = pos
        results.append(sig)
    return results


def portfolio_summary() -> dict:
    rows = []
    total_invested = 0.0
    total_value = 0.0
    for pos in list_positions():
        from nse_data import nse_quote
        q = nse_quote(pos.symbol)
        ltp = float(q["ltp"]) if q and q.get("ltp") else pos.avg_price
        from strategy import evaluate_position
        sig = evaluate_position(ltp, pos) if ltp > 0 else {"signal": "—", "pnl_pct": 0, "reason": ""}
        invested = pos.total_invested
        value = pos.total_qty * ltp
        total_invested += invested
        total_value += value
        rows.append({
            "symbol": pos.symbol,
            "qty": pos.total_qty,
            "avg_price": round(pos.avg_price, 2),
            "ltp": round(ltp, 2),
            "invested": round(invested, 2),
            "value": round(value, 2),
            "pnl_pct": round(pos.pnl_pct(ltp), 2),
            "pnl": round(value - invested, 2),
            "sell_target": pos.sell_target(),
            "stop": pos.hard_stop(),
            "avg_trigger": pos.next_avg_trigger(),
            "averages": f"{pos.average_count}/{_cfg().get('max_averages', 1)}",
            "opened": pos.opened,
            "signal": sig.get("signal", "—"),
            "signal_reason": sig.get("reason", ""),
            "change_pct": q.get("change_pct", 0) if q else 0,
        })
    return {
        "count": len(rows),
        "max_holdings": max_holdings(),
        "total_invested": round(total_invested, 2),
        "total_value": round(total_value, 2),
        "total_pnl": round(total_value - total_invested, 2),
        "total_pnl_pct": round(
            ((total_value / total_invested) - 1) * 100, 2
        ) if total_invested > 0 else 0,
        "positions": rows,
    }
