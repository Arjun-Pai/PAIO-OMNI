# PAIO-Omni · onboarding.py
"""
The single entry point for installing and configuring PAIO-Omni.

Run this first:

    python onboarding.py

Or, after installing the package:

    paio setup

The setup process:

1. Installs missing Python packages.
2. Checks, installs, and starts Ollama where possible.
3. Checks Piper TTS executable and voice files.
4. Tests optional API keys.
5. Configures model priority lists.
6. Downloads local Ollama models for the detected hardware tier.
7. Offers to launch PAIO.
"""

from __future__ import annotations

import importlib
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

import config


try:
    from PySide6.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QDialog,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QPushButton,
        QVBoxLayout,
    )

    _QT = True
except ImportError:
    _QT = False


_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
_MAX_CANDIDATES = 12

_FALLBACK_OPENROUTER_FREE = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-coder-32b-instruct:free",
    "google/gemma-2-9b-it:free",
]

# Ollama Cloud has no confirmed public "list all cloud models" endpoint.
# This is a maintained list of model tags.
OLLAMA_CLOUD_CANDIDATES = [
    {"id": "kimi-k2.6:cloud", "role": "creative"},
    {"id": "minimax-m3:cloud", "role": "general"},
    {"id": "glm-5.1:cloud", "role": "general"},
    {"id": "qwen3.5:cloud", "role": "deep"},
    {"id": "deepseek-v4-flash:cloud", "role": "fast"},
    {"id": "nemotron-3-super:cloud", "role": "deep"},
    {"id": "nemotron-3-ultra:cloud", "role": "deep"},
    {"id": "qwen3-coder:480b-cloud", "role": "coder"},
    {"id": "mistral-large-3:675b-cloud", "role": "deep"},
]

_ROLE_HINTS = [
    ("coder", ["coder", "code", "starcoder", "codestral"]),
    ("scientist", ["math", "reasoning", "r1", "qwq", "o1", "thinking"]),
    ("creative", ["creative", "story", "hermes", "dolphin"]),
    ("teacher", ["instruct", "chat", "it"]),
    ("fast", ["mini", "small", "flash", "lite"]),
    ("deep", ["large", "70b", "72b", "405b", "maverick", "scout"]),
]


_REQUIRED_PACKAGES = {
    "faster_whisper": "faster-whisper",
    "sounddevice": "sounddevice",
    "soundfile": "soundfile",
    "numpy": "numpy",
    "requests": "requests",
    "psutil": "psutil",
    "openai": "openai",
    "dotenv": "python-dotenv",
    "pynput": "pynput",
    "PySide6": "PySide6",
    "sentence_transformers": "sentence-transformers",
    "chromadb": "chromadb",
}

_OPTIONAL_PACKAGES = {
    "violawake_sdk": "violawake[audio,download]",
}


# ------------------------------------------------------------------ #
# 1. Python packages
# ------------------------------------------------------------------ #

def _ensure_pip_packages() -> bool:
    """Install missing Python dependencies."""
    missing = []

    for module_name, pip_name in _REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(pip_name)

    if missing:
        print(f"  Installing missing packages: {', '.join(missing)} ...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", *missing],
            check=False,
        )

        if result.returncode != 0:
            print("  Warning: one or more required packages failed to install.")
            return False

    for module_name, pip_name in _OPTIONAL_PACKAGES.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            print(
                f"  (optional) installing {pip_name} "
                "for voice wake-word support ..."
            )
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", pip_name],
                check=False,
            )

            if result.returncode != 0:
                print(
                    f"  Warning: optional package {pip_name} "
                    "could not be installed."
                )

    return True


# ------------------------------------------------------------------ #
# 2. Ollama install / serve / cloud sign-in
# ------------------------------------------------------------------ #

def _ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def _install_ollama():
    system = platform.system()

    print("  Ollama not found — attempting installation ...")

    if system == "Windows":
        if shutil.which("winget"):
            result = subprocess.run(
                [
                    "winget",
                    "install",
                    "-e",
                    "--id",
                    "Ollama.Ollama",
                    "--silent",
                ],
                check=False,
            )

            if result.returncode != 0:
                print("  winget could not install Ollama.")
        else:
            print("  winget was not found.")
            print(
                "  Install Ollama manually from: "
                "https://ollama.com/download/windows"
            )

    elif system == "Darwin":
        if shutil.which("brew"):
            result = subprocess.run(
                ["brew", "install", "ollama"],
                check=False,
            )

            if result.returncode != 0:
                print("  Homebrew could not install Ollama.")
        else:
            print("  Homebrew was not found.")
            print(
                "  Install Ollama manually from: "
                "https://ollama.com/download/mac"
            )

    elif system == "Linux":
        print("  Running the official Ollama install script ...")

        result = subprocess.run(
            [
                "sh",
                "-c",
                "curl -fsSL https://ollama.com/install.sh | sh",
            ],
            check=False,
        )

        if result.returncode != 0:
            print("  The Ollama installation script failed.")

    else:
        print(f"  Unrecognized operating system: {system}")
        print("  Install Ollama manually from: https://ollama.com/download")


def _ollama_running() -> bool:
    try:
        response = requests.get(
            "http://localhost:11434/api/tags",
            timeout=2,
        )
        return response.status_code == 200
    except Exception:
        return False


def _start_ollama_serve():
    print("  Starting Ollama in the background ...")

    kwargs = {}

    if platform.system() == "Windows":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )
    except Exception as exc:
        print(f"  Could not start Ollama automatically: {exc}")
        return

    for _ in range(20):
        if _ollama_running():
            print("  ✓ Ollama is running.")
            return

        time.sleep(0.5)

    print("  Ollama did not become available in time.")
    print("  You can start it manually with: ollama serve")


def _ollama_cloud_signin() -> bool:
    print("\n  Ollama Cloud sign-in is optional.")
    print("  Signing in opens a browser once.")

    answer = input("  Sign in to Ollama Cloud now? [Y/n] ").strip().lower()

    if answer == "n":
        print("  Skipping Ollama Cloud sign-in.")
        print("  You can run 'ollama signin' later.")
        return False

    try:
        result = subprocess.run(
            ["ollama", "signin"],
            check=False,
        )

        if result.returncode == 0:
            print("  ✓ Signed in to Ollama Cloud.")
            return True

        print("  Ollama Cloud sign-in did not complete successfully.")
        return False

    except Exception as exc:
        print(f"  Could not run 'ollama signin': {exc}")
        return False


# ------------------------------------------------------------------ #
# 3. Piper TTS setup and validation
# ------------------------------------------------------------------ #

def _piper_paths() -> dict[str, Path]:
    """Return platform-aware Piper executable and voice paths."""
    base_dir = Path(__file__).resolve().parent
    piper_dir = base_dir / "models" / "piper"

    configured_exe = os.environ.get("PAIO_PIPER_EXE")
    configured_model = os.environ.get("PAIO_PIPER_MODEL")
    configured_config = os.environ.get("PAIO_PIPER_CONFIG")

    if platform.system() == "Windows":
        executable_candidates = [
            piper_dir / "piper.exe",
            piper_dir / "piper" / "piper.exe",
        ]
    else:
        executable_candidates = [
            piper_dir / "piper",
            piper_dir / "piper" / "piper",
        ]

    model_candidates = [
        piper_dir / "en_US-bryce-medium.onnx",
        piper_dir / "mv2.onnx",
        piper_dir / "piper" / "en_US-bryce-medium.onnx",
        piper_dir / "piper" / "mv2.onnx",
    ]

    executable = (
        Path(configured_exe)
        if configured_exe
        else next(
            (
                path
                for path in executable_candidates
                if path.is_file()
            ),
            executable_candidates[0],
        )
    )

    model = (
        Path(configured_model)
        if configured_model
        else next(
            (
                path
                for path in model_candidates
                if path.is_file()
            ),
            model_candidates[0],
        )
    )

    if configured_config:
        config_path = Path(configured_config)
    else:
        config_candidates = [
            Path(f"{model}.json"),
            piper_dir / "en_US-bryce-medium.onnx.json",
            piper_dir / "piper" / "en_US-bryce-medium.onnx.json",
        ]

        config_path = next(
            (
                path
                for path in config_candidates
                if path.is_file()
            ),
            config_candidates[0],
        )

    return {
        "directory": piper_dir,
        "executable": executable,
        "model": model,
        "config": config_path,
    }


def _print_piper_install_help():
    system = platform.system()

    print("\n[Piper] Piper TTS assets are required for voice output.")
    print("Expected files:")

    if system == "Windows":
        print("  models/piper/piper.exe")
        print("  models/piper/*.dll")
    else:
        print("  models/piper/piper")

    print("  models/piper/en_US-bryce-medium.onnx")
    print("  models/piper/en_US-bryce-medium.onnx.json")

    if system == "Windows":
        print(
            "\nDownload the Piper Windows release and place "
            "piper.exe and its DLL files inside models/piper/."
        )
    elif system == "Darwin":
        print(
            "\nDownload the Piper macOS executable and place it "
            "inside models/piper/."
        )
        print("Then run: chmod +x models/piper/piper")
    else:
        print(
            "\nDownload the Piper Linux executable and place it "
            "inside models/piper/."
        )
        print("Then run: chmod +x models/piper/piper")

    print("\nThe .onnx and .onnx.json files must belong to the same voice.")
    print("See README.md for complete Piper setup instructions.")


def _check_piper_assets() -> bool:
    paths = _piper_paths()

    print("\n[Piper] Checking Piper TTS assets ...")
    print(f"  Executable: {paths['executable']}")
    print(f"  Model:      {paths['model']}")
    print(f"  Config:     {paths['config']}")

    missing = []

    if not paths["executable"].is_file():
        missing.append("Piper executable")

    if not paths["model"].is_file():
        missing.append("Piper voice model")

    if not paths["config"].is_file():
        missing.append("Piper voice configuration")

    if missing:
        print(f"  Missing: {', '.join(missing)}")
        _print_piper_install_help()
        return False

    if platform.system() != "Windows":
        try:
            current_mode = paths["executable"].stat().st_mode
            paths["executable"].chmod(current_mode | 0o111)
        except OSError as exc:
            print(
                "  Warning: could not set Piper executable permission: "
                f"{exc}"
            )

    print("  Piper assets found.")
    return True


def _test_piper() -> bool:
    """Run a short Piper synthesis test."""
    paths = _piper_paths()

    required_paths = (
        paths["executable"],
        paths["model"],
        paths["config"],
    )

    if not all(path.is_file() for path in required_paths):
        return False

    output_path = Path(config.get_runtime_dir()) / "paio-piper-test.wav"

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [
                str(paths["executable"]),
                "--model",
                str(paths["model"]),
                "--config",
                str(paths["config"]),
                "--output_file",
                str(output_path),
            ],
            input=b"PAIO Piper test.",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )

        if result.returncode == 0 and output_path.is_file():
            print("  Piper test passed.")

            try:
                output_path.unlink()
            except OSError:
                pass

            return True

        print("  Piper test failed.")

        if result.stderr:
            error_text = result.stderr.decode(
                "utf-8",
                errors="replace",
            )
            print(error_text[:500])

        return False

    except Exception as exc:
        print(f"  Piper test could not run: {exc}")
        return False

    finally:
        if output_path.exists():
            try:
                output_path.unlink()
            except OSError:
                pass


def _setup_piper() -> bool:
    print("\n[Setup] Piper TTS ...")

    if not _check_piper_assets():
        print(
            "  Setup will continue, but PAIO voice output "
            "will remain unavailable."
        )
        return False

    return _test_piper()


# ------------------------------------------------------------------ #
# 4. API keys
# ------------------------------------------------------------------ #

def _test_openai_compatible(
    base_url: str,
    api_key: str,
    model: str,
    extra_headers: dict | None = None,
) -> tuple[bool, str]:
    """Return (success, detail)."""
    try:
        from openai import OpenAI

        client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            default_headers=extra_headers or {},
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": "hi",
                }
            ],
            max_tokens=5,
        )

        content = response.choices[0].message.content or ""
        return True, content[:40]

    except Exception as exc:
        return False, str(exc)[:200]


def _test_typesafe(api_key: str) -> tuple[bool, str]:
    try:
        response = requests.post(
            "https://api.typesafe.ai/v1/systemone",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "jev-latest",
                "state": "hello",
                "questions": {
                    "role": {
                        "type": "choice",
                        "instructions": "pick one",
                        "criteria": {
                            "a": "option a",
                            "b": "option b",
                        },
                    }
                },
            },
            timeout=6,
        )

        response.raise_for_status()
        return True, "reachable"

    except Exception as exc:
        return False, str(exc)[:200]


def _ask_key(label: str, env_var: str, signup_hint: str) -> str:
    print(f"\n  {label}")
    print(f"  ({signup_hint})")
    return input(
        f"  Paste your {env_var} "
        "(blank to skip): "
    ).strip()


def _run_key_setup() -> dict[str, str]:
    print(
        "\n[Setup] API keys — each key is tested live "
        "after entry.\n"
    )

    env_values = {}
    results = []

    zenmux_key = _ask_key(
        "ZenMux (primary — optional)",
        "ZENMUX_API_KEY",
        "sign up at zenmux.ai",
    )

    if zenmux_key:
        ok, detail = _test_openai_compatible(
            "https://zenmux.ai/api/v1",
            zenmux_key,
            "z-ai/glm-5.3-free",
        )

        results.append(("ZenMux", ok, detail))
        env_values["ZENMUX_API_KEY"] = zenmux_key

    openrouter_key = _ask_key(
        "OpenRouter (optional)",
        "OPENROUTER_API_KEY",
        "openrouter.ai -> API keys",
    )

    if openrouter_key:
        ok, detail = _test_openai_compatible(
            "https://openrouter.ai/api/v1",
            openrouter_key,
            "meta-llama/llama-3.3-70b-instruct:free",
            extra_headers={
                "HTTP-Referer": "https://paio-omni.local",
                "X-Title": "PAIO-Omni",
            },
        )

        results.append(("OpenRouter", ok, detail))
        env_values["OPENROUTER_API_KEY"] = openrouter_key

    groq_key = _ask_key(
        "Groq Cloud (optional)",
        "GROQ_API_KEY",
        "console.groq.com -> API Keys",
    )

    if groq_key:
        ok, detail = _test_openai_compatible(
            "https://api.groq.com/openai/v1",
            groq_key,
            "llama-3.3-70b-versatile",
        )

        results.append(("Groq", ok, detail))
        env_values["GROQ_API_KEY"] = groq_key

    typesafe_key = _ask_key(
        "TypeSafe / Jev (optional)",
        "TYPESAFE_API_KEY",
        "your TypeSafe account",
    )

    if typesafe_key:
        ok, detail = _test_typesafe(typesafe_key)
        results.append(("TypeSafe/Jev", ok, detail))
        env_values["TYPESAFE_API_KEY"] = typesafe_key

    print("\n[Setup] Key test results:")

    if not results:
        print("    No cloud API keys configured.")
    else:
        for name, ok, detail in results:
            status = "✓ OK" if ok else "✗ FAILED"
            print(f"    {status}  {name}  —  {detail}")

    _write_env(env_values)
    return env_values


def _write_env(env_values: dict[str, str]):
    env_path = Path(config.get_runtime_dir()) / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []

    if "ZENMUX_API_KEY" in env_values:
        lines += [
            "ZENMUX_API_BASE=https://zenmux.ai/api/v1",
            f"ZENMUX_API_KEY={env_values['ZENMUX_API_KEY']}",
            "ZENMUX_MODEL=z-ai/glm-5.3-free",
        ]

    if "OPENROUTER_API_KEY" in env_values:
        lines += [
            "OPENROUTER_API_BASE=https://openrouter.ai/api/v1",
            f"OPENROUTER_API_KEY={env_values['OPENROUTER_API_KEY']}",
        ]

    if "GROQ_API_KEY" in env_values:
        lines += [
            "GROQ_API_BASE=https://api.groq.com/openai/v1",
            f"GROQ_API_KEY={env_values['GROQ_API_KEY']}",
        ]

    if "TYPESAFE_API_KEY" in env_values:
        lines.append(
            f"TYPESAFE_API_KEY={env_values['TYPESAFE_API_KEY']}"
        )

    with env_path.open("w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")

    print(f"\n  Wrote {env_path}")


# ------------------------------------------------------------------ #
# 5. Live model fetch and priority dialogs
# ------------------------------------------------------------------ #

def _guess_role(model_id: str) -> str:
    lower = model_id.lower()

    for role, keywords in _ROLE_HINTS:
        if any(keyword in lower for keyword in keywords):
            return role

    return "general"


def fetch_openrouter_candidates(api_key: str = "") -> list[dict]:
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        response = requests.get(
            _OPENROUTER_MODELS_URL,
            headers=headers,
            timeout=8,
        )
        response.raise_for_status()

        data = response.json().get("data", [])

    except Exception as exc:
        print(
            "  [onboarding] Could not fetch OpenRouter models live "
            f"({exc}); using fallback models."
        )

        return [
            {
                "id": model,
                "role": _guess_role(model),
            }
            for model in _FALLBACK_OPENROUTER_FREE
        ]

    free = [
        model
        for model in data
        if str(model.get("pricing", {}).get("prompt", "1")) == "0"
        and str(model.get("pricing", {}).get("completion", "1")) == "0"
    ]

    seen_roles = set()
    picked = []

    for model in free:
        model_id = model.get("id")

        if not model_id:
            continue

        role = _guess_role(model_id)

        if (
            role not in seen_roles
            or len(picked) < _MAX_CANDIDATES // 2
        ):
            picked.append(
                {
                    "id": model_id,
                    "role": role,
                }
            )
            seen_roles.add(role)

        if len(picked) >= _MAX_CANDIDATES:
            break

    if len(picked) < _MAX_CANDIDATES:
        for model in free:
            model_id = model.get("id")

            if not model_id:
                continue

            if len(picked) >= _MAX_CANDIDATES:
                break

            if not any(item["id"] == model_id for item in picked):
                picked.append(
                    {
                        "id": model_id,
                        "role": _guess_role(model_id),
                    }
                )

    return picked[:_MAX_CANDIDATES] or [
        {
            "id": model,
            "role": _guess_role(model),
        }
        for model in _FALLBACK_OPENROUTER_FREE
    ]


def fetch_groq_candidates(api_key: str) -> list[dict]:
    if not api_key:
        return [
            {
                "id": "llama-3.3-70b-versatile",
                "role": "deep",
            }
        ]

    try:
        response = requests.get(
            _GROQ_MODELS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
            },
            timeout=8,
        )
        response.raise_for_status()

        data = response.json().get("data", [])

    except Exception as exc:
        print(
            "  [onboarding] Could not fetch Groq models live "
            f"({exc}); using llama-3.3-70b-versatile."
        )

        return [
            {
                "id": "llama-3.3-70b-versatile",
                "role": "deep",
            }
        ]

    ids = [
        model.get("id")
        for model in data
        if "whisper" not in model.get("id", "").lower()
        and model.get("id")
    ]

    picked = [
        {
            "id": model_id,
            "role": _guess_role(model_id),
        }
        for model_id in ids[:_MAX_CANDIDATES]
    ]

    return picked or [
        {
            "id": "llama-3.3-70b-versatile",
            "role": "deep",
        }
    ]


def fetch_ollama_cloud_candidates() -> list[dict]:
    return list(OLLAMA_CLOUD_CANDIDATES)


class _PriorityDialog(QDialog):
    def __init__(self, title: str, candidates: list[dict]):
        super().__init__()

        self.setWindowTitle(title)
        self.resize(420, 480)

        layout = QVBoxLayout(self)

        layout.addWidget(
            QLabel(
                f"{title}\n"
                "Drag to reorder — top runs first. "
                "Each item below is a fallback."
            )
        )

        self.list_widget = QListWidget(self)
        self.list_widget.setDragDropMode(
            QAbstractItemView.InternalMove
        )

        for candidate in candidates:
            item = QListWidgetItem(
                f"{candidate['id']} [{candidate['role']}]"
            )
            item.setData(1000, candidate["id"])
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

        buttons = QHBoxLayout()
        save_button = QPushButton("Save order")
        save_button.clicked.connect(self.accept)
        buttons.addWidget(save_button)

        layout.addLayout(buttons)

    def ordered_ids(self) -> list[str]:
        return [
            self.list_widget.item(index).data(1000)
            for index in range(self.list_widget.count())
        ]


def _run_priority_dialogs(env_values: dict[str, str]) -> None:
    print("\n[Setup] Model priority configuration.\n")

    openrouter_candidates = fetch_openrouter_candidates(
        env_values.get("OPENROUTER_API_KEY", "")
    )
    groq_candidates = fetch_groq_candidates(
        env_values.get("GROQ_API_KEY", "")
    )
    ollama_cloud_candidates = fetch_ollama_cloud_candidates()

    cfg = config.load_user_config()

    if not _QT:
        print(
            "  PySide6 is not available. "
            "Saving fetched model order without dialogs."
        )

        cfg["openrouter_model_priority"] = [
            candidate["id"]
            for candidate in openrouter_candidates
        ]
        cfg["groq_model_priority"] = [
            candidate["id"]
            for candidate in groq_candidates
        ]
        cfg["ollama_cloud_model_priority"] = [
            candidate["id"]
            for candidate in ollama_cloud_candidates
        ]

    else:
        app = QApplication.instance() or QApplication([])

        groups = (
            (
                "openrouter_model_priority",
                "OpenRouter model priority",
                openrouter_candidates,
            ),
            (
                "groq_model_priority",
                "Groq model priority",
                groq_candidates,
            ),
            (
                "ollama_cloud_model_priority",
                "Ollama Cloud model priority",
                ollama_cloud_candidates,
            ),
        )

        for key, title, candidates in groups:
            dialog = _PriorityDialog(title, candidates)
            dialog.exec()
            cfg[key] = dialog.ordered_ids()

    config.save_user_config(cfg)

    print(
        "  Saved priority lists: "
        f"OpenRouter ({len(cfg['openrouter_model_priority'])}), "
        f"Groq ({len(cfg['groq_model_priority'])}), "
        "Ollama Cloud "
        f"({len(cfg['ollama_cloud_model_priority'])})"
    )


# ------------------------------------------------------------------ #
# 6. Local model download
# ------------------------------------------------------------------ #

def _free_disk_gb(path: str = ".") -> float:
    try:
        return shutil.disk_usage(path).free / (1024 ** 3)
    except Exception:
        return -1.0


def _already_installed_models() -> set[str]:
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        return {
            line.split()[0]
            for line in result.stdout.splitlines()[1:]
            if line.strip()
        }

    except Exception:
        return set()


def _pull_full_tier():
    import hardware

    hw = hardware.detect()
    tier = hw["tier"]
    wanted = hardware.all_models_for_tier(tier)

    installed = _already_installed_models()
    missing = [
        model
        for model in wanted
        if model not in installed
    ]

    if not missing:
        print(
            f"  ✓ All {len(wanted)} models for tier "
            f"'{tier}' are already installed."
        )
        return

    free_gb = _free_disk_gb()
    estimated_gb = len(missing) * 12

    print(
        f"\n  Tier '{tier}' needs {len(missing)} more model(s)."
    )
    print(
        f"  Estimated additional disk usage: approximately "
        f"{estimated_gb} GB."
    )

    if free_gb >= 0:
        print(f"  Free disk space: {free_gb:.0f} GB")

        if free_gb < estimated_gb:
            print(
                "  Warning: the rough estimate is larger than "
                "your available disk space."
            )

    answer = input(
        "  Download all missing models now? [y/N] "
    ).strip().lower()

    if answer != "y":
        print("  Skipping bulk download.")
        print("  Re-run onboarding.py anytime to resume.")
        print("  Or pull an individual model with:")
        print("    ollama pull <model>")
        return

    for index, model in enumerate(missing, 1):
        print(
            f"\n  [{index}/{len(missing)}] "
            f"Pulling {model} ..."
        )
        subprocess.run(
            ["ollama", "pull", model],
            check=False,
        )


# ------------------------------------------------------------------ #
# Entry point
# ------------------------------------------------------------------ #

def run_full_setup():
    print("PAIO-Omni — setup\n")

    print("[1/6] Python packages ...")
    _ensure_pip_packages()

    print("\n[2/6] Ollama install + cloud sign-in ...")

    if not _ollama_installed():
        _install_ollama()
    else:
        print("  ✓ Ollama already installed.")

    if _ollama_installed():
        if not _ollama_running():
            _start_ollama_serve()
        else:
            print("  ✓ Ollama already running.")

        _ollama_cloud_signin()
    else:
        print("  Ollama is unavailable.")
        print("  Install Ollama manually before using local models.")

    print("\n[3/6] Piper TTS ...")
    _setup_piper()

    print("\n[4/6] API keys ...")
    env_values = _run_key_setup()

    print("\n[5/6] Model priorities ...")
    _run_priority_dialogs(env_values)

    print("\n[6/6] Local model tier download ...")

    if _ollama_installed():
        _pull_full_tier()
    else:
        print("  Skipping — Ollama is not installed.")

    print("\nSetup complete.")

    answer = input("Launch PAIO now? [Y/n] ").strip().lower()

    if answer != "n":
        import orchestrator

        orchestrator.run()


if __name__ == "__main__":
    run_full_setup()
