#!/usr/bin/env python3
"""Push EMAIL_* from secrets.env to GitHub Secrets and Render environment."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REPO = "binaykumarjaiswal-ved/vedant-swing"
SERVICE_NAME = "vedant-swing-web"


def main() -> int:
    from pa_config import EMAIL_APP_PASSWORD, EMAIL_FROM, EMAIL_TO

    if not all([EMAIL_FROM, EMAIL_TO, EMAIL_APP_PASSWORD]):
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "Fill secrets.env first (see SETUP_GMAIL_ALERTS.txt)",
                    "need": ["EMAIL_FROM", "EMAIL_TO", "EMAIL_APP_PASSWORD"],
                }
            )
        )
        return 1

    secrets = {
        "EMAIL_ENABLED": "true",
        "EMAIL_FROM": EMAIL_FROM,
        "EMAIL_TO": EMAIL_TO,
        "EMAIL_APP_PASSWORD": EMAIL_APP_PASSWORD,
    }

    for key, value in secrets.items():
        subprocess.run(
            ["gh", "secret", "set", key, "-R", REPO, "-b", value],
            check=True,
            timeout=30,
        )

    from auto_deploy_render import _api_key, _headers, find_service, set_env_vars

    api_key = _api_key()
    if not api_key:
        print(
            json.dumps(
                {
                    "ok": True,
                    "github": True,
                    "render": False,
                    "message": "GitHub secrets set. Add RENDER_API_KEY to update Render env.",
                }
            )
        )
        return 0

    import requests

    svc = find_service(api_key)
    if not svc:
        print(json.dumps({"ok": False, "error": f"Render service {SERVICE_NAME} not found"}))
        return 1

    set_env_vars(api_key, svc["id"], secrets)
    print(json.dumps({"ok": True, "github": True, "render": True, "service_id": svc["id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())