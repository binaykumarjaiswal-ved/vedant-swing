"""Morning scan on Render — no wait for late GitHub Actions queue."""

from __future__ import annotations

import json
import threading
from datetime import date, datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = DATA_DIR / "reports"
DONE_FILE = DATA_DIR / "web_morning_done.txt"
LOCK_FILE = DATA_DIR / "web_morning.lock"

_lock = threading.Lock()
_state = {
    "running": False,
    "last_error": "",
    "last_run": "",
    "source": "",
}


def _today() -> str:
    from market_calendar import ist_now

    return ist_now().date().isoformat()


def report_exists_for_today() -> bool:
    stamp = _today()
    for folder in (REPORTS_DIR, BASE_DIR / "reports"):
        if (folder / f"morning_research_{stamp}.txt").exists():
            return True
    return False


def web_morning_done_today() -> bool:
    if not DONE_FILE.exists():
        return False
    return DONE_FILE.read_text(encoding="utf-8").strip() == _today()


def mark_web_morning_done(source: str = "render") -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DONE_FILE.write_text(_today(), encoding="utf-8")
    _state["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M IST")
    _state["source"] = source


def should_run_web_morning() -> bool:
    from market_calendar import is_github_morning_catchup, is_trading_day

    if not is_trading_day():
        return False
    if report_exists_for_today():
        return False
    if web_morning_done_today():
        return False
    if not is_github_morning_catchup():
        return False
    return True


def get_scan_status() -> dict:
    return {
        "running": _state["running"],
        "today_ready": report_exists_for_today(),
        "last_error": _state.get("last_error", ""),
        "last_run": _state.get("last_run", ""),
        "source": _state.get("source", ""),
        "today": _today(),
    }


def _run_scan_sync() -> bool:
    """Full morning research on Render (8–12 min, 100 stocks + deep enrich)."""
    from run_cloud_job import get_benchmark, load_config, run_morning_research

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    benchmark = get_benchmark()
    run_morning_research(cfg, benchmark)

    stamp = _today()
    src = BASE_DIR / "reports" / f"morning_research_{stamp}.txt"
    dst = REPORTS_DIR / f"morning_research_{stamp}.txt"
    if src.exists() and not dst.exists():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    try:
        from cloud_sync import push_report_files
        push_report_files(stamp)
    except Exception:
        pass

    mark_web_morning_done("render")
    return True


def run_morning_if_needed(background: bool = True) -> dict:
    """
    Run today's morning scan on Render when GitHub is late.
    Returns status dict for API / dashboard.
    """
    if report_exists_for_today():
        return {**get_scan_status(), "started": False, "message": "Today's report ready"}

    if not should_run_web_morning():
        return {
            **get_scan_status(),
            "started": False,
            "message": "Outside morning window or not a trading day",
        }

    if _state["running"]:
        return {**get_scan_status(), "started": False, "message": "Scan already running"}

    def _worker():
        _state["running"] = True
        _state["last_error"] = ""
        try:
            _run_scan_sync()
        except Exception as exc:
            _state["last_error"] = str(exc)[:200]
        finally:
            _state["running"] = False

    if background:
        threading.Thread(target=_worker, daemon=True).start()
        return {**get_scan_status(), "started": True, "message": "Morning scan started on cloud"}

    try:
        _state["running"] = True
        _run_scan_sync()
        return {**get_scan_status(), "started": True, "message": "Morning scan complete"}
    except Exception as exc:
        _state["last_error"] = str(exc)[:200]
        return {**get_scan_status(), "started": False, "message": str(exc)}
    finally:
        _state["running"] = False


def run_morning_force() -> dict:
    """Force scan (e.g. cron ping) — skip done check but not if already running."""
    from market_calendar import is_trading_day

    if not is_trading_day():
        return {**get_scan_status(), "started": False, "message": "Not a trading day"}

    if report_exists_for_today():
        return {**get_scan_status(), "started": False, "message": "Already have today's report"}

    return run_morning_if_needed(background=False)


def run_morning_manual(force: bool = False, background: bool = True) -> dict:
    """User-triggered morning scan from app UI."""
    from market_calendar import get_market_context, is_trading_day

    if _state["running"]:
        return {**get_scan_status(), "started": False, "message": "Morning scan already running"}

    if not force and not is_trading_day():
        ctx = get_market_context()
        return {
            **get_scan_status(),
            "started": False,
            "message": f"No NSE session today ({ctx.get('today_label')}). Wait for next trading day or tap Force run.",
        }

    if not force and report_exists_for_today():
        return {**get_scan_status(), "started": False, "message": "Today's morning report is already ready"}

    if force:
        if DONE_FILE.exists():
            try:
                DONE_FILE.unlink()
            except OSError:
                pass

    def _worker():
        _state["running"] = True
        _state["last_error"] = ""
        try:
            _run_scan_sync()
        except Exception as exc:
            _state["last_error"] = str(exc)[:200]
        finally:
            _state["running"] = False

    if background:
        threading.Thread(target=_worker, daemon=True).start()
        return {**get_scan_status(), "started": True, "message": "Morning scan started (8–12 min)"}

    try:
        _state["running"] = True
        _run_scan_sync()
        return {**get_scan_status(), "started": True, "message": "Morning scan complete"}
    except Exception as exc:
        _state["last_error"] = str(exc)[:200]
        return {**get_scan_status(), "started": False, "message": str(exc)}
    finally:
        _state["running"] = False