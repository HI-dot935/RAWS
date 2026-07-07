@echo off
REM RAWS - Read-only OSINT Workstation
REM One-command local launcher for Windows: creates a venv (if missing),
REM installs requirements, and starts the app on localhost.

cd /d "%~dp0backend"

if not defined PORT set PORT=8420
set HOST=127.0.0.1

if not exist venv (
  echo [RAWS] Creating virtual environment...
  python -m venv venv
)

call venv\Scripts\activate.bat

echo [RAWS] Installing/upgrading requirements...
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if not exist data mkdir data

echo [RAWS] Starting server...
echo [RAWS] Open http://%HOST%:%PORT% in your browser.
echo [RAWS] Press Ctrl+C to stop.

set OSINT_DB_PATH=./data/cases.db
uvicorn app.main:app --host %HOST% --port %PORT%
