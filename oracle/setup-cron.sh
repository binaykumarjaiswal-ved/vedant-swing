#!/bin/bash
# Install cron — every 10 min Mon-Fri (UTC times, covers IST market hours)
set -euo pipefail

APP_DIR="${STOCK_ANALYST_DIR:-$HOME/stock-analyst}"
JOB="cd $APP_DIR && source .venv/bin/activate && bash oracle/run-job.sh >> $APP_DIR/data/cron.log 2>&1"

CRON_BLOCK="# Stock Analyst Oracle PRIMARY — Mon-Fri every 10 min (UTC)
*/10 3-10 * * 1-5 $JOB"

EXISTING=$(crontab -l 2>/dev/null || true)
if echo "$EXISTING" | grep -q "Stock Analyst Oracle"; then
  echo "Cron already installed."
  crontab -l | grep "Stock Analyst"
  exit 0
fi

{
  echo "$EXISTING"
  echo ""
  echo "$CRON_BLOCK"
} | crontab -

echo "Cron installed:"
crontab -l | grep -A1 "Stock Analyst"