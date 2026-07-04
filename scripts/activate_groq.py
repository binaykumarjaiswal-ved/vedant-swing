#!/usr/bin/env python3
"""Read Groq key from local notepad file, encrypt it, activate AI on Render."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REPO = "binaykumarjaiswal-ved/vedant-swing"
PASTE_FILE = ROOT / "local-secrets" / "groq-key-PASTE-HERE.txt"
ALT_FILE = ROOT / "local-secrets" / "groq-key.txt"
LIVE_URL = "https://vedant-swing-web.onrender.com"

INSTRUCTIONS = """================================================================================
  KEY ACTIVATED — paste again here only if you need to change the key
================================================================================

Paste a new Groq key on the line below, save, then run ACTIVATE-GROQ.bat

PASTE_YOUR_KEY_ON_THE_LINE_BELOW


================================================================================
"""


def _extract_key(text: str) -> str:
    skip = re.compile(
        r"^(=|step|paste|get key|vedant|groq|api|never|delete|save|double|the script|encrypt|push|test|https?://)",
        re.I,
    )
    for line in text.splitlines():
        line = line.strip().strip('"').strip("'")
        if not line or line.startswith("#") or skip.search(line):
            continue
        if line.startswith("gsk_") or (len(line) >= 32 and " " not in line):
            return line
    return ""


def _read_notepad_key() -> str:
    for path in (PASTE_FILE, ALT_FILE):
        if not path.exists():
            continue
        key = _extract_key(path.read_text(encoding="utf-8"))
        if key and key != "PASTE_YOUR_KEY_ON_THE_LINE_BELOW":
            return key
    return ""


def _try_glm_tools_key() -> str:
    ps1 = Path(r"D:\BINAY-Projects\01-GLM-AI-Tools\load-ai-keys.ps1")
    if not ps1.exists():
        return ""
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                f"& '{ps1}' | Out-Null; $env:GROQ_API_KEY",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(ps1.parent),
        )
        key = (result.stdout or "").strip().splitlines()[-1].strip() if result.stdout else ""
        return key if key.startswith("gsk_") else ""
    except Exception:
        return ""


def _clear_notepad(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(INSTRUCTIONS, encoding="utf-8")


def _push_render(groq_key: str) -> dict:
    from auto_deploy_render import _api_key, find_service, set_env_vars, trigger_deploy

    api_key = _api_key()
    if not api_key:
        return {"ok": False, "render": False, "error": "RENDER_API_KEY missing (10-Stock-Analyst/render-api-key.txt)"}

    svc = find_service(api_key)
    if not svc:
        return {"ok": False, "render": False, "error": "Render service not found"}

    import os

    import requests

    from auto_deploy_render import REPO, _gh_token

    gh = _gh_token()
    env = {
        "GITHUB_REPO": REPO,
        "GITHUB_TOKEN": gh,
        "AI_ENABLED": "true",
        "PYTHON_VERSION": "3.11.9",
        "STOCK_SCAN_LIMIT": "500",
        "GROQ_API_KEY": groq_key,
    }
    cron_file = ROOT / "cron-secret.txt"
    if cron_file.exists():
        env["CRON_SECRET"] = cron_file.read_text(encoding="utf-8").strip()

    set_env_vars(api_key, svc["id"], env)
    try:
        trigger_deploy(api_key, svc["id"])
    except Exception:
        pass
    return {"ok": True, "render": True, "service_id": svc["id"]}


def _push_github(groq_key: str) -> bool:
    try:
        subprocess.run(
            ["gh", "secret", "set", "GROQ_API_KEY", "-R", REPO, "-b", groq_key],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return True
    except Exception:
        return False


def _test_live_ai() -> dict:
    import time

    import requests

    time.sleep(8)
    try:
        r = requests.get(f"{LIVE_URL}/api/analyze/TITAN?ai=1", timeout=120)
        r.raise_for_status()
        data = r.json()
        note = data.get("ai_note") or ""
        return {
            "ok": bool(note),
            "signal": data.get("signal"),
            "ai_chars": len(note),
            "ai_status": data.get("ai_status", ""),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:120]}


def main() -> int:
    from secret_store import load_groq_key, save_secret

    groq_key = _read_notepad_key()
    source = "notepad"

    if not groq_key:
        groq_key = load_groq_key()
        source = "encrypted"

    if not groq_key:
        groq_key = _try_glm_tools_key()
        source = "glm-tools"

    if not groq_key:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "No Groq key found",
                    "steps": [
                        f"Open: {PASTE_FILE}",
                        "Paste your Groq API key on the blank line",
                        "Save file",
                        "Run ACTIVATE-GROQ.bat again",
                    ],
                },
                indent=2,
            )
        )
        return 1

    if not groq_key.startswith("gsk_"):
        print(json.dumps({"ok": False, "error": "Key should start with gsk_ (Groq format)"}))
        return 1

    save_secret("groq_api_key", groq_key)
    if PASTE_FILE.exists():
        _clear_notepad(PASTE_FILE)
    if ALT_FILE.exists():
        _clear_notepad(ALT_FILE)

    import os

    os.environ["GROQ_API_KEY"] = groq_key

    render_result = _push_render(groq_key)
    github_ok = _push_github(groq_key)
    test = _test_live_ai() if render_result.get("ok") else {"ok": False, "skipped": True}

    print(
        json.dumps(
            {
                "ok": True,
                "message": "Groq API activated — key encrypted on this PC and sent to Render",
                "source": source,
                "encrypted_file": "local-secrets/secrets.enc",
                "notepad_cleared": True,
                "render": render_result,
                "github_secret": github_ok,
                "live_test": test,
                "app_url": LIVE_URL,
            },
            indent=2,
        )
    )
    return 0 if render_result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())