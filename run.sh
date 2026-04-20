#!/usr/bin/env bash
# TA runner for the KDE Sentinel project.
#
# Usage:
#   ./run.sh cis-r1.pdf cis-r2.pdf
#
# This script:
#   1. Creates/activates a Python virtual environment named comp5700-venv
#   2. Installs everything in requirements.txt
#   3. Runs the full extract -> compare -> execute pipeline on the two PDFs
#
# Outputs land in ./outputs/.

set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <pdf1> <pdf2>" >&2
    exit 1
fi

PDF1="$1"
PDF2="$2"
VENV_DIR="comp5700-venv"

if [ ! -f "$PDF1" ]; then
    echo "Error: $PDF1 not found" >&2
    exit 1
fi
if [ ! -f "$PDF2" ]; then
    echo "Error: $PDF2 not found" >&2
    exit 1
fi

if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
else
    PYTHON=python
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "[setup] creating virtual environment in $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
else
    source "$VENV_DIR/Scripts/activate"
fi

echo "[setup] installing dependencies"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "[run] python main.py $PDF1 $PDF2"
python main.py "$PDF1" "$PDF2"
