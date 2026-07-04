"""Binay's swing strategy: 3% profit, average 30% up to 5 times on -3% drops."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
POSITION_FILE = BASE_DIR / "data" / "position.json"
CONFIG = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))


@dataclass
class Lot:
    price: float
    qty: int
    amount: float
    kind: str  # initial | average
    date: str


@dataclass
class Position:
    active: bool
    symbol: str
    initial_amount: float
    lots: list
    average_count: int
    opened: str

    @property
    def total_qty(self) -> int:
        return sum(l["qty"] for l in self.lots)

    @property
    def total_invested(self) -> float:
        return sum(l["amount"] for l in self.lots)

    @property
    def avg_price(self) -> float:
        tq = self.total_qty
        return self.total_invested / tq if tq else 0

    def pnl_pct(self, ltp: float) -> float:
        if self.avg_price <= 0:
            return 0
        return ((ltp / self.avg_price) - 1) * 100

    def sell_target(self) -> float:
        return round(self.avg_price * (1 + CONFIG["profit_target_pct"] / 100), 2)

    def next_avg_trigger(self) -> float:
        return round(self.avg_price * (1 - CONFIG["loss_trigger_pct"] / 100), 2)

    def can_average(self) -> bool:
        return self.average_count < CONFIG["max_averages"]


def load_position() -> Position | None:
    if not POSITION_FILE.exists():
        return None
    try:
        d = json.loads(POSITION_FILE.read_text(encoding="utf-8"))
        if not d.get("active"):
            return None
        return Position(**d)
    except (json.JSONDecodeError, TypeError):
        return None


def calc_best_buy_price(quote: dict) -> float:
    """Best limit price: today's low when valid, otherwise LTP."""
    ltp = float(quote.get("ltp") or 0)
    if ltp <= 0:
        return 0.0
    low = float(quote.get("low") or 0)
    if low > 0 and low <= ltp:
        return round(low, 2)
    return round(ltp, 2)


def calc_buy_order(budget: float | None = None, price: float = 0) -> dict:
    """Qty and cost for a fixed Rs. budget at the given buy price."""
    budget = budget or CONFIG["default_investment"]
    if price <= 0:
        return {"qty": 0, "price": 0, "amount": 0, "budget": budget}
    qty = int(budget / price)
    if qty < 1:
        qty = 1
    amount = round(qty * price, 2)
    return {
        "qty": qty,
        "price": round(price, 2),
        "amount": amount,
        "budget": budget,
    }


def enrich_pick_with_order(pick: dict, quote: dict | None = None) -> dict:
    """Add best buy price, qty, and amounts to a scanner pick."""
    budget = CONFIG["default_investment"]
    if quote and quote.get("ltp", 0) > 0:
        best = calc_best_buy_price(quote)
        pick["price"] = round(float(quote["ltp"]), 2)
        pick["live_source"] = quote.get("source", "nse")
        pick["change_pct"] = quote.get("change_pct", 0)
    else:
        best = round(float(pick.get("entry") or pick.get("price") or 0), 2)

    if best <= 0:
        return pick

    order = calc_buy_order(budget, best)
    pick["best_buy_price"] = best
    pick["entry"] = best
    pick["buy_qty"] = order["qty"]
    pick["buy_amount"] = order["amount"]
    pick["buy_budget"] = budget
    pick["target"] = round(best * (1 + CONFIG["profit_target_pct"] / 100), 2)
    pick["avg_trigger"] = round(best * (1 - CONFIG["loss_trigger_pct"] / 100), 2)
    return pick


def save_position(pos: Position | None) -> None:
    POSITION_FILE.parent.mkdir(parents=True, exist_ok=True)
    if pos is None or not pos.active:
        POSITION_FILE.write_text(json.dumps({"active": False}, indent=2), encoding="utf-8")
        return
    POSITION_FILE.write_text(json.dumps(asdict(pos), indent=2), encoding="utf-8")


def open_position(symbol: str, price: float, amount: float | None = None) -> Position:
    budget = amount or CONFIG["default_investment"]
    order = calc_buy_order(budget, price)
    lot = {
        "price": order["price"],
        "qty": order["qty"],
        "amount": order["amount"],
        "kind": "initial",
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    pos = Position(
        active=True,
        symbol=symbol,
        initial_amount=budget,
        lots=[lot],
        average_count=0,
        opened=lot["date"],
    )
    save_position(pos)
    return pos


def add_average(pos: Position, price: float) -> Position:
    add_budget = pos.initial_amount * CONFIG["average_fraction"]
    order = calc_buy_order(add_budget, price)
    pos.lots.append({
        "price": order["price"],
        "qty": order["qty"],
        "amount": order["amount"],
        "kind": "average",
        "date": datetime.now().strftime("%Y-%m-%d"),
    })
    pos.average_count += 1
    save_position(pos)
    return pos


def close_position() -> None:
    save_position(None)


def evaluate_position(ltp: float, pos: Position) -> dict:
    """Return signal: SELL | AVERAGE | HOLD with details."""
    pnl = pos.pnl_pct(ltp)
    sell_at = pos.sell_target()
    avg_at = pos.next_avg_trigger()

    if pnl >= CONFIG["profit_target_pct"]:
        return {
            "signal": "SELL",
            "confidence": min(95, 70 + pnl),
            "reason": f"Target hit: +{pnl:.2f}% profit (goal {CONFIG['profit_target_pct']}%)",
            "ltp": ltp,
            "avg_price": round(pos.avg_price, 2),
            "sell_price": sell_at,
            "pnl_pct": round(pnl, 2),
            "total_invested": round(pos.total_invested, 2),
            "total_qty": pos.total_qty,
        }

    if ltp <= avg_at and pos.can_average():
        add_budget = pos.initial_amount * CONFIG["average_fraction"]
        add_order = calc_buy_order(add_budget, ltp)
        return {
            "signal": "AVERAGE",
            "confidence": 75,
            "reason": (
                f"Price Rs.{ltp:.2f} fell 3% below avg Rs.{pos.avg_price:.2f}. "
                f"Add {int(CONFIG['average_fraction']*100)}% of initial (avg {pos.average_count+1}/{CONFIG['max_averages']})"
            ),
            "ltp": ltp,
            "avg_price": round(pos.avg_price, 2),
            "add_amount": add_order["amount"],
            "add_budget": round(add_budget, 2),
            "add_qty": add_order["qty"],
            "add_price": add_order["price"],
            "average_count": pos.average_count,
            "pnl_pct": round(pnl, 2),
        }

    return {
        "signal": "HOLD",
        "confidence": 50,
        "reason": f"Wait for +{CONFIG['profit_target_pct']}% (now {pnl:+.2f}%). Sell at Rs.{sell_at:.2f}",
        "ltp": ltp,
        "avg_price": round(pos.avg_price, 2),
        "sell_price": sell_at,
        "avg_trigger": avg_at,
        "pnl_pct": round(pnl, 2),
    }