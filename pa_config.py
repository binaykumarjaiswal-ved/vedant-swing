"""Secrets and settings for cloud (PythonAnywhere / GitHub Actions)."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent


def _load_dotenv():
    env_file = BASE_DIR / "secrets.env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
STOCK_SCAN_LIMIT = int(os.environ.get("STOCK_SCAN_LIMIT", "100"))
CHECK_INTERVAL_MIN = int(os.environ.get("CHECK_INTERVAL_MIN", "10"))
AI_ENABLED = os.environ.get("AI_ENABLED", "true").lower() in ("1", "true", "yes")

# github = GitHub Actions (free) | oracle = Oracle VM
CLOUD_PROVIDER = os.environ.get("CLOUD_PROVIDER", "github").strip().lower()
# primary = main alerts | backup = only if other cloud heartbeat is stale
CLOUD_ROLE = os.environ.get("CLOUD_ROLE", "primary").strip().lower()
BACKUP_STALE_MINUTES = int(os.environ.get("BACKUP_STALE_MINUTES", "25"))

EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "false").lower() in ("1", "true", "yes")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "").strip()
EMAIL_TO = os.environ.get("EMAIL_TO", "").strip()
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD", "").strip()