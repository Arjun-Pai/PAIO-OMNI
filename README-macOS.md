# PAIO-Omni — macOS Setup Guide

PAIO-Omni is an always-on, voice-driven AI assistant that listens through your
microphone, picks a "mode" (fast, deep, coder, teacher, etc.) based on what you
say, talks to a local Ollama model, optionally looks through your webcam, and
speaks the answer back to you using macOS's built-in text-to-speech voices
(Samantha/Alex by default).

This guide walks through a clean macOS machine, end to end. It covers both
Apple Silicon (M1/M2/M3/M4) and Intel Macs.

---

## 1. What you need before you start

| Requirement | Why | Where to get it |
|---|---|---|
| macOS 12+ (Monterey or later recommended) | Target OS | — |
| Python 3.9+ | Runs all the PAIO scripts | https://www.python.org/downloads/mac-osx/ or Homebrew |
| Homebrew | Installs system-level audio libraries | https://brew.sh |
| Ollama for Mac | Runs the local LLM + vision models | https://ollama.com/download/mac or `brew install ollama` |
| A working microphone | Speech input | Built-in MacBook mic or external mic |
| A webcam (optional) | Vision mode ("what do you see") | Built-in FaceTime camera or external |
| ~10–40 GB free disk space | Ollama model weights | Depends on hardware tier, see step 6 |

> **Apple Silicon note:** `hardware.py` detects Apple Silicon (arm64) and
> treats your unified memory as usable "VRAM," so M-series Macs with 16 GB+
> RAM will automatically get bumped to the `gpu_high` tier and larger models.

---

## 2. Install Homebrew (if you don't have it)

Open **Terminal** (Spotlight → type "Terminal") and run:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the on-screen instructions — it may ask you to run one or two extra
`export PATH` lines it prints at the end. Copy/paste and run those.

Verify:

```bash
brew --version
```

---

## 3. Install Python

Either use Homebrew (recommended, keeps things clean from the system Python):

```bash
brew install python@3.12
```

Or download the official installer from
https://www.python.org/downloads/mac-osx/ and run it.

Verify:

```bash
python3 --version
```

You should see `Python 3.9` or higher. On macOS you'll generally use
`python3` / `pip3` rather than `python` / `pip`.

---

## 4. Install Ollama

Either via Homebrew:

```bash
brew install ollama
```

Or download the app from https://ollama.com/download/mac and drag it into
Applications.

Verify:

```bash
ollama --version
```

---

## 5. Get the PAIO-Omni project files onto your Mac

Put all the project files in one folder, e.g. `~/PAIO-Omni/`:

```
check_voices.py
config.py
hardware.py
install.py
llm.py
modes.py
orchestrator.py
requirements.txt
stt.py
tts.py
vision.py
```

Open Terminal and `cd` into that folder:

```bash
cd ~/PAIO-Omni
```

---

## 6. Run the installer

```bash
python3 install.py
```

This script will, in order:

1. **Check Python version** (must be 3.9+).
2. **Check that Ollama is installed** (fails with a helpful message if not).
3. **Install system dependencies via Homebrew:**
   ```bash
   brew install portaudio ffmpeg
   ```
   (`install.py` runs this for you automatically if `brew` is found. If
   Homebrew isn't found, it skips this step and prints the command so you can
   run it yourself later.)
4. **Install Python packages via pip3**, upgrading each of:
   - `faster-whisper` (speech-to-text)
   - `sounddevice` (microphone capture — needs `portaudio` from step 3)
   - `numpy`
   - `requests` (talks to the local Ollama API)
   - `opencv-python` (webcam capture)
   - `pyttsx3` (macOS `NSSpeechSynthesizer`-backed text-to-speech)
   - `psutil` (RAM detection for hardware tiering)
5. **Detect your hardware** (RAM, Apple Silicon vs Intel) and print a summary
   like:

   ```
   Darwin arm64 · 16 GB RAM · Apple Silicon 16GB · Tier: gpu_high
   ```

6. **Ask if you want to pull the Ollama models now.** Type `y` and press
   Enter to download them immediately, or `n` to skip and pull them manually
   later. Model size guide:
   - `cpu_tiny` / `cpu_small` tier → just `llama3.2:1b` (~1.3 GB)
   - `cpu_med` tier → several 3B–8B models (~15–20 GB total)
   - `gpu_high` tier (most Apple Silicon Macs with 16 GB+ RAM) → several
     8B–70B models (~40+ GB total — make sure you have the disk space)

If you'd rather pull models manually:

```bash
ollama pull llama3.2:1b
ollama pull llama3.1:8b
```

---

## 7. Grant microphone & camera permissions

The first time PAIO tries to use the mic or camera, macOS will pop up a
permission dialog — click **Allow**. If you miss it or need to change it
later:

**System Settings → Privacy & Security → Microphone** → enable Terminal (or
whichever app/terminal you're running Python from).

**System Settings → Privacy & Security → Camera** → same, enable Terminal.

If you don't see Terminal in these lists, run `orchestrator.py` once first —
macOS only shows the prompt (and adds the entry) after the app actually tries
to access the mic/camera.

---

## 8. Start everything

PAIO-Omni needs **two Terminal windows/tabs** open at the same time.

**Terminal 1 — start Ollama's server:**

```bash
ollama serve
```

Leave this running in the background. (If you installed the Ollama.app
instead of the CLI, it may already be running as a menu-bar app — in that
case you can skip this step, `llm.check_ollama()` will just find it.)

**Terminal 2 — start PAIO:**

```bash
cd ~/PAIO-Omni
python3 orchestrator.py
```

You'll see hardware detection, then TTS/STT/vision loading, then:

```
👂  Listening — just speak ...
```

Just talk — no wake word or button press needed. PAIO auto-detects the right
"mode" (fast/deep/coder/teacher/etc.) from your phrasing and replies out loud
using Samantha or Alex by default.

Press `Ctrl+C` in Terminal 2 to shut it down cleanly.

---

## 9. Troubleshooting (macOS)

| Symptom | Likely cause / fix |
|---|---|
| `command not found: python3` | Install Python via Homebrew (`brew install python@3.12`) or the official installer |
| `❌ Ollama not found` during install | Install via `brew install ollama` or the Ollama.app, then restart Terminal |
| Ollama error: `Ollama isn't running` | Make sure Terminal 1 (`ollama serve`) is running, or the Ollama menu-bar app is active |
| `sounddevice` fails to import / PortAudio error | Run `brew install portaudio` manually, then reinstall: `pip3 install --force-reinstall sounddevice` |
| No sound comes out | macOS text-to-speech uses `pyttsx3` → `NSSpeechSynthesizer`; check System Settings → Accessibility → Spoken Content to confirm system voices are installed |
| Mic never triggers / nothing gets transcribed | Check System Settings → Privacy & Security → Microphone permissions for Terminal, and confirm the right input device is selected in System Settings → Sound → Input |
| Webcam / vision mode doesn't work | Check System Settings → Privacy & Security → Camera permissions for Terminal |
| Model pulls are very slow or huge | Lower-tier hardware pulls smaller models automatically; you can manually `ollama pull llama3.2:1b` for a much smaller footprint |
| `pip3 install` permission errors | Avoid `sudo pip3install`; instead use a virtual environment: `python3 -m venv venv && source venv/bin/activate` then re-run `python install.py` |

---

## 10. Quick reference — every command in order

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"   # if no brew
brew install python@3.12
brew install ollama
cd ~/PAIO-Omni
python3 install.py
ollama serve                  # keep this terminal open
python3 orchestrator.py       # in a second terminal
```
