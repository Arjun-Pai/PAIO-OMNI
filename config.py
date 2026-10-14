# PAIO-Omni · config.py  v3.1
import json
import os

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_CONFIG_PATH = os.path.join(_BASE_DIR, "config.json")

# ---- Ollama (local, offline fallback) --------------------------------
OLLAMA_URL = "http://localhost:11434"

# ---- Audio / VAD -------------------------------------------------------
SAMPLE_RATE      = 16000
VAD_THRESHOLD    = 0.015     # overwritten by mic calibration on first run
SILENCE_DURATION = 1.8
MAX_RECORD_SECS  = 30

# ---- Conversation memory (in-RAM turns kept verbatim for Ollama) -------
MAX_HISTORY_TURNS = 6

# ---- Token compaction ----------------------------------------------
# When a response reaches this fraction of MAX_RESPONSE_TOKENS, generation
# is stopped and wrapped into one final sentence instead of hard-cutting.
MAX_RESPONSE_TOKENS   = 700
COMPACT_AT_FRACTION   = 0.90

# ---- Vault / memory (Obsidian "Brain" vault) ---------------------------
DEFAULT_VAULT_CANDIDATES = [
    r"D:\Brain",
    r"D:/Brain",
    os.path.join(os.path.expanduser("~"), "Brain"),
]

# ---- Wake word / hotkey -------------------------------------------------
# v3.1: swapped from openWakeWord to ViolaWake — see wakeword_train.py for
# why (openWakeWord's own custom-training pipeline is broken/unmaintained
# as of 2026; ViolaWake is the modern, simpler, actively-maintained
# alternative, built for exactly "train from a handful of real
# recordings"). WAKE_MODEL points at the model trained from voices/.
HOTKEY               = "home"     # push-to-talk key (hold to record, release to send)
WAKE_MODEL           = os.path.join(_BASE_DIR, "models", "hey_paio.onnx")
WAKE_THRESHOLD       = 0.80       # ViolaWake's own recommended default
WAKE_CONFIRM_COUNT   = 3          # consecutive above-threshold frames required to fire

# ---- Defaults written to config.json on first run -----------------------
_DEFAULTS = {
    "vault_path": None,          # resolved on first successful boot
    "hotkey": HOTKEY,
    "mic_threshold": None,       # set by first-run calibration
    "mic_device_index": None,
    "cloud_provider_preference": None,  # "openrouter" | "groq" | "ollama" once chosen
}


def load_user_config() -> dict:
    if os.path.exists(_USER_CONFIG_PATH):
        try:
            with open(_USER_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(_DEFAULTS)
            merged.update(data)
            return merged
        except Exception:
            pass
    return dict(_DEFAULTS)


def save_user_config(cfg: dict) -> None:
    try:
        with open(_USER_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"  [config] could not save config.json: {e}")
