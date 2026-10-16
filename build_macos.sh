#!/usr/bin/env bash

set -euo pipefail

echo
echo "=========================================="
echo "PAIO-Omni macOS Build"
echo "=========================================="
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 was not found."
    exit 1
fi

echo "Installing build dependency..."
python3 -m pip install --upgrade pyinstaller

if [[ -d "models/piper" ]]; then
    echo "Checking Piper assets..."

    if [[ ! -f "models/piper/piper" ]]; then
        echo "WARNING: models/piper/piper was not found."
    else
        chmod +x "models/piper/piper"
    fi

    if [[ ! -f "models/piper/en_US-bryce-medium.onnx" ]]; then
        echo "WARNING: Piper voice model was not found."
    fi

    if [[ ! -f "models/piper/en_US-bryce-medium.onnx.json" ]]; then
        echo "WARNING: Piper voice configuration was not found."
    fi
else
    echo "WARNING: models/piper does not exist."
    echo "The executable will be built without Piper assets."
fi

echo
echo "Building PAIO-Omni..."
python3 -m PyInstaller --noconfirm --clean PAIO-Omni.spec

echo
echo "=========================================="
echo "Build complete"
echo "=========================================="
echo "Output:"
echo "dist/PAIO-Omni/PAIO-Omni"
echo

if [[ -f ".env" ]]; then
    echo "Copying .env into the distribution directory..."
    cp ".env" "dist/PAIO-Omni/.env"
else
    echo "No .env file found."
fi

echo
echo "The first launch may be blocked by macOS Gatekeeper."
echo "Right-click the executable and select Open if necessary."
echo
echo "Alternatively, run:"
echo "xattr -d com.apple.quarantine dist/PAIO-Omni/PAIO-Omni"
