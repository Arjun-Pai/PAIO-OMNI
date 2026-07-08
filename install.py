#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────
#  PAIO-Omni  ·  install.py
#  Cross-platform installer.
#  Works on Windows, macOS, Linux — detects OS automatically.
#  Run with:  python install.py
# ─────────────────────────────────────────────────────────

import subprocess
import sys
import platform
import os
import shutil

OS   = platform.system()    # Windows / Linux / Darwin
ARCH = platform.machine()   # x86_64 / arm64 / aarch64


def run(cmd, **kwargs):
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, **kwargs)


def pip(*packages):
    run([sys.executable, "-m", "pip", "install", "--upgrade", *packages])


def ollama_pull(model: str):
    print(f"\n  Pulling  {model}  ...")
    run(["ollama", "pull", model])


def section(title: str):
    print(f"\n{'─'*50}")
    print(f"  {title}")
    print(f"{'─'*50}")


# ══════════════════════════════════════════════════════════
#  PRE-FLIGHT CHECKS
# ══════════════════════════════════════════════════════════

def check_python():
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 9):
        print(f"❌  Python 3.9+ required.  You have {major}.{minor}")
        print("    Download from https://www.python.org/downloads/")
        sys.exit(1)
    print(f"  ✓ Python {major}.{minor}")


def check_ollama():
    if shutil.which("ollama") is None:
        print("❌  Ollama not found.")
        if OS == "Windows":
            print("    Download: https://ollama.com/download/windows")
        elif OS == "Darwin":
            print("    Run:  brew install ollama")
            print("    Or:   https://ollama.com/download/mac")
        else:
            print("    Run:  curl -fsSL https://ollama.com/install.sh | sh")
        print("    Install Ollama, then re-run this script.")
        sys.exit(1)
    print("  ✓ Ollama found")


# ══════════════════════════════════════════════════════════
#  SYSTEM DEPENDENCIES  (platform-specific)
# ══════════════════════════════════════════════════════════

def install_system_deps():
    section("System dependencies")

    if OS == "Linux":
        pkgs = ["portaudio19-dev", "espeak-ng", "python3-dev", "ffmpeg"]
        # v4l-utils for camera detection
        pkgs.append("v4l-utils")
        print("  Installing system packages via apt ...")
        run(["sudo", "apt-get", "install", "-y"] + pkgs)

    elif OS == "Darwin":
        if shutil.which("brew"):
            print("  Installing portaudio via Homebrew ...")
            run(["brew", "install", "portaudio", "ffmpeg"])
        else:
            print("  Homebrew not found — skipping system deps.")
            print("  If audio fails, install Homebrew then run:")
            print("    brew install portaudio ffmpeg")

    elif OS == "Windows":
        print("  Windows: no system deps needed (bundled in pip packages).")


# ══════════════════════════════════════════════════════════
#  PYTHON PACKAGES
# ══════════════════════════════════════════════════════════

def install_python_packages():
    section("Python packages")
    packages = [
        "faster-whisper",    # STT
        "sounddevice",       # microphone / audio
        "numpy",             # audio array processing
        "requests",          # Ollama API
        "opencv-python",     # camera capture
        "pyttsx3",           # TTS (cross-platform SAPI)
        "psutil",            # hardware RAM detection
    ]
    pip(*packages)


# ══════════════════════════════════════════════════════════
#  OLLAMA MODELS  (hardware-aware)
# ══════════════════════════════════════════════════════════

def install_models():
    section("Detecting hardware to choose models")

    # Import hardware AFTER psutil is installed
    try:
        import hardware
        hw = hardware.detect()
        print(f"  {hardware.summary(hw)}")
    except Exception as e:
        print(f"  Hardware detection failed ({e}) — using cpu_medium defaults")
        hw = {"models": hardware.TIER_MODELS["cpu_medium"], "tier": "cpu_medium"}

    models_needed = set(hw["models"].values())
    models_needed.discard(None)

    print(f"\n  Tier: {hw['tier']}")
    print(f"  Models to pull: {len(models_needed)}")
    total_est = len(models_needed) * 2   # rough GB estimate
    print(f"  Estimated download: ~{total_est} GB")
    print()

    ans = input("  Pull all models now? (y/n): ").strip().lower()
    if ans == "y":
        for model in sorted(models_needed):
            ollama_pull(model)
    else:
        print("  Skipped. Run  ollama pull <model>  manually.")
        print("  Required models for your hardware:")
        for role, model in sorted(hw["models"].items()):
            if model:
                print(f"    {role:<14} → ollama pull {model}")


# ══════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════

def main():
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║       PAIO-Omni  —  Installer                ║")
    print(f"║       {OS}  {ARCH:<34}║")
    print("╚══════════════════════════════════════════════╝")
    print()

    check_python()
    check_ollama()
    install_system_deps()
    install_python_packages()
    install_models()

    print()
    print("═" * 52)
    print("  ✅  Installation complete!")
    print()
    print("  HOW TO START:")
    print("   Terminal 1 →  ollama serve")
    print("   Terminal 2 →  python orchestrator.py")
    print()
    print("  PAIO will start listening immediately.")
    print("  Just speak — mode is detected automatically.")
    print("═" * 52)
    print()


if __name__ == "__main__":
    main()
