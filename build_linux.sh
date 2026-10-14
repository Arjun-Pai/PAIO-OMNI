#!/bin/bash
# Build the PAIO-Omni binary on Linux. Run this once, on Linux, after
# installing requirements.txt. PyInstaller can't cross-compile, so this
# must be run on the OS you're building for.

set -e

echo "Installing build dependency (PyInstaller) ..."
pip install -q pyinstaller

echo "Building PAIO-Omni ..."
pyinstaller --noconfirm --clean PAIO-Omni.spec

echo ""
echo "Done. Find it at dist/PAIO-Omni/PAIO-Omni"
echo "Copy your real .env (from .env.example) into dist/PAIO-Omni/ before running it."
echo ""
echo "Note: the tray icon needs a system tray host (most desktop"
echo "environments have one; some minimal window managers don't)."
