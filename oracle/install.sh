#!/bin/bash
# One-time Oracle VM setup — Ubuntu 22.04/24.04
set -euo pipefail

APP_DIR="${1:-$HOME/stock-analyst}"
REPO_URL="${2:-}"

echo "=============================================="
echo " Stock Analyst — Oracle Cloud Install"
echo " App dir: $APP_DIR"
echo "=============================================="

sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv git curl

mkdir -p "$APP_DIR"
cd "$APP_DIR"

if [[ -n "$REPO_URL" && ! -d .git ]]; then
  git clone "$REPO_URL" "$APP_DIR"
fi

if [[ ! -f requirements.txt ]]; then
  echo "ERROR: requirements.txt not found in $APP_DIR"
  echo "Clone repo first: git clone https://github.com/YOURUSER/stock-analyst-cloud.git $APP_DIR"
  exit 1
fi

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

chmod +x oracle/run-job.sh oracle/push-state.sh

if [[ ! -f secrets.env ]]; then
  cp secrets.example.env secrets.env
  echo ""
  echo "IMPORTANT: Edit secrets.env now:"
  echo "  nano $APP_DIR/secrets.env"
  echo "  Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"
  echo ""
fi

echo ""
echo "Test run:"
echo "  cd $APP_DIR && source .venv/bin/activate && bash oracle/run-job.sh"
echo ""
echo "Install cron:"
echo "  bash oracle/setup-cron.sh"
echo ""