#!/usr/bin/env python3
"""Deploy Vedant Swing to Render.com (free tier)."""

from __future__ import annotations

import json
import os
import subprocess
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
    for path in (
        Path(__file__).parent / "render-api-key.txt",
        Path(__file__).parent.parent / "10-Stock-Analyst" / "render-api-key.txt",
    ):
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return ""


def _gh_token() -> str:
    try:
        return subprocess.check_output(["gh", "auth", "token"], text=True, timeout=15).strip()
    except Exception:
        return os.environ.get("GITHUB_TOKEN", "").strip()


def _headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "Accept": "application/json", "Content-Type": "application/json"}


def find_service(api_key: str) -> dict | None:
    r = requests.get(f"{RENDER_API}/services", headers=_headers(api_key), timeout=30)
    r.raise_for_status()
    for item in r.json():
        svc = item.get("service", {})
        if svc.get("name") == SERVICE_NAME:
            return svc
    return None


def create_service(api_key: str, owner_id: str) -> dict:
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
            "healthCheckPath": "/api/health",
            "envSpecificDetails": {
                "buildCommand": "pip install -r requirements.txt",
                "startCommand": "gunicorn webapp.app:app --bind 0.0.0.0:$PORT --timeout 900 --workers 1 --threads 2",
            },
        },
    }
    r = requests.post(f"{RENDER_API}/services", headers=_headers(api_key), json=payload, timeout=60)
    if r.status_code == 409:
        return find_service(api_key) or {}
    if r.status_code >= 400:
        print("Render error:", r.text[:500])
        r.raise_for_status()
    return r.json().get("service", r.json())


def set_env_vars(api_key: str, service_id: str, env: dict) -> None:
    items = [{"key": k, "value": v} for k, v in env.items() if v is not None]
    requests.put(
        f"{RENDER_API}/services/{service_id}/env-vars",
        headers=_headers(api_key),
        json=items,
        timeout=30,
    ).raise_for_status()


def trigger_deploy(api_key: str, service_id: str) -> None:
    requests.post(f"{RENDER_API}/services/{service_id}/deploys", headers=_headers(api_key), json={}, timeout=30)


def main() -> int:
    api_key = _api_key()
    if not api_key:
        print("No RENDER_API_KEY. Use Render Dashboard → Blueprint →", REPO)
        return 1

    gh = _gh_token()
    owners = requests.get(f"{RENDER_API}/owners", headers=_headers(api_key), timeout=30).json()
    owner_id = owners[0]["owner"]["id"]

    svc = find_service(api_key) or create_service(api_key, owner_id)
    service_id = svc["id"]
    url = svc.get("serviceDetails", {}).get("url") or f"https://{SERVICE_NAME}.onrender.com"

    from pa_config import EMAIL_APP_PASSWORD, EMAIL_ENABLED, EMAIL_FROM, EMAIL_TO

    env = {
        "GITHUB_REPO": REPO,
        "GITHUB_TOKEN": gh,
        "AI_ENABLED": "false",
        "PYTHON_VERSION": "3.11.9",
        "STOCK_SCAN_LIMIT": "500",
        "EMAIL_ENABLED": "true" if EMAIL_ENABLED else "false",
    }
    if EMAIL_FROM:
        env["EMAIL_FROM"] = EMAIL_FROM
    if EMAIL_TO:
        env["EMAIL_TO"] = EMAIL_TO
    if EMAIL_APP_PASSWORD:
        env["EMAIL_APP_PASSWORD"] = EMAIL_APP_PASSWORD
    set_env_vars(api_key, service_id, env)

    try:
        trigger_deploy(api_key, service_id)
    except Exception:
        pass

    subprocess.run(
        ["gh", "secret", "set", "WEBAPP_URL", "-R", REPO, "-b", url.rstrip("/")],
        capture_output=True, text=True, timeout=30,
    )

    print(json.dumps({"ok": True, "url": url, "service_id": service_id}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())