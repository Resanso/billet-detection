#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# build.sh — Build BilletDetection on macOS / Linux
# Usage:  chmod +x build.sh && ./build.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

VENV_DIR="venv"

echo "==> Checking virtual environment …"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

echo "==> Installing / upgrading dependencies …"
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo "==> Cleaning previous build …"
rm -rf build/ dist/

echo "==> Running PyInstaller …"
pyinstaller app.spec

echo ""
echo "✅  Build complete!"
echo "    Output: dist/BilletDetection/"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "    macOS app: dist/BilletDetection.app"
fi
