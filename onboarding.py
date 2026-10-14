# PAIO-Omni · onboarding.py  v3.2
"""
The single entry point — replaces launcher.py entirely. Run this first,
and re-run it anytime you want to change any setting: API keys, model
priority order, or hardware-tier models. Nothing else in this project
handles setup or reconfiguration.

What it does, in order:
  1. Installs missing Python packages.
  2. Installs Ollama if missing, starts it, signs in for Ollama Cloud.
  3. Asks for each API key interactively (ZenMux, OpenRouter, Groq,
     TypeSafe/Jev), tests each one live with a real minimal request,
     and writes .env itself.
  4. Fetches live model lists (OpenRouter, Groq) and shows a drag-to-
     reorder dialog for each, plus Ollama Cloud (a maintained-by-hand
     list — no confirmed public catalog endpoint exists for that one,
     unlike OpenRouter/Groq which do; see fetch_ollama_cloud_candidates).
     ZenMux gets no dialog — it's a single hand-picked endpoint, not a
     ranked list.
  5. Checks disk space, then pulls all 13 models for your detected
     hardware tier.
  6. Offers to launch PAIO immediately.
"""

import importlib
import os
import platform
import shutil
import subprocess
import sys
import time

import requests

import config

try:
    from PySide6.QtWidgets import (
        QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QListWidget, QListWidgetItem, QPushButton, QAbstractItemView,
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

# Ollama Cloud has no confirmed public "list all cloud models" endpoint
# (unlike OpenRouter/Groq, which both document a real /models route) —
# so unlike those two, this is a maintained-by-hand list of tags
# verified real and non-deprecated as of this build, not a live fetch.
# Update this list by hand if Ollama's cloud roster changes.
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

def _ensure_pip_packages():
    missing = []
    for module_name, pip_name in _REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(pip_name)
    if missing:
        print(f"  Installing missing packages: {', '.join(missing)} ...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", *missing])

    for module_name, pip_name in _OPTIONAL_PACKAGES.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            print(f"  (optional) installing {pip_name} for voice wake-word support ...")
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", pip_name])


# ------------------------------------------------------------------ #
# 2. Ollama install / serve / cloud sign-in
# ------------------------------------------------------------------ #

def _ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def _install_ollama():
    system = platform.system()
    print("  Ollama not found — attempting install ...")
    if system == "Windows":
        if shutil.which("winget"):
            subprocess.run(["winget", "install", "-e", "--id", "Ollama.Ollama", "--silent"])
        else:
            print("  Couldn't auto-install (winget not found). Install manually: "
                  "https://ollama.com/download/windows")
    elif system == "Darwin":
        if shutil.which("brew"):
            subprocess.run(["brew", "install", "ollama"])
        else:
            print("  Couldn't auto-install (Homebrew not found). Install manually: "
                  "https://ollama.com/download/mac")
    elif system == "Linux":
        print("  Running the official Ollama install script ...")
        subprocess.run(["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"])
    else:
        print(f"  Unrecognized OS ({system}) — install manually: https://ollama.com/download")


def _ollama_running() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _start_ollama_serve():
    print("  Starting Ollama in the background ...")
    kwargs = {}
    if platform.system() == "Windows":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, **kwargs)
    except Exception as e:
        print(f"  Could not start Ollama automatically: {e}")
        return
    for _ in range(20):
        if _ollama_running():
            print("  ✓ Ollama is up.")
            return
        time.sleep(0.5)
    print("  Ollama didn't come up in time.")


def _ollama_cloud_signin():
    print("\n  Ollama Cloud needs you signed in once — this opens a browser.")
    answer = input("  Sign in now? [Y/n] ").strip().lower()
    if answer == "n":
        print("  Skipping — Ollama Cloud models won't be usable until you run "
              "'ollama signin' yourself.")
        return False
    try:
        result = subprocess.run(["ollama", "signin"])
        if result.returncode == 0:
            print("  ✓ Signed in to Ollama Cloud.")
            return True
        print("  Sign-in didn't complete successfully — Ollama Cloud may not work yet.")
        return False
    except Exception as e:
        print(f"  Could not run 'ollama signin': {e}")
        return False


# ------------------------------------------------------------------ #
# 3. API keys — ask, test live, write .env
# ------------------------------------------------------------------ #

def _test_openai_compatible(base_url: str, api_key: str, model: str, extra_headers: dict = None) -> tuple:
    """Returns (ok: bool, detail: str)."""
    try:
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key=api_key, default_headers=extra_headers or {})
        resp = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": "hi"}], max_tokens=5,
        )
        return True, (resp.choices[0].message.content or "")[:40]
    except Exception as e:
        return False, str(e)[:200]


def _test_typesafe(api_key: str) -> tuple:
    try:
        resp = requests.post(
            "https://api.typesafe.ai/v1/systemone",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "jev-latest", "state": "hello",
                  "questions": {"role": {"type": "choice", "instructions": "pick one",
                                          "criteria": {"a": "option a", "b": "option b"}}}},
            timeout=6,
        )
        resp.raise_for_status()
        return True, "reachable"
    except Exception as e:
        return False, str(e)[:200]


def _ask_key(label: str, env_var: str, signup_hint: str) -> str:
    print(f"\n  {label}")
    print(f"  ({signup_hint})")
    return input(f"  Paste your {env_var} (blank to skip): ").strip()


def _run_key_setup() -> dict:
    print("\n[Setup] API keys — each gets tested live right after you enter it.\n")
    env_values = {}
    results = []

    zenmux_key = _ask_key("ZenMux (primary — currently free GLM access)", "ZENMUX_API_KEY",
                           "sign up at zenmux.ai")
    if zenmux_key:
        ok, detail = _test_openai_compatible(
            "https://zenmux.ai/api/v1", zenmux_key, "z-ai/glm-5.3-free")
        results.append(("ZenMux", ok, detail))
        env_values["ZENMUX_API_KEY"] = zenmux_key

    openrouter_key = _ask_key("OpenRouter", "OPENROUTER_API_KEY", "openrouter.ai -> API keys")
    if openrouter_key:
        ok, detail = _test_openai_compatible(
            "https://openrouter.ai/api/v1", openrouter_key,
            "meta-llama/llama-3.3-70b-instruct:free",
            extra_headers={"HTTP-Referer": "https://paio-omni.local", "X-Title": "PAIO-Omni"})
        results.append(("OpenRouter", ok, detail))
        env_values["OPENROUTER_API_KEY"] = openrouter_key

    groq_key = _ask_key("Groq Cloud", "GROQ_API_KEY", "console.groq.com -> API Keys, free")
    if groq_key:
        ok, detail = _test_openai_compatible(
            "https://api.groq.com/openai/v1", groq_key, "llama-3.3-70b-versatile")
        results.append(("Groq", ok, detail))
        env_values["GROQ_API_KEY"] = groq_key

    typesafe_key = _ask_key("TypeSafe / Jev (role classification)", "TYPESAFE_API_KEY",
                             "your existing TypeSafe account")
    if typesafe_key:
        ok, detail = _test_typesafe(typesafe_key)
        results.append(("TypeSafe/Jev", ok, detail))
        env_values["TYPESAFE_API_KEY"] = typesafe_key

    print("\n[Setup] Key test results:")
    for name, ok, detail in results:
        status = "✓ OK" if ok else "✗ FAILED"
        print(f"    {status}  {name}  —  {detail}")

    _write_env(env_values)
    return env_values


def _write_env(env_values: dict):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base_dir, ".env")
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
        lines += [f"TYPESAFE_API_KEY={env_values['TYPESAFE_API_KEY']}"]

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n  Wrote {env_path}")


# ------------------------------------------------------------------ #
# 4. Live model fetch + drag-reorder priority dialogs
# ------------------------------------------------------------------ #

def _guess_role(model_id: str) -> str:
    lower = model_id.lower()
    for role, keywords in _ROLE_HINTS:
        if any(k in lower for k in keywords):
            return role
    return "general"


def fetch_openrouter_candidates(api_key: str = "") -> list:
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        resp = requests.get(_OPENROUTER_MODELS_URL, headers=headers, timeout=8)
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception as e:
        print(f"  [onboarding] couldn't fetch OpenRouter models live ({e}); using a small fallback seed.")
        return [{"id": m, "role": _guess_role(m)} for m in _FALLBACK_OPENROUTER_FREE]

    free = [m for m in data
            if str(m.get("pricing", {}).get("prompt", "1")) == "0"
            and str(m.get("pricing", {}).get("completion", "1")) == "0"]
    seen_roles, picked = set(), []
    for m in free:
        role = _guess_role(m["id"])
        if role not in seen_roles or len(picked) < _MAX_CANDIDATES // 2:
            picked.append({"id": m["id"], "role": role})
            seen_roles.add(role)
        if len(picked) >= _MAX_CANDIDATES:
            break
    if len(picked) < _MAX_CANDIDATES:
        for m in free:
            if len(picked) >= _MAX_CANDIDATES:
                break
            if not any(p["id"] == m["id"] for p in picked):
                picked.append({"id": m["id"], "role": _guess_role(m["id"])})
    return picked[:_MAX_CANDIDATES] or [{"id": m, "role": _guess_role(m)} for m in _FALLBACK_OPENROUTER_FREE]


def fetch_groq_candidates(api_key: str) -> list:
    try:
        resp = requests.get(_GROQ_MODELS_URL, headers={"Authorization": f"Bearer {api_key}"}, timeout=8)
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception as e:
        print(f"  [onboarding] couldn't fetch Groq models live ({e}); using llama-3.3-70b-versatile only.")
        return [{"id": "llama-3.3-70b-versatile", "role": "deep"}]
    ids = [m["id"] for m in data if "whisper" not in m.get("id", "").lower()]
    picked = [{"id": mid, "role": _guess_role(mid)} for mid in ids[:_MAX_CANDIDATES]]
    return picked or [{"id": "llama-3.3-70b-versatile", "role": "deep"}]


def fetch_ollama_cloud_candidates() -> list:
    """See the module docstring — hand-maintained, not live-fetched."""
    return list(OLLAMA_CLOUD_CANDIDATES)


class _PriorityDialog(QDialog):
    def __init__(self, title: str, candidates: list):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(420, 480)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"{title}\nDrag to reorder — top runs first, each one below is the fallback "
            "if everything above it fails."
        ))
        self.list_widget = QListWidget(self)
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        for c in candidates:
            item = QListWidgetItem(f"{c['id']}   [{c['role']}]")
            item.setData(1000, c["id"])
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)
        buttons = QHBoxLayout()
        ok = QPushButton("Save order")
        ok.clicked.connect(self.accept)
        buttons.addWidget(ok)
        layout.addLayout(buttons)

    def ordered_ids(self) -> list:
        return [self.list_widget.item(i).data(1000) for i in range(self.list_widget.count())]


def _run_priority_dialogs(env_values: dict) -> None:
    print("\n[Setup] Model priority — drag to reorder each list.\n")
    openrouter_candidates = fetch_openrouter_candidates(env_values.get("OPENROUTER_API_KEY", ""))
    groq_candidates = fetch_groq_candidates(env_values.get("GROQ_API_KEY", ""))
    ollama_cloud_candidates = fetch_ollama_cloud_candidates()

    cfg = config.load_user_config()

    if not _QT:
        print("  [onboarding] PySide6 not available — saving fetched order without manual ranking.")
        cfg["openrouter_model_priority"] = [c["id"] for c in openrouter_candidates]
        cfg["groq_model_priority"] = [c["id"] for c in groq_candidates]
        cfg["ollama_cloud_model_priority"] = [c["id"] for c in ollama_cloud_candidates]
    else:
        app = QApplication.instance() or QApplication([])
        for key, title, candidates in (
            ("openrouter_model_priority", "OpenRouter model priority", openrouter_candidates),
            ("groq_model_priority", "Groq model priority", groq_candidates),
            ("ollama_cloud_model_priority", "Ollama Cloud model priority", ollama_cloud_candidates),
        ):
            dlg = _PriorityDialog(title, candidates)
            dlg.exec()
            cfg[key] = dlg.ordered_ids()

    config.save_user_config(cfg)
    print(f"  Saved priority lists: OpenRouter ({len(cfg['openrouter_model_priority'])}), "
          f"Groq ({len(cfg['groq_model_priority'])}), "
          f"Ollama Cloud ({len(cfg['ollama_cloud_model_priority'])})")


# ------------------------------------------------------------------ #
# 5. Full tier download
# ------------------------------------------------------------------ #

def _free_disk_gb(path: str = ".") -> float:
    try:
        return shutil.disk_usage(path).free / (1024 ** 3)
    except Exception:
        return -1.0


def _already_installed_models() -> set:
    try:
        out = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        return {line.split()[0] for line in out.stdout.splitlines()[1:] if line.strip()}
    except Exception:
        return set()


def _pull_full_tier():
    import hardware
    hw = hardware.detect()
    tier = hw["tier"]
    wanted = hardware.all_models_for_tier(tier)
    installed = _already_installed_models()
    missing = [m for m in wanted if m not in installed]

    if not missing:
        print(f"  ✓ All {len(wanted)} models for tier '{tier}' are already installed.")
        return

    free_gb = _free_disk_gb()
    estimated_gb = len(missing) * 12  # rough, deliberately generous
    print(f"\n  Tier '{tier}' needs {len(missing)} more model(s) — "
          f"roughly {estimated_gb}GB, very approximately.")
    if free_gb >= 0:
        print(f"  Free disk space: {free_gb:.0f}GB")
        if free_gb < estimated_gb:
            print("  ⚠️  That's more than your free space, going by this rough estimate.")

    answer = input("  Proceed with downloading all of them now? [y/N] ").strip().lower()
    if answer != "y":
        print("  Skipping bulk download. Re-run onboarding.py anytime to resume,")
        print("  or pull individual models yourself with: ollama pull <model>")
        return

    for i, model in enumerate(missing, 1):
        print(f"\n  [{i}/{len(missing)}] Pulling {model} ...")
        subprocess.run(["ollama", "pull", model])


# ------------------------------------------------------------------ #
# Entry point
# ------------------------------------------------------------------ #

def run_full_setup():
    print("PAIO-Omni — setup\n")

    print("[1/5] Python packages ...")
    _ensure_pip_packages()

    print("\n[2/5] Ollama install + cloud sign-in ...")
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

    env_values = _run_key_setup()

    _run_priority_dialogs(env_values)

    print("\n[5/5] Local model tier download ...")
    if _ollama_installed():
        _pull_full_tier()
    else:
        print("  Skipping — Ollama isn't installed.")

    print("\nSetup complete.")
    answer = input("Launch PAIO now? [Y/n] ").strip().lower()
    if answer != "n":
        import orchestrator
        orchestrator.run()


if __name__ == "__main__":
    run_full_setup()
