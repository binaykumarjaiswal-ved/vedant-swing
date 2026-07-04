#!/usr/bin/env python3
"""Check price alerts — run from GitHub Actions or cron."""

from __future__ import annotations

import json

from alerts import check_alerts

if __name__ == "__main__":
    result = check_alerts()
    print(json.dumps(result))