"""Process /buy /sell /average /status /holdings from Telegram (multi-stock)."""

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
    close_position,
    get_position,
    list_positions,
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
        print("TELEGRAM: not configured (set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)")
        return 0

    offset = _load_offset()
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        resp = requests.get(url, params={"offset": offset, "timeout": 5}, timeout=15)
        data = resp.json()
    except Exception as exc:
        print("TELEGRAM poll error:", exc)
        return 0

    if not data.get("ok"):
        print("TELEGRAM getUpdates failed:", data.get("description", data))
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
        max_h = CONFIG.get("max_holdings", 10)
        send_message(
            "Vedant Swing — multi holdings\n\n"
            f"/buy SYMBOL [price] [qty] — add holding (max {max_h})\n"
            "  e.g. /buy TITAN\n"
            "  e.g. /buy RELIANCE 1400 20\n"
            "/sell SYMBOL — close that holding\n"
            "/average SYMBOL — record optional average\n"
            "/status — all holdings + SELL/HOLD/STOP\n"
            "/holdings — same as /status\n"
            "/help — this message\n\n"
            "Bot does NOT place broker orders. You trade, then /buy or /sell."
        )
        return True

    if cmd in ("/status", "/holdings"):
        return _cmd_status()

    if cmd == "/sell":
        if len(parts) < 2:
            open_list = list_positions()
            if len(open_list) == 1:
                symbol = open_list[0].symbol
            elif not open_list:
                send_message("No open holdings.")
                return True
            else:
                syms = ", ".join(p.symbol for p in open_list)
                send_message(f"Multiple holdings. Use /sell SYMBOL\nOpen: {syms}")
                return True
        else:
            symbol = parts[1].upper()
        try:
            if not close_position(symbol):
                send_message(f"No open holding for {symbol}.")
                return True
        except ValueError as exc:
            send_message(str(exc))
            return True
        try:
            from alert_state import clear_symbol
            clear_symbol(symbol)
        except Exception:
            pass
        send_message(f"Closed tracking for {symbol}. (Sell in broker yourself if not done.)")
        return True

    if cmd == "/average":
        if len(parts) < 2:
            open_list = list_positions()
            if len(open_list) == 1:
                symbol = open_list[0].symbol
            else:
                send_message("Usage: /average SYMBOL")
                return True
        else:
            symbol = parts[1].upper()
        pos = get_position(symbol)
        if not pos:
            send_message(f"No open holding for {symbol}.")
            return True
        if not pos.can_average():
            send_message(f"{symbol}: max averages reached.")
            return True
        q = nse_quote(symbol)
        if not q:
            send_message(f"Could not get price for {symbol}")
            return True
        price = calc_best_buy_price(q)
        if len(parts) >= 3:
            try:
                price = float(parts[2])
            except ValueError:
                pass
        pos = add_average(pos, price)
        send_message(
            f"AVERAGE recorded: {symbol}\n"
            f"Add @ Rs.{price:.2f}\n"
            f"New avg Rs.{pos.avg_price:.2f}\n"
            f"Qty {pos.total_qty} | Target Rs.{pos.sell_target():.2f} | Stop Rs.{pos.hard_stop():.2f}"
        )
        return True

    if cmd == "/buy":
        if len(parts) < 2:
            send_message("Usage: /buy SYMBOL [price] [qty]\ne.g. /buy DABUR")
            return True
        symbol = parts[1].upper()
        if get_position(symbol):
            send_message(f"Already tracking {symbol}. /sell {symbol} first to reset.")
            return True
        price = 0.0
        qty = None
        if len(parts) >= 3:
            try:
                price = float(parts[2])
            except ValueError:
                price = 0
        if len(parts) >= 4:
            try:
                qty = int(float(parts[3]))
            except ValueError:
                qty = None
        if price <= 0:
            q = nse_quote(symbol)
            if not q:
                send_message(f"Could not get price for {symbol}")
                return True
            price = calc_best_buy_price(q)
        try:
            pos = open_position(symbol, price, qty=qty)
        except ValueError as exc:
            send_message(str(exc))
            return True
        send_message(
            f"HOLDING added: {symbol}\n"
            f"Entry Rs.{price:.2f} | Qty {pos.total_qty}\n"
            f"Invested Rs.{pos.total_invested:,.0f}\n"
            f"Target Rs.{pos.sell_target():.2f} | Stop Rs.{pos.hard_stop():.2f}\n"
            f"Open holdings: {len(list_positions())}/{CONFIG.get('max_holdings', 10)}\n"
            "You will get SELL/STOP/AVERAGE alerts on cloud checks."
        )
        return True

    return False


def _cmd_status() -> bool:
    from strategy import evaluate_position

    positions = list_positions()
    if not positions:
        send_message("No open holdings.\nAdd with /buy SYMBOL after you buy in broker.")
        return True

    lines = [f"HOLDINGS ({len(positions)}/{CONFIG.get('max_holdings', 10)})", ""]
    for pos in positions:
        q = nse_quote(pos.symbol)
        ltp = float(q["ltp"]) if q and q.get("ltp") else 0
        if ltp > 0:
            sig = evaluate_position(ltp, pos)
            signal = sig.get("signal", "—")
            pnl = sig.get("pnl_pct", pos.pnl_pct(ltp))
            reason = (sig.get("reason") or "")[:80]
        else:
            signal, pnl, reason = "?", 0, "No price"
        lines.append(
            f"{pos.symbol} [{signal}]\n"
            f"  Qty {pos.total_qty} @ Rs.{pos.avg_price:.2f} | LTP Rs.{ltp:.2f} | P&L {pnl:+.2f}%\n"
            f"  Target Rs.{pos.sell_target():.2f} | Stop Rs.{pos.hard_stop():.2f}\n"
            f"  {reason}"
        )
        lines.append("")
    lines.append("Not SEBI advice. Trade manually in broker.")
    send_message("\n".join(lines))
    return True
