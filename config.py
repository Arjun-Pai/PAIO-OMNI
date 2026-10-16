"""PAIO-Omni runtime configuration.

User-writable files are stored outside the installed package whenever possible.

Environment override:

    PAIO_DATA_DIR=/custom/path

Default locations:

Windows:
    %LOCALAPPDATA%/PAIO-Omni

macOS:
    ~/Library/Application Support/PAIO-Omni

Linux:
    $XDG_DATA_HOME/paio-omni
    or ~/.local/share/paio-omni
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path


def _source_dir() -> Path:
    return Path(__file__).resolve().parent


def get_runtime_dir() -> str:
    """Return the directory used for PAIO user data and runtime files."""
    override = os.environ.get("PAIO_DATA_DIR")

    if override:
        path = Path(override).expanduser()
    else:
        system = platform.system()

        if system == "Windows":
            local_app_data = os.environ.get("LOCALAPPDATA")

            if local_app_data:
                path = Path(local_app_data) / "PAIO-Omni"
            else:
                path = Path.home() / "AppData" / "Local" / "PAIO-Omni"

        elif system == "Darwin":
            path = (
                Path.home()
                / "Library"
                / "Application Support"
                / "PAIO-Omni"
            )

        else:
            xdg_data_home = os.environ.get("XDG_DATA_HOME")

            if xdg_data_home:
                path = Path(xdg_data_home) / "paio-omni"
            else:
                path = Path.home() / ".local" / "share" / "paio-omni"

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        # Source checkouts may be running in an environment where the
        # platform data directory is unavailable. Preserve compatibility
        # with the original repository layout as a fallback.
        fallback = _source_dir()
        print(
            f"  [config] could not create runtime directory {path}: {exc}"
        )
        print(f"  [config] using source directory instead: {fallback}")
        return str(fallback)

    return str(path)


def get_runtime_path(filename: str) -> str:
    return str(Path(get_runtime_dir()) / filename)


# ---- Ollama -----------------------------------------------------------

OLLAMA_URL = "http://localhost:11434"


# ---- Audio / VAD ------------------------------------------------------

SAMPLE_RATE = 16000
VAD_THRESHOLD = 0.015
SILENCE_DURATION = 1.8
MAX_RECORD_SECS = 30


# ---- Conversation memory ----------------------------------------------

MAX_HISTORY_TURNS = 6


# ---- Token compaction --------------------------------------------------

MAX_RESPONSE_TOKENS = 700
COMPACT_AT_FRACTION = 0.90


# ---- Vault / memory ----------------------------------------------------

DEFAULT_VAULT_CANDIDATES = [
    r"D:\Brain",
    r"D:/Brain",
    str(Path.home() / "Brain"),
]


# ---- Wake word / hotkey ------------------------------------------------

HOTKEY = "home"
WAKE_MODEL = str(_source_dir() / "models" / "hey_paio.onnx")
WAKE_THRESHOLD = 0.80
WAKE_CONFIRM_COUNT = 3


# ---- Runtime paths -----------------------------------------------------

USER_CONFIG_PATH = Path(get_runtime_path("config.json"))
SESSION_STATE_PATH = Path(get_runtime_path("session_state.json"))
LOG_PATH = Path(get_runtime_path("paio.log"))
ENV_PATH = Path(get_runtime_path(".env"))


# ---- Defaults written to config.json on first run ----------------------

_DEFAULTS = {
    "vault_path": None,
    "hotkey": HOTKEY,
    "mic_threshold": None,
    "mic_device_index": None,
    "cloud_provider_preference": None,
    "openrouter_model_priority": [],
    "groq_model_priority": [],
    "ollama_cloud_model_priority": [],
}


def load_user_config() -> dict:
    if USER_CONFIG_PATH.exists():
        try:
            with USER_CONFIG_PATH.open("r", encoding="utf-8") as file:
                data = json.load(file)

            merged = dict(_DEFAULTS)
            merged.update(data)
            return merged

        except Exception as exc:
            print(f"  [config] could not read config.json: {exc}")

    return dict(_DEFAULTS)


def save_user_config(cfg: dict) -> None:
    try:
        USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

        with USER_CONFIG_PATH.open("w", encoding="utf-8") as file:
            json.dump(cfg, file, indent=2)

    except Exception as exc:
        print(f"  [config] could not save config.json: {exc}")
