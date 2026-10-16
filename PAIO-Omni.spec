@echo off
setlocal enabledelayedexpansion

REM Build PAIO-Omni on Windows.
REM Run this script from the repository root.

echo.
echo ==========================================
echo PAIO-Omni Windows Build
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found.
    echo Install Python 3.10 or newer and try again.
    exit /b 1
)

echo Installing build dependency...
python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo ERROR: Could not install PyInstaller.
    exit /b 1
)

if not exist "models\piper" (
    echo WARNING: models\piper does not exist.
    echo The executable will be built without Piper assets.
    echo Install Piper before building if voice output should be bundled.
) else (
    if not exist "models\piper\piper.exe" (
        echo WARNING: models\piper\piper.exe was not found.
    )

    if not exist "models\piper\en_US-bryce-medium.onnx" (
        echo WARNING: Piper voice model was not found.
    )

    if not exist "models\piper\en_US-bryce-medium.onnx.json" (
        echo WARNING: Piper voice configuration was not found.
    )
)

echo.
echo Building PAIO-Omni...
python -m PyInstaller --noconfirm --clean PAIO-Omni.spec

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed.
    exit /b 1
)

echo.
echo ==========================================
echo Build complete
echo ==========================================
echo Output:
echo dist\PAIO-Omni\PAIO-Omni.exe
echo.

if exist ".env" (
    echo Copying .env into the distribution directory...
    copy /Y ".env" "dist\PAIO-Omni\.env" >nul
) else (
    echo No .env file found. Cloud providers will need configuration later.
)

echo.
echo Piper files, if present, were included from:
echo models\piper\
echo.

endlocal
pause
