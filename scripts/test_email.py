#!/usr/bin/env python3
"""Test Gmail alerts for Vedant Swing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from email_notify import is_configured, send_email


def main() -> int:
    if not is_configured():
        print(json.dumps({
            "ok": False,
            "error": "Email not configured. See SETUP_GMAIL_ALERTS.txt",
            "need": ["EMAIL_ENABLED=true", "EMAIL_FROM", "EMAIL_TO", "EMAIL_APP_PASSWORD"],
        }))
        return 1

    ok = send_email(
        "Test — Vedant Swing alerts working",
        "If you received this, Gmail alerts are configured correctly.\n\n— Vedant Swing",
        "<p>If you received this, <b>Gmail alerts</b> are working.</p>",
    )
    print(json.dumps({"ok": ok}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())