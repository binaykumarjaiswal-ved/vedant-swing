#!/usr/bin/env bash
# Vedant Swing — Google Cloud Shell bootstrap (no secrets in repo)
set -euo pipefail

REPO="${VEDANT_SWING_REPO:-binaykumarjaiswal-ved/vedant-swing}"
WORKDIR="${HOME}/vedant-swing"

echo "==> Vedant Swing cloud bootstrap"
if [ ! -d "$WORKDIR/.git" ]; then
  git clone "https://github.com/${REPO}.git" "$WORKDIR"
fi

cd "$WORKDIR"
git pull --ff-only || true
python3 -m pip install -q -r requirements.txt

echo "==> Ready. Commands:"
echo "  cd $WORKDIR && python evening_scan.py"
echo "  cd $WORKDIR && python -m webapp.app"
echo "==> Open Cloud Shell Editor or connect VS Code to this folder."