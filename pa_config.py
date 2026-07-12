"""Secrets and settings for cloud (PythonAnywhere / GitHub Actions)."""

from __future__ import annotations

import json
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


def _load_telegram_from_agent_project() -> None:
    """Fallback: load from 09-Telegram-Agent encrypted store if secrets.env empty."""
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        return
    agent = Path(r"D:\BINAY-Projects\09-Telegram-Agent")
    if not agent.exists():
        return
    try:
        import sys
        sys.path.insert(0, str(agent))
        from load_telegram import load_telegram_env  # noqa: WPS433
        load_telegram_env()
    except Exception:
        pass


_load_telegram_from_agent_project()


def _groq_from_env_or_vault() -> str:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key:
        return key
    try:
        from secret_store import load_groq_key

        return load_groq_key()
    except Exception:
        return ""


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def refresh_telegram_env() -> tuple[str, str]:
    """Re-read env after secrets loaded (for tests / late bind)."""
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    _load_dotenv()
    _load_telegram_from_agent_project()
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    return TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
GROQ_API_KEY = _groq_from_env_or_vault()
if GROQ_API_KEY:
    os.environ.setdefault("GROQ_API_KEY", GROQ_API_KEY)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
STOCK_SCAN_LIMIT = int(os.environ.get("STOCK_SCAN_LIMIT", "100"))
CHECK_INTERVAL_MIN = int(os.environ.get("CHECK_INTERVAL_MIN", "10"))
def _config_ai_enabled() -> bool:
    try:
        cfg = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))
        return bool(cfg.get("ai_enabled", True))
    except Exception:
        return True


def is_ai_enabled() -> bool:
    """Env AI_ENABLED overrides config.json when set."""
    env = os.environ.get("AI_ENABLED", "").strip().lower()
    if env in ("1", "true", "yes"):
        return True
    if env in ("0", "false", "no"):
        return False
    return _config_ai_enabled()


AI_ENABLED = is_ai_enabled()

# github = GitHub Actions (free) | oracle = Oracle VM
CLOUD_PROVIDER = os.environ.get("CLOUD_PROVIDER", "github").strip().lower()
# primary = main alerts | backup = only if other cloud heartbeat is stale
CLOUD_ROLE = os.environ.get("CLOUD_ROLE", "primary").strip().lower()
BACKUP_STALE_MINUTES = int(os.environ.get("BACKUP_STALE_MINUTES", "25"))

EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "false").lower() in ("1", "true", "yes")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "").strip()
EMAIL_TO = os.environ.get("EMAIL_TO", "").strip()
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD", "").strip()