"""Sync position + reports from GitHub repo (private cloud data)."""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = DATA_DIR / "reports"

GITHUB_REPO = os.environ.get("GITHUB_REPO", "binaykumarjaiswal-ved/vedant-swing").strip()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
CACHE_SEC = int(os.environ.get("SYNC_CACHE_SEC", "90"))

_last_pull = 0.0


def _enabled() -> bool:
    return bool(GITHUB_REPO and GITHUB_TOKEN)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_file(path: str) -> tuple[str | None, str | None]:
    """Return (content, sha) or (None, None)."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    try:
        r = requests.get(url, headers=_headers(), timeout=30)
        if r.status_code != 200:
            return None, None
        data = r.json()
        raw = base64.b64decode(data["content"]).decode("utf-8")
        return raw, data.get("sha")
    except Exception:
        return None, None


def _put_file(path: str, content: str, message: str) -> bool:
    _, sha = _get_file(path)
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    body = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
    }
    if sha:
        body["sha"] = sha
    try:
        r = requests.put(url, headers=_headers(), json=body, timeout=30)
        return r.status_code in (200, 201)
    except Exception:
        return False


def pull_state(force: bool = False) -> bool:
    """Download latest position + reports from GitHub."""
    global _last_pull
    if not _enabled():
        return False
    now = time.time()
    if not force and now - _last_pull < CACHE_SEC:
        return True

    ok = False
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    pos_text, _ = _get_file("data/position.json")
    if pos_text:
        (DATA_DIR / "position.json").write_text(pos_text, encoding="utf-8")
        ok = True

    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data/reports"
        r = requests.get(url, headers=_headers(), timeout=30)
        if r.status_code == 200:
            for item in r.json():
                if item.get("type") != "file":
                    continue
                name = item.get("name", "")
                if not name.endswith(".txt"):
                    continue
                text, _ = _get_file(f"data/reports/{name}")
                if text:
                    (REPORTS_DIR / name).write_text(text, encoding="utf-8")
                    ok = True
    except Exception:
        pass

    _last_pull = now
    return ok


def push_report_files(date_str: str) -> bool:
    """Upload morning report txt to GitHub data/reports/."""
    if not _enabled():
        return False
    ok = False
    for name in (f"morning_research_{date_str}.txt", f"signal_{date_str}.txt"):
        local = REPORTS_DIR / name
        if not local.exists():
            alt = BASE_DIR / "reports" / name
            if alt.exists():
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_text(alt.read_text(encoding="utf-8"), encoding="utf-8")
        if local.exists():
            text = local.read_text(encoding="utf-8")
            if _put_file(f"data/reports/{name}", text, f"render-web: morning report {date_str}"):
                ok = True
    if ok:
        global _last_pull
        _last_pull = 0.0
    return ok


def push_position(content: str) -> bool:
    """Upload position.json back to GitHub after user confirms trade."""
    if not _enabled():
        return False
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "position.json").write_text(content, encoding="utf-8")
    ok = _put_file(
        "data/position.json",
        content,
        f"webapp: position update {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}",
    )
    if ok:
        global _last_pull
        _last_pull = time.time()
    return ok