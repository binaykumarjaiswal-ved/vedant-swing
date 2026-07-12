"""Swing position rules: target, hard stop, max 1 optional average. Recommend-only."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
POSITION_FILE = BASE_DIR / "data" / "position.json"
CONFIG = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))


def _cfg() -> dict:
    """Reload config so runtime changes apply."""
    global CONFIG
    try:
        CONFIG = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    return CONFIG


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
        c = _cfg()
        # Prefer stored target on first lot if present
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
    c = _cfg()
    budget = budget or c.get("default_investment", 30000)
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
    """Add best buy price, ATR risk levels, and risk-sized qty to a pick."""
    c = _cfg()
    if quote and quote.get("ltp", 0) > 0:
        best = calc_best_buy_price(quote)
        pick["price"] = round(float(quote["ltp"]), 2)
        pick["live_source"] = quote.get("source", "nse")
        pick["change_pct"] = quote.get("change_pct", 0)
    else:
        best = round(float(pick.get("entry") or pick.get("price") or 0), 2)

    if best <= 0:
        return pick

    pick["best_buy_price"] = best
    pick["entry"] = best

    # Prefer risk engine (ATR + risk %)
    try:
        from risk_engine import enrich_pick_with_risk

        pick["price"] = pick.get("price") or best
        return enrich_pick_with_risk(pick)
    except Exception:
        pass

    budget = c.get("default_investment", 30000)
    order = calc_buy_order(budget, best)
    pick["buy_qty"] = order["qty"]
    pick["buy_amount"] = order["amount"]
    pick["buy_budget"] = budget
    pick["target"] = round(best * (1 + c.get("profit_target_pct", 3.0) / 100), 2)
    pick["stop"] = round(best * (1 - c.get("hard_stop_pct", 4.0) / 100), 2)
    pick["avg_trigger"] = round(best * (1 - c.get("loss_trigger_pct", 3.0) / 100), 2)
    pick["target_pct"] = c.get("profit_target_pct", 3.0)
    pick["stop_pct"] = c.get("hard_stop_pct", 4.0)
    return pick


def save_position(pos: Position | None) -> None:
    POSITION_FILE.parent.mkdir(parents=True, exist_ok=True)
    if pos is None or not pos.active:
        POSITION_FILE.write_text(json.dumps({"active": False}, indent=2), encoding="utf-8")
        return
    POSITION_FILE.write_text(json.dumps(asdict(pos), indent=2), encoding="utf-8")


def open_position(
    symbol: str,
    price: float,
    amount: float | None = None,
    stop: float | None = None,
    target: float | None = None,
) -> Position:
    c = _cfg()
    budget = amount or c.get("default_investment", 30000)
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
        initial_amount=budget,
        lots=[lot],
        average_count=0,
        opened=lot["date"],
    )
    save_position(pos)
    return pos


def add_average(pos: Position, price: float) -> Position:
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
    save_position(pos)
    return pos


def close_position() -> None:
    save_position(None)


def evaluate_position(ltp: float, pos: Position) -> dict:
    """Return signal: SELL | STOP | AVERAGE | HOLD with details."""
    c = _cfg()
    pnl = pos.pnl_pct(ltp)
    sell_at = pos.sell_target()
    stop_at = pos.hard_stop()
    avg_at = pos.next_avg_trigger()
    target_pct = c.get("profit_target_pct", 3.0)

    # Hard stop first (capital protection)
    if c.get("hard_stop_enabled", True) and ltp <= stop_at:
        return {
            "signal": "STOP",
            "confidence": 90,
            "reason": (
                f"Hard stop hit: LTP Rs.{ltp:.2f} <= stop Rs.{stop_at:.2f} "
                f"({pnl:+.2f}% from avg Rs.{pos.avg_price:.2f})"
            ),
            "ltp": ltp,
            "avg_price": round(pos.avg_price, 2),
            "sell_price": stop_at,
            "stop_price": stop_at,
            "pnl_pct": round(pnl, 2),
            "total_invested": round(pos.total_invested, 2),
            "total_qty": pos.total_qty,
        }

    if ltp >= sell_at or pnl >= target_pct:
        return {
            "signal": "SELL",
            "confidence": min(95, 70 + max(pnl, 0)),
            "reason": f"Target zone: +{pnl:.2f}% (goal ~{target_pct}%). Sell near Rs.{sell_at:.2f}",
            "ltp": ltp,
            "avg_price": round(pos.avg_price, 2),
            "sell_price": sell_at,
            "stop_price": stop_at,
            "pnl_pct": round(pnl, 2),
            "total_invested": round(pos.total_invested, 2),
            "total_qty": pos.total_qty,
        }

    # Optional single average only (max_averages default 1)
    if ltp <= avg_at and pos.can_average() and int(c.get("max_averages", 1)) > 0:
        add_budget = pos.initial_amount * c.get("average_fraction", 0.30)
        add_order = calc_buy_order(add_budget, ltp)
        max_avg = int(c.get("max_averages", 1))
        return {
            "signal": "AVERAGE",
            "confidence": 70,
            "reason": (
                f"Price Rs.{ltp:.2f} below avg trigger Rs.{avg_at:.2f}. "
                f"Optional add {int(c.get('average_fraction', 0.3)*100)}% "
                f"(avg {pos.average_count + 1}/{max_avg}). Hard stop remains Rs.{stop_at:.2f}."
            ),
            "ltp": ltp,
            "avg_price": round(pos.avg_price, 2),
            "add_amount": add_order["amount"],
            "add_budget": round(add_budget, 2),
            "add_qty": add_order["qty"],
            "add_price": add_order["price"],
            "average_count": pos.average_count,
            "stop_price": stop_at,
            "pnl_pct": round(pnl, 2),
        }

    return {
        "signal": "HOLD",
        "confidence": 50,
        "reason": (
            f"Hold. PnL {pnl:+.2f}%. Target Rs.{sell_at:.2f} | "
            f"Stop Rs.{stop_at:.2f} | Avg trigger Rs.{avg_at:.2f}"
        ),
        "ltp": ltp,
        "avg_price": round(pos.avg_price, 2),
        "sell_price": sell_at,
        "stop_price": stop_at,
        "avg_trigger": avg_at,
        "pnl_pct": round(pnl, 2),
    }