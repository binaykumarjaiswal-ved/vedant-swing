"""Send trading signals to Telegram."""

from __future__ import annotations

from telegram_notify import format_buy, format_position
from telegram_send import send_message


def send_buy(pick: dict, ai_note: str = "") -> bool:
    return send_message(format_buy(pick, ai_note))


def send_position(signal: dict, symbol: str) -> bool:
    return send_message(format_position(signal, symbol))