"""Telegram alerts via env vars (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)."""

from __future__ import annotations

import requests

from pa_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def is_telegram_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def send_telegram(text: str) -> bool:
    if not is_telegram_configured():
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text[:4000]},
            timeout=20,
        )
        return r.ok
    except Exception:
        return False