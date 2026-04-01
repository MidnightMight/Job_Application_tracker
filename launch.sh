#!/usr/bin/env bash
# launch.sh — One-command launcher for Job Application Tracker (Linux / macOS)
# Usage: bash launch.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/venv"

# ── Create virtual environment if it doesn't exist ──────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "[launcher] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# ── Activate the virtual environment ────────────────────────────────────────
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ── Install / upgrade dependencies ──────────────────────────────────────────
echo "[launcher] Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# ── Launch the server ────────────────────────────────────────────────────────
echo "[launcher] Starting Job Tracker at http://localhost:5000"
python app.py
