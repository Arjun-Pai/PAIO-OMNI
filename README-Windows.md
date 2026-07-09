# PAIO-Omni — Windows Setup Guide

PAIO-Omni is an always-on, voice-driven AI assistant that listens through your
microphone, picks a "mode" (fast, deep, coder, teacher, etc.) based on what you
say, talks to a local Ollama model, optionally looks through your webcam, and
speaks the answer back to you with Windows' built-in text-to-speech voices
(including any custom voice you've installed, like a VoiceBox voice).

This guide walks through a totally clean Windows 10/11 machine, end to end.

---

## 1. What you need before you start

| Requirement | Why | Where to get it |
|---|---|---|
| Windows 10 or 11 (64-bit) | Target OS | — |
| Python 3.9+ | Runs all the PAIO scripts | https://www.python.org/downloads/ |
| Ollama for Windows | Runs the local LLM + vision models | https://ollama.com/download/windows |
| A working microphone | Speech input | Built-in laptop mic or USB mic |
| A webcam (optional) | Vision mode ("what do you see") | Built-in or USB webcam |
| ~10–40 GB free disk space | Ollama model weights | Depends on hardware tier, see step 6 |

> **Tip:** If you have an NVIDIA GPU, install the latest NVIDIA driver first —
> `hardware.py` checks for `nvidia-smi` to detect your VRAM and pick bigger models
> automatically.

---

## 2. Install Python

1. Download the installer from https://www.python.org/downloads/
2. Run it. **Check the box "Add Python to PATH"** at the bottom of the first
   install screen — this is the #1 cause of "python is not recognized" errors.
3. Verify it worked. Open **Command Prompt** or **PowerShell** and run:

   ```powershell
   python --version
   ```

   You should see `Python 3.9` or higher. If you see an error, restart your
   terminal (or your PC) and try again.

---

## 3. Install Ollama

1. Download and run the Windows installer:
   https://ollama.com/download/windows
2. Once installed, Ollama runs as a background service. Confirm it's working:

   ```powershell
   ollama --version
   ```

---

## 4. Get the PAIO-Omni project files onto your PC

Put all the project files in one folder, e.g. `C:\PAIO-Omni\`:

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

Open Command Prompt / PowerShell **in that folder** (Shift + right-click inside
the folder → "Open PowerShell window here", or `cd C:\PAIO-Omni`).

---

## 5. Run the installer

Windows needs no extra system packages (portaudio/ffmpeg come bundled inside
the pip wheels), so `install.py` keeps this step short on Windows. From inside
the project folder:

```powershell
python install.py
```

This script will, in order:

1. **Check Python version** (must be 3.9+).
2. **Check that Ollama is installed** (fails with a helpful message if not).
3. **Skip system dependency installs** (not needed on Windows).
4. **Install Python packages via pip**, upgrading each of:
   - `faster-whisper` (speech-to-text)
   - `sounddevice` (microphone capture)
   - `numpy`
   - `requests` (talks to the local Ollama API)
   - `opencv-python` (webcam capture)
   - `pyttsx3` (Windows SAPI text-to-speech)
   - `psutil` (RAM detection for hardware tiering)
5. **Detect your hardware** (RAM, GPU, VRAM) and print a summary like:

   ```
   Windows AMD64 · 16 GB RAM · NVIDIA GPU 8GB · Tier: gpu_high
   ```

6. **Ask if you want to pull the Ollama models now.** Type `y` and press Enter
   to download them immediately, or `n` to skip and pull them manually later.
   Model size guide:
   - `cpu_tiny` / `cpu_small` tier → just `llama3.2:1b` (~1.3 GB)
   - `cpu_med` tier → several 3B–8B models (~15–20 GB total)
   - `gpu_high` tier → several 8B–70B models (~40+ GB total — make sure you have
     the disk space and a good connection before saying yes)

If you'd rather pull models manually, run e.g.:

```powershell
ollama pull llama3.2:1b
ollama pull llama3.1:8b
```

---

## 6. (Recommended) Set up your custom voice

If you have a custom TTS voice installed on Windows (e.g. a "VoiceBox" voice
made from your own recordings) and want PAIO to use it instead of the default
David/Zira voices, find its exact name first:

```powershell
python check_voices.py
```

This lists every voice Windows knows about (via SAPI) and tries to
auto-detect and test-speak anything with "voicebox", "custom", or "my" in its
name. Copy the **exact name** it prints, then open `tts.py` and add your voice
to the `preferred` list near the top of `_tts_worker`:

```python
preferred = ["david", "zira", "mark", "your voice name here"] if os_name == "Windows" else ["samantha", "alex"]
```

Put your voice name **first** in the list if you want it prioritized over the
defaults.

---

## 7. Start everything

PAIO-Omni needs **two terminal windows** open at the same time.

**Terminal 1 — start Ollama's server:**

```powershell
ollama serve
```

Leave this window open and running in the background.

**Terminal 2 — start PAIO:**

```powershell
cd C:\PAIO-Omni
python orchestrator.py
```

You'll see hardware detection, then TTS/STT/vision loading, then:

```
👂  Listening — just speak ...
```

Just talk — no wake word or button press needed. PAIO auto-detects the right
"mode" (fast/deep/coder/teacher/etc.) from your phrasing and replies out loud.

Press `Ctrl+C` in Terminal 2 to shut it down cleanly.

---

## 8. Troubleshooting (Windows)

| Symptom | Likely cause / fix |
|---|---|
| `python is not recognized` | Python wasn't added to PATH — reinstall Python and check the PATH box, or run `py` instead of `python` |
| `❌ Ollama not found` during install | Install Ollama, then close and reopen your terminal so PATH refreshes |
| Ollama error: `Ollama isn't running` | Make sure Terminal 1 (`ollama serve`) is still open |
| No sound / wrong voice speaking | Run `python check_voices.py` to see available voices and fix the name in `tts.py` |
| Mic never triggers / nothing gets transcribed | Check Windows microphone privacy permissions: **Settings → Privacy & security → Microphone** → allow desktop apps. Also confirm the correct mic is set as your Windows default input device |
| Webcam / vision mode doesn't work | Check Windows camera privacy permissions: **Settings → Privacy & security → Camera**. Also make sure no other app (Teams, Zoom) is holding the camera |
| Downloads of Ollama models are very slow/huge | Lower-tier hardware pulls smaller models automatically; you can also manually `ollama pull llama3.2:1b` for a much smaller footprint |
| `faster-whisper`/`torch` install fails | Make sure you're on 64-bit Python 3.9+ and have a recent pip: `python -m pip install --upgrade pip` |

---

## 9. Quick reference — every command in order

```powershell
python --version
ollama --version
cd C:\PAIO-Omni
python install.py
python check_voices.py        REM optional, for custom voices
ollama serve                  REM keep this terminal open
python orchestrator.py        REM in a second terminal
```
