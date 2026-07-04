#!/bin/bash
# Manual test — sends Telegram if configured
set -euo pipefail

APP_DIR="${STOCK_ANALYST_DIR:-$HOME/stock-analyst}"
cd "$APP_DIR"
source .venv/bin/activate
export CLOUD_ROLE=primary
export FORCE_RUN=true
export JOB_MODE=morning
python3 run_loop.py
echo "Check Telegram on phone."