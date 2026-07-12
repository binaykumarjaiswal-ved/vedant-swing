#!/usr/bin/env python3
"""Intraday check: SELL/STOP/AVERAGE alerts for ALL open holdings."""

from __future__ import annotations

import sys
import traceback

from pa_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from telegram_commands import process_commands
from telegram_send import send_message


def main() -> int:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing")
        return 1

    try:
        n = process_commands()
        if n:
            print(f"Processed {n} Telegram command(s)")

        from market_calendar import is_intraday_window, is_trading_day

        if not is_trading_day():
            print("Not a trading day")
            return 0
        if not is_intraday_window():
            print("Outside intraday window — skip")
            return 0

        from alert_state import should_send
        from broadcast import send_position
        from holdings import list_positions
        from nse_data import nse_quote
        from strategy import evaluate_position

        positions = list_positions()
        if not positions:
            print("No holdings — skip")
            return 0

        sent = 0
        for pos in positions:
            quote = nse_quote(pos.symbol)
            if not quote or quote.get("ltp", 0) <= 0:
                print(f"{pos.symbol}: no price")
                continue
            signal = evaluate_position(float(quote["ltp"]), pos)
            sig = signal.get("signal")
            if sig not in ("SELL", "STOP", "AVERAGE"):
                print(f"HOLD {pos.symbol} {signal.get('pnl_pct', 0):+.2f}%")
                continue
            if not should_send(pos.symbol, sig, signal.get("pnl_pct", 0)):
                print(f"{pos.symbol} {sig}: already alerted recently")
                continue
            if send_position(signal, pos.symbol):
                sent += 1
                print(f"Alert: {pos.symbol} {sig}")
            else:
                print(f"Alert send FAILED: {pos.symbol} {sig}")

        print(f"Done. Alerts sent: {sent}/{len(positions)}")
        return 0

    except Exception:
        err = traceback.format_exc()
        print(err)
        send_message(f"Position check ERROR:\n{err[:2000]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
