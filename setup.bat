@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo.
echo ╔══════════════════════════════════════════════╗
echo ║       PAIO-Omni  -  Standalone Installer     ║
echo ║       Windows                                ║
echo ╚══════════════════════════════════════════════╝
echo.

:: ══════════════════════════════════════════════════════════
::  PRE-FLIGHT: PYTHON
:: ══════════════════════════════════════════════════════════
echo ──────────────────────────────────────────────────
echo   Checking Python...
echo ──────────────────────────────────────────────────

python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] Python not found.
    echo     Download from https://www.python.org/downloads/
    echo     Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do (
    set PYMAJ=%%a
    set PYMIN=%%b
)

if !PYMAJ! LSS 3 (
    echo [X] Python 3.9+ required. You have !PYVER!
    pause
    exit /b 1
)
if !PYMAJ! EQU 3 if !PYMIN! LSS 9 (
    echo [X] Python 3.9+ required. You have !PYVER!
    pause
    exit /b 1
)
echo   [+] Python !PYVER!

:: ══════════════════════════════════════════════════════════
::  PRE-FLIGHT: OLLAMA
:: ══════════════════════════════════════════════════════════
echo.
echo ──────────────────────────────────────────────────
echo   Checking Ollama...
echo ──────────────────────────────────────────────────

where ollama >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] Ollama not found.
    echo     Download: https://ollama.com/download/windows
    echo     Install Ollama, then re-run this script.
    pause
    exit /b 1
)
echo   [+] Ollama found

:: ══════════════════════════════════════════════════════════
::  PYTHON PACKAGES
:: ══════════════════════════════════════════════════════════
echo.
echo ──────────────────────────────────────────────────
echo   Installing Python packages...
echo   (This might take a moment, please wait)
echo ──────────────────────────────────────────────────

python -m pip install --upgrade ^
    faster-whisper ^
    sounddevice ^
    soundfile ^
    numpy ^
    requests ^
    psutil ^
    torch ^
    torchaudio

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ════════════════════════════════════════════════════
    echo [X] PIP INSTALL FAILED!
    echo     Scroll up to read the red error text above.
    echo ════════════════════════════════════════════════════
    pause
    exit /b 1
)
echo   [+] Python packages installed successfully

:: ══════════════════════════════════════════════════════════
::  HARDCODED MODEL TIERS
:: ══════════════════════════════════════════════════════════
set "MODELS_cpu_tiny=smollm2:135m qwen2.5:0.5b deepseek-r1:1.5b qwen2.5-coder:0.5b llama3.2:1b tinyllama:1.1b danube3:500m qwen:0.5b smollm2:360m qwen2.5:1.5b llama3.2:1b-instruct-q8_0 qwen2.5:0.5b-instruct-q8_0 qwen2.5-coder:1.5b"
set "MODELS_cpu_small=gemma2:2b qwen2.5:3b llama3.2:3b phi3.5:mini granite3-dense:2b starcoder2:3b stable-code:3b qwen2.5-coder:3b gemma2:2b-instruct-q8_0 llama3.2:3b-instruct-q8_0 qwen2.5:1.5b-instruct-q8_0 phi3:mini deepseek-r1:1.5b-q8_0"
set "MODELS_cpu_medium=llama3.1:8b qwen2.5:7b mistral:7b gemma2:9b deepseek-r1:7b deepseek-r1:8b qwen2.5-coder:7b llama3.1:8b-instruct-q4_0 qwen2.5:7b-instruct-q4_K_M mistral-nemo:12b qwen2-math:7b codegemma:7b aya:8b"
set "MODELS_cpu_large=qwen2.5:14b qwen2.5:32b deepseek-r1:14b deepseek-r1:32b phi3:medium gemma2:27b-instruct-q4_0 qwen2.5-coder:14b qwen2.5-coder:32b starcoder2:15b deepseek-coder-v2:16b mixtral:8x7b-instruct-v0.1-q4_0 command-r:35b yi:34b"
set "MODELS_cpu_mega=llama3.3:70b-instruct-q4_K_M qwen2.5:72b-instruct-q4_K_M deepseek-r1:70b-q4_K_M nemotron:70b-instruct-q4_K_M llama3.1:70b-instruct-q4_0 mixtral:8x22b-instruct-v0.1-q4_0 qwen2.5-coder:32b-instruct-q8_0 command-r-plus:104b-q4_0 dolphin-llama3:70b wizardlm2:8x22b-q4_0 qwen2-math:72b-instruct-q4_0 deepseek-v2:236b-chat-q2_K deepseek-coder-v2:236b-instruct-q2_K"

set "MODELS_gpu_tiny=qwen2.5:1.5b-instruct-fp16 llama3.2:1b-instruct-fp16 gemma2:2b-instruct-fp16 qwen2.5-coder:1.5b-instruct-fp16 deepseek-r1:1.5b-fp16 llama3.2:3b-instruct-q4_K_M qwen2.5:3b-instruct-q4_K_M qwen2.5-coder:3b-instruct-q4_K_M phi3.5:mini-instruct-fp16 smollm2:1.7b-instruct-fp16 granite3-dense:2b-instruct-fp16 stable-code:3b-fp16 qwen2.5:3b-instruct-q8_0"
set "MODELS_gpu_small=llama3.1:8b-instruct-q8_0 qwen2.5:7b-instruct-q8_0 gemma2:9b-instruct-q8_0 deepseek-r1:7b-q8_0 deepseek-r1:8b-q8_0 qwen2.5-coder:7b-instruct-q8_0 mistral:7b-instruct-q8_0 aya:8b-instruct-q8_0 llama3.1:8b-instruct-fp16 qwen2.5:7b-instruct-fp16 gemma2:9b-instruct-fp16 qwen2-math:7b-instruct-q8_0 codegemma:7b-instruct-q8_0"
set "MODELS_gpu_medium=qwen2.5:14b-instruct-q8_0 qwen2.5:32b-instruct-q4_K_M deepseek-r1:14b-q8_0 deepseek-r1:32b-q4_K_M gemma2:27b gemma2:27b-instruct-q8_0 qwen2.5-coder:14b-instruct-q8_0 qwen2.5-coder:32b-instruct-q4_K_M command-r:35b-v0.1-q8_0 mixtral:8x7b starcoder2:15b-instruct-q8_0 deepseek-coder-v2:16b-lite-instruct-q8_0 phi3:medium-128k-instruct-q8_0"
set "MODELS_gpu_large=llama3.3:70b qwen2.5:72b deepseek-r1:70b nemotron:70b qwen2.5:32b-instruct-q8_0 deepseek-r1:32b-q8_0 qwen2.5-coder:32b-instruct-q8_0 llama3.1:70b mixtral:8x22b command-r-plus:104b wizardlm2:8x22b qwen2-math:72b dolphin-llama3:70b-v2.9.3-q8_0"
set "MODELS_gpu_mega=llama3.3:70b-instruct-q8_0 qwen2.5:72b-instruct-q8_0 deepseek-r1:70b-q8_0 nemotron:70b-instruct-q8_0 llama3.1:70b-instruct-q8_0 mixtral:8x22b-instruct-v0.1-q8_0 command-r-plus:104b-q8_0 qwen2-math:72b-instruct-q8_0 dolphin-llama3:70b-v2.9.3-fp16 deepseek-coder-v2:236b dbrx:132b wizardlm:70b llama3.3:70b-instruct-fp16"

:: ══════════════════════════════════════════════════════════
::  MODEL DOWNLOADER
:: ══════════════════════════════════════════════════════════
echo.
echo ──────────────────────────────────────────────────
echo Please select your hardware tier to download models:
echo  1. CPU Tiny   (Under 8GB RAM)
echo  2. CPU Small  (8GB - 15GB RAM)
echo  3. CPU Medium (16GB - 31GB RAM)
echo  4. CPU Large  (32GB - 63GB RAM)
echo  5. CPU Mega   (64GB+ RAM)
echo  6. GPU Tiny   (Under 8GB VRAM)
echo  7. GPU Small  (8GB - 15GB VRAM)
echo  8. GPU Medium (16GB - 23GB VRAM)
echo  9. GPU Large  (24GB - 47GB VRAM)
echo 10. GPU Mega   (48GB+ VRAM)
echo  0. Skip model download
echo ──────────────────────────────────────────────────

set /p TIER_CHOICE="Enter number (0-10): "

if "%TIER_CHOICE%"=="1" set "SELECTED_MODELS=!MODELS_cpu_tiny!"
if "%TIER_CHOICE%"=="2" set "SELECTED_MODELS=!MODELS_cpu_small!"
if "%TIER_CHOICE%"=="3" set "SELECTED_MODELS=!MODELS_cpu_medium!"
if "%TIER_CHOICE%"=="4" set "SELECTED_MODELS=!MODELS_cpu_large!"
if "%TIER_CHOICE%"=="5" set "SELECTED_MODELS=!MODELS_cpu_mega!"
if "%TIER_CHOICE%"=="6" set "SELECTED_MODELS=!MODELS_gpu_tiny!"
if "%TIER_CHOICE%"=="7" set "SELECTED_MODELS=!MODELS_gpu_small!"
if "%TIER_CHOICE%"=="8" set "SELECTED_MODELS=!MODELS_gpu_medium!"
if "%TIER_CHOICE%"=="9" set "SELECTED_MODELS=!MODELS_gpu_large!"
if "%TIER_CHOICE%"=="10" set "SELECTED_MODELS=!MODELS_gpu_mega!"
if "%TIER_CHOICE%"=="0" goto skip_pull

if not defined SELECTED_MODELS (
    echo.
    echo Invalid choice. Skipping model download.
    goto skip_pull
)

echo.
echo Pulling models for your selected tier...
for %%M in (!SELECTED_MODELS!) do (
    echo Pulling %%M...
    ollama pull %%M
)
echo.
echo Note: Whisper models are downloaded automatically by faster-whisper on first use.

:skip_pull
echo.
echo ════════════════════════════════════════════════════
echo   ✅  Installation complete!
echo.
echo   HOW TO START:
echo    Terminal 1 -  ollama serve
echo    Terminal 2 -  python orchestrator.py
echo.
echo   PAIO will start listening immediately.
echo ════════════════════════════════════════════════════
echo.
pause
endlocal