"""Primary/backup coordination — Oracle VM primary, GitHub Actions backup."""

from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent
HEARTBEAT_FILE = BASE_DIR / "data" / "cloud_heartbeat.json"


def write_heartbeat(role: str = "primary", provider: str = "github") -> None:
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "role": role,
        "provider": provider,
        "host": socket.gethostname(),
        "time_utc": datetime.now(timezone.utc).isoformat(),
    }
    HEARTBEAT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_heartbeat() -> dict | None:
    if not HEARTBEAT_FILE.exists():
        return None
    try:
        return json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def primary_is_alive(max_age_minutes: int = 25) -> bool:
    """True if primary cloud ran recently (heartbeat fresh)."""
    data = _read_heartbeat()
    if not data or data.get("role") != "primary":
        return False
    raw = data.get("time_utc", "")
    try:
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_min = (datetime.now(timezone.utc) - ts).total_seconds() / 60
        return age_min <= max_age_minutes
    except ValueError:
        return False


def should_run_market_jobs() -> bool:
    """Primary always runs market; backup only if primary heartbeat is stale."""
    from pa_config import BACKUP_STALE_MINUTES, CLOUD_ROLE

    if CLOUD_ROLE == "primary":
        return True
    if CLOUD_ROLE == "backup":
        alive = primary_is_alive(BACKUP_STALE_MINUTES)
        if alive:
            print(
                f"[Backup] Oracle primary alive (<{BACKUP_STALE_MINUTES} min) — "
                "market skipped, commands only"
            )
            return False
        print("[Backup] Oracle primary DOWN — taking over market alerts")
        return True
    return True