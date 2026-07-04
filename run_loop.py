#!/usr/bin/env python3
"""
Stock Analyst — Loop Engineering Entry Point
=============================================
  LOOP 1 — COMMANDS   Process /buy /sell /average /status from Telegram
  LOOP 2 — MARKET     Morning BUY scan OR intraday SELL/AVERAGE check
  LOOP 3 — STATE      Position saved in data/position.json (GitHub commits it)

IST schedule (real clock, not GitHub cron label):
  8:25–10:30  morning briefing (once per day)
  10:30–11:00 catch-up if GitHub delayed
  9:10–15:35  intraday position checks
  Other times commands only — no spam
"""

from __future__ import annotations

import traceback
from datetime import datetime

from market_calendar import detect_job_mode, ist_now


def loop_commands() -> int:
    from telegram_commands import process_commands
    n = process_commands()
    print(f"[Loop 1] Commands processed: {n}")
    return n


def loop_market(mode: str) -> int:
    if mode == "commands_only":
        print("[Loop 2] Outside market window — commands only")
        return 0

    if mode == "morning":
        print("[Loop 2] Morning BUY scan")
        from run_cloud_job import main as morning_main
        return morning_main()

    print("[Loop 2] Intraday SELL/AVERAGE check")
    from run_position_check import main as intraday_main
    return intraday_main()


def main() -> int:
    from pa_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    from telegram_send import send_message

    now = ist_now()
    mode = detect_job_mode()
    print("=" * 50)
    print("STOCK ANALYST — Loop Run")
    print(f"IST: {now.strftime('%Y-%m-%d %H:%M')} | Mode: {mode}")
    print("=" * 50)

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        return 1

    try:
        from cloud_heartbeat import should_run_market_jobs, write_heartbeat
        from pa_config import CLOUD_PROVIDER, CLOUD_ROLE

        loop_commands()
        if mode == "commands_only":
            if CLOUD_ROLE == "primary":
                write_heartbeat("primary", CLOUD_PROVIDER)
            return 0

        if not should_run_market_jobs():
            return 0

        code = loop_market(mode)
        if CLOUD_ROLE == "primary":
            write_heartbeat("primary", CLOUD_PROVIDER)
        print("[Loop 3] State in data/position.json")
        print("=" * 50)
        print("DONE")
        return code

    except Exception:
        err = traceback.format_exc()
        print(err)
        send_message(f"Stock Analyst LOOP ERROR ({mode}):\n{err[:3500]}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())