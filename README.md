# PAIO-Omni
<img width="1366" height="678" alt="image" src="https://github.com/user-attachments/assets/dee533b6-ae46-463f-84a9-96aa0ae6349a" />

PAIO-Omni is an offline-first AI assistant with:

- A native floating orb interface.
- Local Ollama model support.
- Piper text-to-speech.
- Whisper speech-to-text.
- Optional cloud fallbacks.
- Custom wake-word support.
- Persistent memory and optional Obsidian vault integration.

PAIO can run locally through Ollama. Cloud providers are optional.

---

## Fresh installation

### Requirements

Install the following before starting:

- Python 3.10 or newer
- Ollama
- A microphone
- Speakers or headphones
- Piper and a Piper voice model
- Git, if cloning the repository

Windows users should use PowerShell or Command Prompt. Linux and macOS users should use a terminal.

---

## 1. Download PAIO-Omni

```bash
git clone https://github.com/Arjun-Pai/PAIO-OMNI.git
cd PAIO-OMNI
```

To use the V3.0 branch:

```bash
git checkout V3.0
```

---

## 2. Create a Python virtual environment

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

### Windows Command Prompt

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate.bat
```

### Linux or macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

---

## 3. Install PAIO dependencies

From the repository root:

```bash
python -m pip install -r requirements.txt
```

You can also install PAIO as a local pip package:

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e .
```

After installation, the following commands are available:

```bash
paio
paio setup
paio check
paio-omni
```

If the `paio` command is not found, use:

```bash
python -m paio.cli
```

---

## 4. Install and test Ollama

PAIO uses Ollama for local models and offline fallback.

### Windows

Install Ollama from the official Ollama website or use the automatic installer in `onboarding.py`.

After installation, check it:

```powershell
ollama --version
```

### macOS

Install Ollama from the official Ollama website or with Homebrew:

```bash
brew install ollama
```

Check it:

```bash
ollama --version
```

### Linux

Install Ollama using the official installation method. The onboarding script can also attempt the installation automatically.

Check it:

```bash
ollama --version
```

### Start Ollama

If Ollama is not already running:

```bash
ollama serve
```

Leave that terminal open if Ollama is not configured as a background service.

### Download a local model

For example:

```bash
ollama pull llama3.2
```

Test the model:

```bash
ollama run llama3.2
```

PAIO can download additional models during onboarding based on detected hardware. The initial model download may require significant disk space.

The local Ollama API should be available at:

```text
http://localhost:11434
```

---

## 5. Install Piper TTS

Piper is an external text-to-speech executable. It is not installed by the normal Python dependency installation.

Create this directory:

```text
models/piper/
```

The expected layout is:

### Windows

```text
models/
└── piper/
    ├── piper.exe
    ├── *.dll
    ├── en_US-bryce-medium.onnx
    └── en_US-bryce-medium.onnx.json
```

### Linux or macOS

```text
models/
└── piper/
    ├── piper
    ├── en_US-bryce-medium.onnx
    └── en_US-bryce-medium.onnx.json
```

The `.onnx` voice file and `.onnx.json` configuration file must belong to the same Piper voice model.

The default voice expected by PAIO is:

```text
en_US-bryce-medium.onnx
en_US-bryce-medium.onnx.json
```

If you use a different Piper voice, set the following environment variables:

```text
PAIO_PIPER_EXE=/path/to/piper
PAIO_PIPER_MODEL=/path/to/voice.onnx
PAIO_PIPER_CONFIG=/path/to/voice.onnx.json
```

On Windows, use paths such as:

```text
PAIO_PIPER_EXE=C:\PAIO-OMNI\models\piper\piper.exe
PAIO_PIPER_MODEL=C:\PAIO-OMNI\models\piper\en_US-bryce-medium.onnx
PAIO_PIPER_CONFIG=C:\PAIO-OMNI\models\piper\en_US-bryce-medium.onnx.json
```

On Linux and macOS, make the Piper executable runnable:

```bash
chmod +x models/piper/piper
```

### Test Piper manually

#### Windows PowerShell

```powershell
"Hello from PAIO" | .\models\piper\piper.exe `
  --model .\models\piper\en_US-bryce-medium.onnx `
  --config .\models\piper\en_US-bryce-medium.onnx.json `
  --output_file .\paio-test.wav
```

#### Linux

```bash
echo "Hello from PAIO" | ./models/piper/piper \
  --model ./models/piper/en_US-bryce-medium.onnx \
  --config ./models/piper/en_US-bryce-medium.onnx.json \
  --output_file ./paio-test.wav
```

#### macOS

```bash
echo "Hello from PAIO" | ./models/piper/piper \
  --model ./models/piper/en_US-bryce-medium.onnx \
  --config ./models/piper/en_US-bryce-medium.onnx.json \
  --output_file ./paio-test.wav
```

Play `paio-test.wav`. Delete it after testing.

---

## 6. Run the guided setup

The recommended setup command is:

```bash
paio setup
```

You can also run:

```bash
python onboarding.py
```

The setup process can:

1. Check and install missing Python packages.
2. Check for Ollama.
3. Attempt to install Ollama when supported by the operating system.
4. Start the local Ollama service.
5. Optionally sign in to Ollama Cloud.
6. Ask for optional cloud API keys.
7. Test cloud API keys.
8. Configure model priorities.
9. Download local Ollama models.
10. Check Piper files.
11. Offer to launch PAIO.

Cloud API keys are optional. PAIO can use local Ollama without them.

---

## 7. Check the installation

Run:

```bash
paio check
```

This checks:

- Python
- Ollama
- Piper executable
- Piper model
- Piper configuration file
- PAIO setup configuration

Fix any missing items before launching PAIO.

---

## 8. Launch PAIO

After setup:

```bash
paio
```

You can also use:

```bash
paio start
```

Or run the application directly:

```bash
python orchestrator.py
```

PAIO can normally be activated by:

- Saying the configured wake phrase.
- Holding the Home key.
- Clicking the floating orb.

---

## API keys and cloud services

The following services are optional:

```text
ZENMUX_API_KEY
OPENROUTER_API_KEY
GROQ_API_KEY
TYPESAFE_API_KEY
```

Run:

```bash
paio setup
```

to enter and test them interactively.

You may manually copy `.env.example` to `.env`, but do not commit `.env`:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Ollama Cloud authentication is handled separately:

```bash
ollama signin
```

---

## Wake-word recordings are not Piper files

These directories have different purposes.

### Piper TTS files

```text
models/piper/
```

These files make PAIO speak:

```text
piper
piper.exe
*.onnx
*.onnx.json
```

### Wake-word training recordings

```text
voices/
```

These are recordings of you saying the wake phrase. They are used to train the custom wake-word detector.

Add at least 10 recordings, preferably more:

```text
voices/
├── recording-01.wav
├── recording-02.wav
├── recording-03.wav
└── ...
```

Then run:

```bash
python wakeword_train.py
```

The generated wake-word model is expected at:

```text
models/hey_paio.onnx
```

Do not put Piper voice models in `voices/`.

---

## Optional Brain vault

PAIO can use an Obsidian-compatible vault for persistent memory and retrieval.

Common locations include:

```text
D:\Brain
D:\Brain\
~/Brain
```

If PAIO cannot find the vault, it asks for the path during startup.

Obsidian is optional. PAIO can run without a vault, but long-term memory and RAG features will be limited.

---

## Configuration and generated files

PAIO may create local runtime files such as:

```text
config.json
session_state.json
paio.log
.env
```

These files contain local configuration, logs, credentials, or personal information. Do not commit them.

---

## Building an executable

PyInstaller must be run on the same operating system as the target executable.

### Windows

```powershell
.\build_windows.bat
```

Output:

```text
dist\PAIO-Omni\PAIO-Omni.exe
```

### Linux

```bash
chmod +x build_linux.sh
./build_linux.sh
```

Output:

```text
dist/PAIO-Omni/PAIO-Omni
```

### macOS

```bash
chmod +x build_macos.sh
./build_macos.sh
```

Output:

```text
dist/PAIO-Omni/PAIO-Omni
```

Piper assets must be present before building if you want TTS included in the generated application.

Copy the real `.env` into the distribution directory after building if cloud services are needed. Do not bake secrets into the executable.

On macOS, Gatekeeper may block an unsigned build the first time. You may need to right-click the application and choose **Open**.

---

## Troubleshooting

### `Piper executable not found`

Verify that one of these exists:

```text
models/piper/piper.exe
models/piper/piper
```

Also check the `PAIO_PIPER_EXE` environment variable.

### `Piper model not found`

Verify that this file exists:

```text
models/piper/en_US-bryce-medium.onnx
```

### `Piper config not found`

Verify that this file exists:

```text
models/piper/en_US-bryce-medium.onnx.json
```

The JSON file must match the `.onnx` voice model.

### `Ollama connection refused`

Start Ollama:

```bash
ollama serve
```

Then test:

```bash
ollama list
```

### `paio` command not found

Activate the virtual environment and reinstall:

```bash
python -m pip install -e .
```

Then try:

```bash
python -m paio.cli
```

### No microphone input

Check that:

- The microphone is connected.
- The operating system granted microphone permission.
- No other application has exclusive access to the microphone.
- The correct input device is selected.

### No audio output

Check that:

- Speakers or headphones are connected.
- The output device is selected correctly.
- The manually generated `paio-test.wav` plays successfully.
- `sounddevice` and `soundfile` installed correctly.

---

## Project files

| File | Purpose |
|---|---|
| `onboarding.py` | Guided setup and configuration |
| `orchestrator.py` | Main PAIO application |
| `tts.py` | Piper text-to-speech |
| `stt.py` | Whisper speech-to-text |
| `llm.py` | Local Ollama client |
| `cloud_llm.py` | Cloud-compatible LLM clients |
| `router.py` | Provider fallback routing |
| `ensemble.py` | Multi-model answering |
| `jev_router.py` | Role and complexity classification |
| `wakeword.py` | Wake-word and barge-in detection |
| `wakeword_train.py` | Custom wake-word training |
| `memory.py` | Persistent memory and session state |
| `rag.py` | Vault indexing and retrieval |
| `hardware.py` | Hardware detection and model selection |
| `config.py` | Runtime configuration |
| `paio/cli.py` | `paio` command-line entry point |

---

## Offline behavior

The local offline path requires:

```text
Ollama installed
Ollama running
At least one local Ollama model downloaded
Piper executable installed
Piper voice model installed
Whisper dependencies installed
```

Cloud providers are optional and are only used when configured.

The first installation may require internet access to download:

- Python packages
- Ollama
- Ollama models
- Piper
- Piper voice models
- Whisper models
- RAG embedding models

After those files are downloaded, local PAIO operation can run without cloud APIs.

---

## License

See the repository license and included project files for licensing information.
