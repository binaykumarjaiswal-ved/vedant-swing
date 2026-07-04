"""NSE trading calendar — skip weekends and exchange holidays."""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent
CACHE = BASE_DIR / "data" / "nse_holidays.json"
MORNING_SENT_FILE = BASE_DIR / "data" / "last_morning_sent.txt"
IST = timezone(timedelta(hours=5, minutes=30))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/",
}

# Fallback if NSE API unavailable (trading holidays only)
FALLBACK_HOLIDAYS = {
    "2026-01-26",
    "2026-02-19",
    "2026-03-03",
    "2026-03-26",
    "2026-03-31",
    "2026-04-02",
    "2026-04-03",
    "2026-04-14",
    "2026-05-01",
    "2026-05-28",
    "2026-06-17",
    "2026-08-15",
    "2026-08-26",
    "2026-10-02",
    "2026-10-20",
    "2026-10-21",
    "2026-11-05",
    "2026-11-24",
    "2026-12-25",
}


def _fetch_nse_holidays() -> set[str]:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get("https://www.nseindia.com", timeout=15)
    time.sleep(0.5)
    r = s.get("https://www.nseindia.com/api/holiday-master?type=trading", timeout=20)
    r.raise_for_status()
    holidays: set[str] = set()
    for block in r.json():
        for item in block.get("tradingDate", []):
            raw = item.get("tradingDate", "")
            if raw:
                holidays.add(raw.strip())
    return holidays


def get_holiday_dates() -> set[str]:
    if CACHE.exists():
        try:
            d = json.loads(CACHE.read_text(encoding="utf-8"))
            if datetime.now() - datetime.fromisoformat(d["updated"]) < timedelta(days=30):
                return set(d["dates"])
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    try:
        dates = _fetch_nse_holidays()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(
            json.dumps({"updated": datetime.now().isoformat(), "dates": sorted(dates)}, indent=2),
            encoding="utf-8",
        )
        return dates
    except Exception:
        return set(FALLBACK_HOLIDAYS)


def is_nse_holiday(day: date | None = None) -> bool:
    day = day or date.today()
    return day.isoformat() in get_holiday_dates()


def ist_now() -> datetime:
    return datetime.now(IST)


def ist_minutes() -> int:
    n = ist_now()
    return n.hour * 60 + n.minute


def is_morning_window() -> bool:
    """8:25 AM – 10:30 AM IST — ideal morning delivery time."""
    m = ist_minutes()
    return (8 * 60 + 25) <= m <= (10 * 60 + 30)


def is_github_morning_catchup() -> bool:
    """8:25 AM – 3:35 PM IST — send morning if GitHub was late (laptop OFF ok)."""
    m = ist_minutes()
    return (8 * 60 + 25) <= m <= (15 * 60 + 35)


def is_evening_blocked() -> bool:
    """After market close — never send morning briefing."""
    return ist_minutes() > (15 * 60 + 35)


def is_intraday_window() -> bool:
    """9:10 AM – 3:35 PM IST — SELL/AVERAGE checks only."""
    m = ist_minutes()
    return (9 * 60 + 10) <= m <= (15 * 60 + 35)


def get_market_context() -> dict:
    """IST clock + session status for UI analysis context."""
    now = ist_now()
    m = ist_minutes()
    trading_day = is_trading_day(now.date())

    if not trading_day:
        status = "HOLIDAY"
        hint = "No NSE session today — last trade day data shown"
    elif m < (9 * 60 + 15):
        status = "PRE_OPEN"
        hint = "Pre-market · NSE opens 9:15 AM IST"
    elif m <= (15 * 60 + 30):
        status = "OPEN"
        hint = "Market open · live NSE prices"
    else:
        status = "CLOSED"
        hint = "Market closed · today's final OHLC (till 3:30 PM)"

    return {
        "now_ist": now.strftime("%d %b %Y, %I:%M %p IST"),
        "today_ist": now.strftime("%Y-%m-%d"),
        "today_label": now.strftime("%a, %d %b %Y"),
        "market_status": status,
        "market_open": status == "OPEN",
        "trading_day": trading_day,
        "session_hint": hint,
        "evening_scan_at": "3:45 PM IST",
        "market_hours": "9:15 AM – 3:30 PM IST",
    }


def morning_already_sent_today() -> bool:
    today = date.today().isoformat()
    if not MORNING_SENT_FILE.exists():
        return False
    return MORNING_SENT_FILE.read_text(encoding="utf-8").strip() == today


def mark_morning_sent() -> None:
    MORNING_SENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    MORNING_SENT_FILE.write_text(date.today().isoformat(), encoding="utf-8")


def is_manual_run() -> bool:
    import os
    return os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"


def should_run_morning_job() -> bool:
    """Run morning scan once per day — Oracle exact time, GitHub catch-up if late."""
    import os

    from pa_config import CLOUD_PROVIDER, CLOUD_ROLE

    if not is_trading_day():
        return False
    if morning_already_sent_today():
        return False
    if is_evening_blocked():
        return False
    if is_manual_run() and os.environ.get("FORCE_RUN", "").lower() in ("1", "true", "yes"):
        return True
    if CLOUD_PROVIDER == "oracle" and CLOUD_ROLE == "primary":
        return is_morning_window()
    # GitHub free tier often runs late — allow until market close if not sent yet
    return is_github_morning_catchup()


def should_send_morning_telegram() -> bool:
    """Send morning once; block evening spam after 3:35 PM IST."""
    import os

    from pa_config import CLOUD_PROVIDER, CLOUD_ROLE

    if os.environ.get("FORCE_MORNING") == "1":
        return True
    if morning_already_sent_today():
        return False
    if is_evening_blocked():
        return False
    if is_manual_run() and os.environ.get("FORCE_RUN", "").lower() in ("1", "true", "yes"):
        return True
    if CLOUD_PROVIDER == "oracle" and CLOUD_ROLE == "primary":
        return is_morning_window()
    return is_github_morning_catchup()


def detect_job_mode() -> str:
    """Use real IST clock — not GitHub schedule label (fixes delayed evening runs)."""
    import os

    forced = os.environ.get("JOB_MODE", "auto").lower()
    if forced == "commands_only":
        return "commands_only"

    if ist_now().weekday() >= 5:
        return "commands_only"

    if forced == "morning":
        return "morning" if should_run_morning_job() or is_manual_run() else "commands_only"
    if forced == "intraday":
        return "intraday" if is_intraday_window() else "commands_only"

    if should_run_morning_job():
        return "morning"
    if is_intraday_window():
        return "intraday"
    return "commands_only"


def is_trading_day(day: date | None = None, *, force: bool = False) -> bool:
    """Weekday and not an NSE holiday."""
    import os

    if force:
        return True
    if os.environ.get("FORCE_RUN", "").lower() in ("1", "true", "yes"):
        return True
    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        return True

    today = day or date.today()
    if today.weekday() >= 5:
        return False
    if is_nse_holiday(today):
        return False
    return True