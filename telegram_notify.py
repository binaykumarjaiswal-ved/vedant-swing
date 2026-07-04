"""Send Stock Analyst signals via existing Telegram Agent."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
CONFIG = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))


def _telegram_module():
    tg_path = Path(CONFIG.get("telegram_path", r"D:\BINAY-Projects\09-Telegram-Agent"))
    if not tg_path.exists():
        return None
    sys.path.insert(0, str(tg_path))
    try:
        from telegram_send import send_message  # noqa: WPS433
        from load_telegram import is_configured  # noqa: WPS433
        if not is_configured():
            return None
        return send_message
    except ImportError:
        return None


def send_signal(message: str) -> bool:
    send = _telegram_module()
    if not send:
        print("  Telegram not configured — run 09-Telegram-Agent SETUP.bat")
        return False
    return send(message)


def format_buy(pick: dict, ai_note: str = "") -> str:
    inv = CONFIG.get("default_investment", 30000)
    best = pick.get("best_buy_price", pick.get("entry", 0))
    qty = pick.get("buy_qty", 0)
    cost = pick.get("buy_amount", 0)
    lines = [
        "STOCK ANALYST — BUY SIGNAL",
        datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "",
        f"Stock: {pick['symbol']} ({pick.get('index_group', 'Nifty')})",
        f"Score: {pick.get('swing_score', 0):.0f}/100",
        f"LTP: Rs.{pick.get('price', 0):.2f}",
        f"Source: {pick.get('live_source', 'nse').upper()}",
        "",
        f"PURCHASE PLAN (fixed Rs.{inv:,.0f}):",
        f"  Best buy price: Rs.{best:.2f}",
        f"  Quantity: {qty} shares",
        f"  Actual cost: Rs.{cost:,.2f}",
        "",
        "YOUR STRATEGY LEVELS:",
        f"  Buy at: Rs.{best:.2f}",
        f"  Sell target (+3%): Rs.{pick.get('target', 0):.2f}",
        f"  Avg trigger (-3%): Rs.{pick.get('avg_trigger', 0):.2f}",
        "",
        "Technicals:",
        f"  RSI {pick.get('rsi', 0)} | Trend {pick.get('trend', '?')}",
        f"  5d {pick.get('chg_5d', 0):+.1f}% | vs Nifty {pick.get('vs_nifty_20d', 0):+.1f}%",
    ]
    reasons = pick.get("reasons", [])
    if reasons:
        lines.append(f"  {reasons[0]}")
    news = pick.get("news_summary", "")
    if news and news != "No recent news":
        lines.extend(["", "News:", f"  {news[:200]}"])
    if ai_note:
        lines.extend(["", "AI Note:", ai_note[:500]])
    lines.extend([
        "",
        "After you buy:",
        "  Laptop: CONFIRM_BUY.bat",
        f"  Cloud:  message bot /buy {pick['symbol']}",
        "Not SEBI advice. Trade at your own risk.",
    ])
    return "\n".join(lines)


def format_position(signal: dict, pos_symbol: str) -> str:
    sig = signal["signal"]
    lines = [
        f"STOCK ANALYST — {sig}",
        datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "",
        f"Position: {pos_symbol}",
        f"LTP: Rs.{signal.get('ltp', 0):.2f}",
        f"Avg cost: Rs.{signal.get('avg_price', 0):.2f}",
        f"P&L: {signal.get('pnl_pct', 0):+.2f}%",
        "",
        signal.get("reason", ""),
    ]
    if sig == "SELL":
        lines.extend([
            "",
            f"SELL at Rs.{signal.get('sell_price', signal.get('ltp', 0)):.2f} or better",
            "After selling run: CONFIRM_SELL.bat",
        ])
    elif sig == "AVERAGE":
        lines.extend([
            "",
            f"Best buy price: Rs.{signal.get('add_price', signal.get('ltp', 0)):.2f}",
            f"Add qty: {signal.get('add_qty', 0)} shares",
            f"Add cost: Rs.{signal.get('add_amount', 0):,.2f} (30% of Rs.{CONFIG.get('default_investment', 30000):,.0f})",
            f"Average {signal.get('average_count', 0) + 1}/{CONFIG.get('max_averages', 5)}",
            "After averaging run: CONFIRM_AVERAGE.bat",
        ])
    else:
        lines.extend([
            "",
            f"Hold — sell target Rs.{signal.get('sell_price', 0):.2f}",
            f"Avg trigger Rs.{signal.get('avg_trigger', 0):.2f}",
        ])
    lines.append("\nNot SEBI advice.")
    return "\n".join(lines)