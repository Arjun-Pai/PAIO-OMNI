# PAIO-Omni — Linux Setup Guide

PAIO-Omni is an always-on, voice-driven AI assistant that listens through your
microphone, picks a "mode" (fast, deep, coder, teacher, etc.) based on what you
say, talks to a local Ollama model, optionally looks through your webcam, and
speaks the answer back to you using `espeak-ng` (via `pyttsx3`).

This guide is written for **Debian/Ubuntu-based distros** (Ubuntu, Debian,
Linux Mint, Pop!_OS, etc.), since `install.py` uses `apt-get` directly. If
you're on Fedora, Arch, or another distro, see the note at the bottom for
package-name substitutions.

---

## 1. What you need before you start

| Requirement | Why | Where to get it |
|---|---|---|
| Debian/Ubuntu-based Linux | Target OS for this guide | — |
| Python 3.9+ | Runs all the PAIO scripts | usually preinstalled, or `apt install python3` |
| Ollama for Linux | Runs the local LLM + vision models | https://ollama.com/download/linux |
| A working microphone | Speech input | Built-in laptop mic or USB mic |
| A webcam (optional) | Vision mode ("what do you see") | Built-in or USB webcam, exposed as `/dev/video0` |
| ~10–40 GB free disk space | Ollama model weights | Depends on hardware tier, see step 6 |
| `sudo` access | Installing system packages | — |

> **NVIDIA GPU note:** If you have an NVIDIA GPU, install the proprietary
> driver (`nvidia-driver-XXX` from `apt` or `ubuntu-drivers autoinstall`) so
> that `nvidia-smi` works — `hardware.py` uses it to detect VRAM and pick the
> `gpu_high` tier automatically.

---

## 2. Install/verify Python

Most Debian/Ubuntu systems already ship with Python 3. Check:

```bash
python3 --version
```

If it's missing or older than 3.9:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv
```

---

## 3. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verify:

```bash
ollama --version
```

---

## 4. Get the PAIO-Omni project files onto your machine

Put all the project files in one folder, e.g. `~/paio-omni/`:

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

Then:

```bash
cd ~/paio-omni
```

---

## 5. Run the installer

```bash
python3 install.py
```

This script will, in order:

1. **Check Python version** (must be 3.9+).
2. **Check that Ollama is installed** (fails with a helpful message if not).
3. **Install system dependencies via `apt-get`:**
   ```bash
   sudo apt-get install -y portaudio19-dev espeak-ng python3-dev ffmpeg v4l-utils
   ```
   - `portaudio19-dev` → required for `sounddevice` to build/run (microphone)
   - `espeak-ng` → the actual voice engine `pyttsx3` drives on Linux
   - `python3-dev` → headers needed to compile some Python packages
   - `ffmpeg` → audio/video codec support
   - `v4l-utils` → Video4Linux camera utilities/detection for webcam support

   You'll be prompted for your `sudo` password during this step.
4. **Install Python packages via pip**, upgrading each of:
   - `faster-whisper` (speech-to-text)
   - `sounddevice` (microphone capture)
   - `numpy`
   - `requests` (talks to the local Ollama API)
   - `opencv-python` (webcam capture)
   - `pyttsx3` (drives `espeak-ng` for text-to-speech)
   - `psutil` (RAM detection for hardware tiering)
5. **Detect your hardware** (RAM, GPU/VRAM via `nvidia-smi`) and print a
   summary like:

   ```
   Linux x86_64 · 32 GB RAM · NVIDIA GPU 12GB · Tier: gpu_high
   ```

6. **Ask if you want to pull the Ollama models now.** Type `y` and press
   Enter to download them immediately, or `n` to skip and pull them manually
   later. Model size guide:
   - `cpu_tiny` / `cpu_small` tier → just `llama3.2:1b` (~1.3 GB)
   - `cpu_med` tier → several 3B–8B models (~15–20 GB total)
   - `gpu_high` tier → several 8B–70B models (~40+ GB total — make sure you
     have the disk space and a good connection before saying yes)

If you'd rather pull models manually:

```bash
ollama pull llama3.2:1b
ollama pull llama3.1:8b
```

> **Tip:** it's usually cleanest to do all of this inside a virtual
> environment so PAIO's dependencies don't clash with system Python packages:
> ```bash
> python3 -m venv venv
> source venv/bin/activate
> python install.py
> ```
> Remember to `source venv/bin/activate` again in any new terminal before
> running `orchestrator.py`.

---

## 6. Check microphone & camera access

**Microphone:** list your input devices to confirm one is detected:

```bash
python3 -c "import sounddevice as sd; print(sd.query_devices())"
```

If your user isn't in the `audio` group, add yourself and log out/in:

```bash
sudo usermod -aG audio $USER
```

**Camera:** confirm your webcam shows up as a video device:

```bash
v4l2-ctl --list-devices
```

You should see something like `/dev/video0`. If your user lacks permission,
add yourself to the `video` group and log out/in:

```bash
sudo usermod -aG video $USER
```

---

## 7. Start everything

PAIO-Omni needs **two terminals** open at the same time.

**Terminal 1 — start Ollama's server:**

```bash
ollama serve
```

(On many installs, Ollama also runs automatically as a `systemd` service —
check with `systemctl status ollama` before assuming you need this step.)

**Terminal 2 — start PAIO:**

```bash
cd ~/paio-omni
source venv/bin/activate   # if you used a virtual environment
python3 orchestrator.py
```

You'll see hardware detection, then TTS/STT/vision loading, then:

```
👂  Listening — just speak ...
```

Just talk — no wake word or button press needed. PAIO auto-detects the right
"mode" (fast/deep/coder/teacher/etc.) from your phrasing and replies out loud.

Press `Ctrl+C` in Terminal 2 to shut it down cleanly.

---

## 8. Troubleshooting (Linux)

| Symptom | Likely cause / fix |
|---|---|
| `sudo: command not found` during `apt-get install` | You're not on a Debian/Ubuntu-based distro — see the distro-substitution note below |
| `❌ Ollama not found` during install | Re-run `curl -fsSL https://ollama.com/install.sh \| sh`, then restart your terminal |
| Ollama error: `Ollama isn't running` | Run `ollama serve` in another terminal, or check `systemctl status ollama` |
| `sounddevice`/PortAudio import errors | Make sure `portaudio19-dev` installed correctly: `sudo apt-get install -y portaudio19-dev`, then `pip install --force-reinstall sounddevice` |
| No audio output at all | Confirm `espeak-ng` is installed (`espeak-ng "test"` should speak) and that your system's default audio sink is correct (`pavucontrol` or `alsamixer`) |
| Mic never triggers / nothing transcribed | Check `python3 -c "import sounddevice as sd; print(sd.query_devices())"` for the right default input, and confirm you're in the `audio` group |
| Webcam / vision mode doesn't work | Confirm `/dev/video0` exists (`v4l2-ctl --list-devices`), you're in the `video` group, and no other app is holding the camera |
| `opencv-python` fails to build/import | Try `pip install opencv-python-headless` instead, or ensure `python3-dev` and standard build tools are installed |
| Model pulls are very slow or huge | Lower-tier hardware pulls smaller models automatically; you can manually `ollama pull llama3.2:1b` for a much smaller footprint |

### Using a non-Debian distro (Fedora, Arch, etc.)

`install.py`'s system-dependency step only runs `apt-get`, so on other distros
you'll need to install the equivalent packages yourself **before** running
`python install.py` (the pip/model steps will work the same everywhere):

- **Fedora:**
  ```bash
  sudo dnf install -y portaudio-devel espeak-ng python3-devel ffmpeg v4l-utils
  ```
- **Arch/Manjaro:**
  ```bash
  sudo pacman -S portaudio espeak-ng ffmpeg v4l-utils
  ```

---

## 9. Quick reference — every command in order

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv
curl -fsSL https://ollama.com/install.sh | sh
cd ~/paio-omni
python3 -m venv venv && source venv/bin/activate
python install.py
ollama serve                  # keep this terminal open
python3 orchestrator.py       # in a second terminal
```
