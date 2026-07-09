# PAIO-OMNI

**A fully offline, voice-driven AI assistant** powered by local Ollama models, custom TTS voices, and optional vision capabilities.

![Status](https://img.shields.io/badge/Status-Active-brightgreen) ![Python](https://img.shields.io/badge/Python-3.9+-blue) ![License](https://img.shields.io/badge/License-Other-orange)

---

## What is PAIO-OMNI?

PAIO-OMNI is an always-on AI assistant that:

- **Listens passively** through your microphone — no wake words or button presses required
- **Auto-detects modes** (fast, deep, coder, teacher, etc.) based on your phrasing and intent
- **Runs entirely offline** using Ollama with local LLM models (Llama 3.2, Llama 3.1, and more)
- **Speaks back naturally** using platform-specific TTS:
  - **Linux:** espeak-ng via pyttsx3
  - **Windows:** SAPI voices (including custom VoiceBox voices)
  - **macOS:** Samantha/Alex via NSSpeechSynthesizer
- **Optionally sees** through your webcam for vision-based queries ("what do you see?")

No cloud calls. No API keys. No data sent outside your machine. **100% private.**

---

## Quick Start

### Prerequisites

| Requirement | Why | Where |
|---|---|---|
| **OS** | Target platform | Windows 10/11, macOS 12+, or Debian/Ubuntu-based Linux |
| **Python 3.9+** | Runtime | https://www.python.org/downloads/ or your system package manager |
| **Ollama** | Local LLM engine | https://ollama.com/download |
| **Microphone** | Speech input | Built-in or USB |
| **Webcam (optional)** | Vision mode | Built-in or USB |
| **10–40 GB disk space** | Model weights | Depends on your hardware tier |

> **GPU Acceleration:** If you have an NVIDIA GPU, install the latest driver — `hardware.py` will auto-detect VRAM and pull larger models automatically.

### Installation & Setup

1. **Clone or download** all project files to a local folder
2. **Pick your platform guide:**
   - **[Linux Setup](./README-Linux.md)** — Debian/Ubuntu-based systems
   - **[Windows Setup](./README-Windows.md)** — Windows 10/11
   - **[macOS Setup](./README-macOS.md)** — macOS 12+

3. Each guide walks you through:
   - Installing system dependencies
   - Running `python install.py` (auto-detects your hardware tier)
   - Optionally pulling Ollama models
   - Starting the Ollama server and PAIO

### Run It

```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Start PAIO
python3 orchestrator.py  # or python orchestrator.py on Windows
