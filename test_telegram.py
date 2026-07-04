#!/usr/bin/env python3
"""Quick Telegram test for GitHub Actions."""
from pa_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from telegram_send import send_message

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print(f"MISSING: token={bool(TELEGRAM_BOT_TOKEN)} chat={bool(TELEGRAM_CHAT_ID)}")
    raise SystemExit(1)

print(f"Token length: {len(TELEGRAM_BOT_TOKEN)}")
print(f"Chat ID: {TELEGRAM_CHAT_ID}")
ok = send_message("Stock Analyst - Telegram connection test from GitHub OK!")
print("RESULT:", "SENT" if ok else "FAILED")
raise SystemExit(0 if ok else 1)