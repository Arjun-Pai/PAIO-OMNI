#!/bin/bash
# Build the PAIO-Omni binary on macOS. Run this once, on a Mac, after
# installing requirements.txt. PyInstaller can't cross-compile, so this
# must be run on the OS you're building for — it can't be produced from
# Windows or Linux.

set -e

echo "Installing build dependency (PyInstaller) ..."
pip install -q pyinstaller

echo "Building PAIO-Omni ..."
pyinstaller --noconfirm --clean PAIO-Omni.spec

echo ""
echo "Done. Find it at dist/PAIO-Omni/PAIO-Omni"
echo "Copy your real .env (from .env.example) into dist/PAIO-Omni/ before running it."
echo ""
echo "Note: on first launch, macOS Gatekeeper will likely block an unsigned"
echo "binary. Right-click -> Open the first time, or run:"
echo "  xattr -d com.apple.quarantine dist/PAIO-Omni/PAIO-Omni"
