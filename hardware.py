# PAIO-Omni · hardware.py  v0.5
import platform
import subprocess

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False


TIER_MODELS = {
    "cpu_tiny": {
        "fast": "llama3.2:1b", "deep": "llama3.2:1b", "coder": "llama3.2:1b",
        "creative": "llama3.2:1b", "story": "llama3.2:1b", "debate": "llama3.2:1b",
        "teacher": "llama3.2:1b", "scientist": "llama3.2:1b", "professional": "llama3.2:1b",
        "formal": "llama3.2:1b", "executive": "llama3.2:1b", "strict": "llama3.2:1b",
    },
    "cpu_small": {
        "fast": "llama3.2:1b", "deep": "llama3.2:1b", "coder": "llama3.2:1b",
        "creative": "llama3.2:1b", "story": "llama3.2:1b", "debate": "llama3.2:1b",
        "teacher": "llama3.2:1b", "scientist": "llama3.2:1b", "professional": "llama3.2:1b",
        "formal": "llama3.2:1b", "executive": "llama3.2:1b", "strict": "llama3.2:1b",
    },
    "cpu_med": {
        "fast": "llama3.2:3b", "deep": "llama3.1:8b", "coder": "qwen2.5-coder:7b",
        "creative": "mistral:7b", "story": "mistral:7b", "debate": "llama3.1:8b",
        "teacher": "llama3.1:8b", "scientist": "llama3.1:8b", "professional": "llama3.1:8b",
        "formal": "llama3.1:8b", "executive": "llama3.1:8b", "strict": "llama3.1:8b",
    },
    "gpu_high": {
        "fast": "llama3.1:8b", "deep": "llama3.1:70b", "coder": "deepseek-coder-v2:16b",
        "creative": "command-r", "story": "command-r", "debate": "llama3.1:70b",
        "teacher": "llama3.1:70b", "scientist": "llama3.1:70b", "professional": "llama3.1:70b",
        "formal": "llama3.1:70b", "executive": "llama3.1:70b", "strict": "llama3.1:70b",
    }
}


def _ram_gb():
    if _PSUTIL:
        return psutil.virtual_memory().total / (1024 ** 3)
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) / (1024 ** 2)
    except Exception:
        pass
    return 4.0


def _nvidia_vram_mb():
    try:
        out = subprocess.check_output(
            ["nvidia-smi","--query-gpu=memory.total","--format=csv,noheader,nounits"],
            timeout=4, stderr=subprocess.DEVNULL
        ).decode().strip().splitlines()
        return int(out[0]) if out else 0
    except Exception:
        return 0


def detect() -> dict:
    os_name = platform.system()
    arch    = platform.machine()
    ram     = _ram_gb()
    gpus    = []

    is_apple = (os_name == "Darwin" and arch in ("arm64","aarch64"))
    vram     = _nvidia_vram_mb()

    if vram:
        gpus = [{"type":"nvidia","name":"NVIDIA GPU","vram_mb":vram}]
    elif is_apple:
        gpus = [{"type":"metal","name":"Apple Silicon","vram_mb":int(ram*1024)}]

    # ── tier selection ─────────────────────────────────
    if vram >= 4000 or (is_apple and ram >= 16) or ram >= 16:
        tier = "gpu_high"
    elif ram >= 8:
        tier = "cpu_large"
    elif ram >= 4:
        tier = "cpu_med"
    elif ram >= 2:
        tier = "cpu_small"
    else:
        tier = "cpu_tiny"

    # ── camera backend (platform-specific) ────────────
    try:
        import cv2
        if os_name == "Windows":
            cam_backend = cv2.CAP_DSHOW
        elif os_name == "Linux":
            cam_backend = cv2.CAP_V4L2
        else:
            cam_backend = cv2.CAP_AVFOUNDATION
    except ImportError:
        cam_backend = 0

    return {
        "os":             os_name,
        "arch":           arch,
        "ram_gb":         round(ram, 1),
        "gpus":           gpus,
        "tier":           tier,
        "models":         TIER_MODELS[tier],
        "camera_index":   0,
        "camera_backend": cam_backend,
    }


def summary(profile: dict) -> str:
    gpus    = profile.get("gpus") or []
    gpu_str = ""
    if gpus:
        g       = gpus[0]
        vram    = f" {g['vram_mb']//1024}GB" if g.get("vram_mb") else ""
        gpu_str = f" · {g.get('name','GPU')}{vram}"
    return (f"{profile['os']} {profile['arch']} · "
            f"{profile['ram_gb']:.0f} GB RAM{gpu_str} · "
            f"Tier: {profile['tier']}")