#!/usr/bin/env python3
"""Fast intraday check: SELL/AVERAGE alerts only. For GitHub Actions market hours."""

from __future__ import annotations

import sys
import traceback
from datetime import datetime

from pa_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from telegram_commands import process_commands
from telegram_send import send_message


def is_trading_day() -> bool:
    from market_calendar import is_trading_day as nse_trading_day
    return nse_trading_day()


def main() -> int:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: secrets.env missing")
        return 1

    try:
        process_commands()

        if not is_trading_day():
            return 0

        from market_calendar import is_intraday_window
        if not is_intraday_window():
            print("Outside intraday window (9:10 AM–3:35 PM IST) — skip")
            return 0

        from strategy import load_position
        pos = load_position()
        if not pos:
            print("No position — skip intraday check")
            return 0

        from nse_data import nse_quote
        from strategy import evaluate_position
        from broadcast import send_position

        quote = nse_quote(pos.symbol)
        if not quote or quote.get("ltp", 0) <= 0:
            print("No price")
            return 0

        signal = evaluate_position(quote["ltp"], pos)
        if signal["signal"] not in ("SELL", "AVERAGE"):
            print(f"HOLD {pos.symbol} {signal.get('pnl_pct', 0):+.2f}% — no alert")
            return 0

        from alert_state import should_send

        if not should_send(pos.symbol, signal["signal"], signal.get("pnl_pct", 0)):
            print(f"{signal['signal']} already alerted recently — skip")
            return 0

        send_position(signal, pos.symbol)
        print(f"Alert sent: {signal['signal']} (Telegram)")
        return 0

    except Exception:
        err = traceback.format_exc()
        print(err)
        send_message(f"Position check ERROR:\n{err[:2000]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())