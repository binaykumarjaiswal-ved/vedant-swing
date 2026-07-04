#!/usr/bin/env python3
"""Deploy Vedant Swing web app to Render.com (free tier)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

REPO = "binaykumarjaiswal-ved/vedant-swing"
SERVICE_NAME = "vedant-swing-web"
RENDER_API = "https://api.render.com/v1"


def _api_key() -> str:
    key = os.environ.get("RENDER_API_KEY", "").strip()
    if key:
        return key
    f = Path(__file__).parent / "render-api-key.txt"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    return ""


def _headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "Accept": "application/json", "Content-Type": "application/json"}


def main() -> int:
    key = _api_key()
    if not key:
        print("Set RENDER_API_KEY env or create render-api-key.txt locally (never commit).")
        print("Or use Render Dashboard → New → Blueprint → connect", REPO)
        return 1

    gh = os.environ.get("GITHUB_TOKEN", "")
    if not gh:
        import subprocess
        try:
            gh = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
        except Exception:
            pass

    owners = requests.get(f"{RENDER_API}/owners", headers=_headers(key), timeout=30).json()
    owner_id = owners[0]["owner"]["id"]

    payload = {
        "type": "web_service",
        "name": SERVICE_NAME,
        "ownerId": owner_id,
        "repo": f"https://github.com/{REPO}",
        "branch": "master",
        "autoDeploy": "yes",
        "serviceDetails": {
            "env": "python",
            "plan": "free",
            "region": "singapore",
            "buildCommand": "pip install -r requirements.txt",
            "startCommand": "gunicorn webapp.app:app --bind 0.0.0.0:$PORT --timeout 900 --workers 1 --threads 2",
            "healthCheckPath": "/api/health",
            "envVars": [
                {"key": "PYTHON_VERSION", "value": "3.11.9"},
                {"key": "GITHUB_REPO", "value": REPO},
                {"key": "GITHUB_TOKEN", "value": gh},
                {"key": "AI_ENABLED", "value": "false"},
                {"key": "STOCK_SCAN_LIMIT", "value": "500"},
            ],
        },
    }

    r = requests.post(f"{RENDER_API}/services", headers=_headers(key), json=payload, timeout=60)
    if r.status_code not in (200, 201):
        print("Render API:", r.status_code, r.text[:500])
        return 1
    svc = r.json().get("service") or r.json()
    print(json.dumps({"ok": True, "name": svc.get("name"), "url": f"https://{SERVICE_NAME}.onrender.com"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())