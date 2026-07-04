"""Send Telegram messages using secrets.env."""

from __future__ import annotations

import requests

from pa_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

MAX_LEN = 4000


def send_message(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in secrets.env")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    ok = True
    for chunk in _split(text, MAX_LEN):
        try:
            resp = requests.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": chunk,
                    "disable_web_page_preview": True,
                },
                timeout=60,
            )
            data = resp.json()
            if not data.get("ok"):
                print("TELEGRAM FAILED:", data.get("description", data))
                ok = False
            else:
                print("TELEGRAM SENT OK")
        except Exception as e:
            print("Send failed:", e)
            ok = False
    return ok


def _split(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return parts