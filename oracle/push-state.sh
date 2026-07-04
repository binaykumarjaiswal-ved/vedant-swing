#!/bin/bash
# Save position + heartbeat to GitHub (so backup knows Oracle is alive)
set -euo pipefail

APP_DIR="${STOCK_ANALYST_DIR:-$HOME/stock-analyst}"
cd "$APP_DIR"

if [[ ! -d .git ]]; then
  echo "[push-state] Not a git repo — skip"
  exit 0
fi

git config user.name "stock-analyst-oracle"
git config user.email "oracle@stock-analyst.local"

git add data/ 2>/dev/null || true
if git diff --staged --quiet; then
  echo "[push-state] No changes"
  exit 0
fi

git commit -m "oracle state: $(date -u +%Y-%m-%d-%H:%M UTC)"
git push origin main