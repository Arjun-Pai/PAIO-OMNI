@echo off
REM Build PAIO-Omni.exe on Windows. Run this once, on Windows, after
REM installing requirements.txt. PyInstaller can't cross-compile, so this
REM must be run on the OS you're building for.

echo Installing build dependency (PyInstaller) ...
pip install -q pyinstaller

echo Building PAIO-Omni.exe ...
pyinstaller --noconfirm --clean PAIO-Omni.spec

echo.
echo Done. Find it at dist\PAIO-Omni\PAIO-Omni.exe
echo Copy your real .env (from .env.example) into dist\PAIO-Omni\ before running it.
pause
