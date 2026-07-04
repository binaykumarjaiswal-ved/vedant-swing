#!/bin/bash
# Oracle VM — primary job runner (called by cron every 10 min)
set -euo pipefail

APP_DIR="${STOCK_ANALYST_DIR:-$HOME/stock-analyst}"
cd "$APP_DIR"

if [[ -f secrets.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source secrets.env
  set +a
fi

export CLOUD_ROLE=primary
export STOCK_SCAN_LIMIT="${STOCK_SCAN_LIMIT:-50}"
export CHECK_INTERVAL_MIN="${CHECK_INTERVAL_MIN:-10}"
export JOB_MODE=auto

# Pull latest state (position.json, heartbeat) from GitHub
if [[ -d .git ]]; then
  git pull --rebase origin main 2>/dev/null || git pull origin main 2>/dev/null || true
fi

PYTHON="${APP_DIR}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON=python3
"$PYTHON" run_loop.py
bash oracle/push-state.sh