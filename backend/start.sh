#!/usr/bin/env bash
# One-command setup + run for the Disaster Intelligence API.
#
# Usage:
#   ./start.sh
#
# What it does:
#   1. Creates a virtual environment (venv/) if it doesn't exist yet.
#   2. Activates it.
#   3. Installs dependencies (only if not already installed).
#   4. Starts the API with auto-reload at http://127.0.0.1:8000
#
# Safe to re-run any time — it skips steps that are already done.

set -e

cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
# shellcheck disable=SC1091
source venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

echo ""
echo "Starting server..."
echo "  API:        http://127.0.0.1:8000"
echo "  Docs (UI):  http://127.0.0.1:8000/docs"
echo "  Press Ctrl+C to stop."
echo ""

uvicorn app.main:app --reload
