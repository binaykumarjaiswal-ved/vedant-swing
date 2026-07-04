"""Process /buy /sell /average /status from Telegram (no 24/7 listener needed)."""

from __future__ import annotations

import json
from pathlib import Path

import requests

from nse_data import nse_quote
from pa_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from strategy import (
    CONFIG,
    add_average,
    calc_best_buy_price,
    calc_buy_order,
    close_position,
    load_position,
    open_position,
)
from telegram_send import send_message

BASE_DIR = Path(__file__).parent
OFFSET_FILE = BASE_DIR / "data" / "telegram_offset.json"


def _load_offset() -> int:
    if not OFFSET_FILE.exists():
        return 0
    try:
        return int(json.loads(OFFSET_FILE.read_text(encoding="utf-8")).get("offset", 0))
    except (json.JSONDecodeError, ValueError):
        return 0


def _save_offset(offset: int) -> None:
    OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(json.dumps({"offset": offset}, indent=2), encoding="utf-8")


def process_commands() -> int:
    """Poll Telegram once; return number of commands handled."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return 0

    offset = _load_offset()
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        resp = requests.get(url, params={"offset": offset, "timeout": 5}, timeout=15)
        data = resp.json()
    except Exception:
        return 0

    if not data.get("ok"):
        return 0

    handled = 0
    max_id = offset
    for upd in data.get("result", []):
        max_id = max(max_id, upd["update_id"] + 1)
        msg = upd.get("message") or {}
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if chat_id != str(TELEGRAM_CHAT_ID):
            continue
        text = (msg.get("text") or "").strip()
        if not text.startswith("/"):
            continue
        if _handle_command(text):
            handled += 1

    if max_id > offset:
        _save_offset(max_id)
    return handled


def _handle_command(text: str) -> bool:
    parts = text.split()
    cmd = parts[0].lower().split("@")[0]

    if cmd in ("/help", "/start"):
        send_message(
            "Stock Analyst Commands:\n"
            "/buy SYMBOL — record purchase (e.g. /buy TITAN)\n"
            "/average — record averaging down\n"
            "/sell — close position\n"
            "/status — show open position\n"
            "/help — this message"
        )
        return True

    if cmd == "/status":
        pos = load_position()
        if not pos:
            send_message("No open position.")
            return True
        q = nse_quote(pos.symbol)
        ltp = q["ltp"] if q else 0
        send_message(
            f"Position: {pos.symbol}\n"
            f"Qty: {pos.total_qty}\n"
            f"Avg: Rs.{pos.avg_price:.2f}\n"
            f"LTP: Rs.{ltp:.2f}\n"
            f"P&L: {pos.pnl_pct(ltp):+.2f}%\n"
            f"Sell target: Rs.{pos.sell_target():.2f}\n"
            f"Avg trigger: Rs.{pos.next_avg_trigger():.2f}\n"
            f"Averages: {pos.average_count}/5"
        )
        return True

    if cmd == "/sell":
        pos = load_position()
        if not pos:
            send_message("No open position to sell.")
            return True
        sym = pos.symbol
        close_position()
        try:
            from alert_state import clear_on_close
            clear_on_close()
        except ImportError:
            pass
        send_message(f"Position closed: {sym}. Ready for next BUY signal.")
        return True

    if cmd == "/average":
        pos = load_position()
        if not pos:
            send_message("No open position.")
            return True
        if not pos.can_average():
            send_message("Max 5 averages already used.")
            return True
        q = nse_quote(pos.symbol)
        if not q:
            send_message(f"Could not get price for {pos.symbol}")
            return True
        best = calc_best_buy_price(q)
        add_budget = pos.initial_amount * CONFIG["average_fraction"]
        order = calc_buy_order(add_budget, best)
        pos = add_average(pos, best)
        send_message(
            f"Averaged {pos.symbol}\n"
            f"Best price: Rs.{best:.2f}\n"
            f"Added: {order['qty']} shares | Rs.{order['amount']:,.2f}\n"
            f"New avg Rs.{pos.avg_price:.2f}\n"
            f"Sell target Rs.{pos.sell_target():.2f}"
        )
        return True

    if cmd == "/buy":
        if len(parts) < 2:
            send_message("Usage: /buy SYMBOL (e.g. /buy TITAN)")
            return True
        symbol = parts[1].upper()
        if load_position():
            send_message(f"Already holding {load_position().symbol}. /sell first.")
            return True
        q = nse_quote(symbol)
        if not q:
            send_message(f"Could not get price for {symbol}")
            return True
        best = calc_best_buy_price(q)
        pos = open_position(symbol, best)
        send_message(
            f"BUY recorded: {symbol}\n"
            f"Best buy price: Rs.{best:.2f}\n"
            f"Qty: {pos.total_qty} shares\n"
            f"Invested: Rs.{pos.total_invested:,.2f} (budget Rs.{CONFIG['default_investment']:,.0f})\n"
            f"Sell target: Rs.{pos.sell_target():.2f}\n"
            f"Avg trigger: Rs.{pos.next_avg_trigger():.2f}"
        )
        return True

    return False