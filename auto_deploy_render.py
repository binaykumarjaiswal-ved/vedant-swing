#!/usr/bin/env python3
"""Auto-deploy Stock Analyst web app to Render.com (free)."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import requests

DATA_REPO = "binaykumarjaiswal-ved/stock-analyst-cloud"
DEPLOY_REPO = "binaykumarjaiswal-ved/stock-analyst-web"
DEPLOY_BRANCH = "master"
SERVICE_NAME = "stock-analyst-web"
RENDER_API = "https://api.render.com/v1"


def _load_groq_key() -> str:
    ai_tools = Path(r"D:\BINAY-Projects\01-GLM-AI-Tools\get-api-key.ps1")
    if not ai_tools.exists():
        return os.environ.get("GROQ_API_KEY", "")
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ai_tools), "-Provider", "groq"],
            capture_output=True, text=True, timeout=30,
        )
        key = (r.stdout or "").strip()
        return key if key.startswith("gsk_") else os.environ.get("GROQ_API_KEY", "")
    except Exception:
        return os.environ.get("GROQ_API_KEY", "")


def _gh_token() -> str:
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=15)
        return (r.stdout or "").strip()
    except Exception:
        return os.environ.get("GITHUB_TOKEN", "")


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def get_owner_id(api_key: str) -> str:
    r = requests.get(f"{RENDER_API}/owners", headers=_headers(api_key), timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise RuntimeError("No Render workspace found")
    return data[0]["owner"]["id"]


def find_service(api_key: str) -> dict | None:
    r = requests.get(
        f"{RENDER_API}/services",
        headers=_headers(api_key),
        params={"name": SERVICE_NAME},
        timeout=30,
    )
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
        "repo": f"https://github.com/{DEPLOY_REPO}",
        "branch": DEPLOY_BRANCH,
        "autoDeploy": "yes",
        "serviceDetails": {
            "env": "python",
            "plan": "free",
            "region": "oregon",
            "envSpecificDetails": {
                "buildCommand": "pip install -r requirements.txt",
                "startCommand": "gunicorn webapp.app:app --bind 0.0.0.0:$PORT --timeout 900 --workers 1 --threads 2",
            },
            "healthCheckPath": "/api/health",
        },
    }
    r = requests.post(f"{RENDER_API}/services", headers=_headers(api_key), json=payload, timeout=60)
    if r.status_code == 409:
        return find_service(api_key) or {}
    if r.status_code >= 400:
        print(f"  Render error: {r.text[:500]}")
    r.raise_for_status()
    return r.json().get("service", r.json())


def set_env_vars(api_key: str, service_id: str, env: dict) -> None:
    items = [{"key": k, "value": v} for k, v in env.items() if v]
    r = requests.put(
        f"{RENDER_API}/services/{service_id}/env-vars",
        headers=_headers(api_key),
        json=items,
        timeout=30,
    )
    r.raise_for_status()


def trigger_deploy(api_key: str, service_id: str) -> None:
    requests.post(f"{RENDER_API}/services/{service_id}/deploys", headers=_headers(api_key), json={}, timeout=30)


def set_github_webapp_secret(url: str) -> None:
    if not url:
        return
    subprocess.run(
        ["gh", "secret", "set", "WEBAPP_URL", "-R", DATA_REPO, "-b", url.rstrip("/")],
        capture_output=True, text=True, timeout=30,
    )


def main() -> int:
    key_file = Path(__file__).parent.parent / "render-api-key.txt"
    api_key = os.environ.get("RENDER_API_KEY", "").strip()
    if not api_key and key_file.exists():
        api_key = key_file.read_text(encoding="utf-8").strip()
    if not api_key:
        print("ERROR: No Render API key.")
        print("  Save NEW key (one line rnd_...) to:")
        print(f"  {key_file}")
        print("  Then run: ROTATE_RENDER_KEY.bat")
        return 1

    gh = _gh_token()
    if not gh:
        print("ERROR: gh auth token missing — run: gh auth login")
        return 1

    groq = _load_groq_key()
    print("Connecting to Render API...")
    owner_id = get_owner_id(api_key)
    print(f"  Workspace OK: {owner_id[:8]}...")

    svc = find_service(api_key)
    if not svc:
        print("Creating web service (free plan)...")
        svc = create_service(api_key, owner_id)
    else:
        print(f"  Service exists: {svc.get('name')}")

    service_id = svc["id"]
    url = svc.get("serviceDetails", {}).get("url") or svc.get("url", "")
    if not url and "dashboardUrl" in svc:
        slug = svc.get("slug", SERVICE_NAME)
        url = f"https://{slug}.onrender.com"

    cron_secret = os.environ.get("CRON_SECRET", "").strip()
    if not cron_secret:
        cron_secret = secrets.token_urlsafe(24)

    print("Setting environment variables...")
    set_env_vars(api_key, service_id, {
        "GITHUB_REPO": DATA_REPO,
        "GITHUB_TOKEN": gh,
        "GROQ_API_KEY": groq,
        "AI_ENABLED": "true",
        "PYTHON_VERSION": "3.11.9",
        "STOCK_SCAN_LIMIT": "100",
        "CRON_SECRET": cron_secret,
    })

    subprocess.run(
        ["gh", "secret", "set", "CRON_SECRET", "-R", DATA_REPO, "-b", cron_secret],
        capture_output=True, text=True, timeout=30,
    )

    print("Triggering deploy...")
    try:
        trigger_deploy(api_key, service_id)
    except Exception:
        pass

    if url:
        print(f"\nWEBAPP_URL={url}")
        set_github_webapp_secret(url)
        print("Saved WEBAPP_URL to GitHub secrets (keep-awake workflow).")

    print("\nDONE — open on phone:")
    print(f"  {url}")
    print("Deploy takes 3-5 minutes on first run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())