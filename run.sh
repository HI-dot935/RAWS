#!/usr/bin/env bash
# RAWS - Read-only OSINT Workstation
# One-command local launcher: creates a venv (if missing), installs
# requirements, and starts the app on localhost.
set -euo pipefail

cd "$(dirname "$0")/backend"

PORT="${PORT:-8420}"
HOST="127.0.0.1"

if [ ! -d "venv" ]; then
  echo "[RAWS] Creating virtual environment..."
  python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate

echo "[RAWS] Installing/upgrading requirements..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

mkdir -p data

echo "[RAWS] Starting server..."
echo "[RAWS] Open http://${HOST}:${PORT} in your browser."
echo "[RAWS] Press Ctrl+C to stop."

OSINT_DB_PATH="./data/cases.db" exec uvicorn app.main:app --host "${HOST}" --port "${PORT}"
