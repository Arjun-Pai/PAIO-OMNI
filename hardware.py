# PAIO-Omni · hardware.py  v0.5
import platform
import subprocess

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

ROLE_KEYS = (
    "fast",
    "brief",
    "deep",
    "casual",
    "professional",
    "formal",
    "executive",
    "strict",
    "debate",
    "scientist",
    "creative",
    "teacher",
    "coder",
)


def _tier_map(models: tuple[str, ...], whisper: str) -> dict:
    tier = dict(zip(ROLE_KEYS, models))
    tier["whisper"] = whisper
    return tier


RAW_TIER_MODELS = {
    "cpu_tiny": _tier_map((
        "smollm2:135m",
        "qwen2.5:0.5b",
        "deepseek-r1:1.5b",
        "qwen2.5-coder:0.5b",
        "llama3.2:1b",
        "tinyllama:1.1b",
        "danube3:500m",
        "qwen:0.5b",
        "smollm2:360m",
        "qwen2.5:1.5b",
        "llama3.2:1b-instruct-q8_0",
        "qwen2.5:0.5b-instruct-q8_0",
        "qwen2.5-coder:1.5b",
    ), "tiny.en"),
    "cpu_small": _tier_map((
        "gemma2:2b",
        "qwen2.5:3b",
        "llama3.2:3b",
        "phi3.5:mini",
        "granite3-dense:2b",
        "starcoder2:3b",
        "stable-code:3b",
        "qwen2.5-coder:3b",
        "gemma2:2b-instruct-q8_0",
        "llama3.2:3b-instruct-q8_0",
        "qwen2.5:1.5b-instruct-q8_0",
        "phi3:mini",
        "deepseek-r1:1.5b-q8_0",
    ), "base.en"),
    "cpu_medium": _tier_map((
        "llama3.1:8b",
        "qwen2.5:7b",
        "mistral:7b",
        "gemma2:9b",
        "deepseek-r1:7b",
        "deepseek-r1:8b",
        "qwen2.5-coder:7b",
        "llama3.1:8b-instruct-q4_0",
        "qwen2.5:7b-instruct-q4_K_M",
        "mistral-nemo:12b",
        "qwen2-math:7b",
        "codegemma:7b",
        "aya:8b",
    ), "small.en"),
    "cpu_large": _tier_map((
        "qwen2.5:14b",
        "qwen2.5:32b",
        "deepseek-r1:14b",
        "deepseek-r1:32b",
        "phi3:medium",
        "gemma2:27b-instruct-q4_0",
        "qwen2.5-coder:14b",
        "qwen2.5-coder:32b",
        "starcoder2:15b",
        "deepseek-coder-v2:16b",
        "mixtral:8x7b-instruct-v0.1-q4_0",
        "command-r:35b",
        "yi:34b",
    ), "medium.en"),
    "cpu_mega": _tier_map((
        "llama3.3:70b-instruct-q4_K_M",
        "qwen2.5:72b-instruct-q4_K_M",
        "deepseek-r1:70b-q4_K_M",
        "nemotron:70b-instruct-q4_K_M",
        "llama3.1:70b-instruct-q4_0",
        "mixtral:8x22b-instruct-v0.1-q4_0",
        "qwen2.5-coder:32b-instruct-q8_0",
        "command-r-plus:104b-q4_0",
        "dolphin-llama3:70b",
        "wizardlm2:8x22b-q4_0",
        "qwen2-math:72b-instruct-q4_0",
        "deepseek-v2:236b-chat-q2_K",
        "deepseek-coder-v2:236b-instruct-q2_K",
    ), "large-v3"),
    "gpu_tiny": _tier_map((
        "qwen2.5:1.5b-instruct-fp16",
        "llama3.2:1b-instruct-fp16",
        "gemma2:2b-instruct-fp16",
        "qwen2.5-coder:1.5b-instruct-fp16",
        "deepseek-r1:1.5b-fp16",
        "llama3.2:3b-instruct-q4_K_M",
        "qwen2.5:3b-instruct-q4_K_M",
        "qwen2.5-coder:3b-instruct-q4_K_M",
        "phi3.5:mini-instruct-fp16",
        "smollm2:1.7b-instruct-fp16",
        "granite3-dense:2b-instruct-fp16",
        "stable-code:3b-fp16",
        "qwen2.5:3b-instruct-q8_0",
    ), "small.en"),
    "gpu_small": _tier_map((
        "llama3.1:8b-instruct-q8_0",
        "qwen2.5:7b-instruct-q8_0",
        "gemma2:9b-instruct-q8_0",
        "deepseek-r1:7b-q8_0",
        "deepseek-r1:8b-q8_0",
        "qwen2.5-coder:7b-instruct-q8_0",
        "mistral:7b-instruct-q8_0",
        "aya:8b-instruct-q8_0",
        "llama3.1:8b-instruct-fp16",
        "qwen2.5:7b-instruct-fp16",
        "gemma2:9b-instruct-fp16",
        "qwen2-math:7b-instruct-q8_0",
        "codegemma:7b-instruct-q8_0",
    ), "medium.en"),
    "gpu_medium": _tier_map((
        "qwen2.5:14b-instruct-q8_0",
        "qwen2.5:32b-instruct-q4_K_M",
        "deepseek-r1:14b-q8_0",
        "deepseek-r1:32b-q4_K_M",
        "gemma2:27b",
        "gemma2:27b-instruct-q8_0",
        "qwen2.5-coder:14b-instruct-q8_0",
        "qwen2.5-coder:32b-instruct-q4_K_M",
        "command-r:35b-v0.1-q8_0",
        "mixtral:8x7b",
        "starcoder2:15b-instruct-q8_0",
        "deepseek-coder-v2:16b-lite-instruct-q8_0",
        "phi3:medium-128k-instruct-q8_0",
    ), "medium.en"),
    "gpu_large": _tier_map((
        "llama3.3:70b",
        "qwen2.5:72b",
        "deepseek-r1:70b",
        "nemotron:70b",
        "qwen2.5:32b-instruct-q8_0",
        "deepseek-r1:32b-q8_0",
        "qwen2.5-coder:32b-instruct-q8_0",
        "llama3.1:70b",
        "mixtral:8x22b",
        "command-r-plus:104b",
        "wizardlm2:8x22b",
        "qwen2-math:72b",
        "dolphin-llama3:70b-v2.9.3-q8_0",
    ), "medium.en"),
    "gpu_mega": _tier_map((
        "llama3.3:70b-instruct-q8_0",
        "qwen2.5:72b-instruct-q8_0",
        "deepseek-r1:70b-q8_0",
        "nemotron:70b-instruct-q8_0",
        "llama3.1:70b-instruct-q8_0",
        "mixtral:8x22b-instruct-v0.1-q8_0",
        "command-r-plus:104b-q8_0",
        "qwen2-math:72b-instruct-q8_0",
        "dolphin-llama3:70b-v2.9.3-fp16",
        "deepseek-coder-v2:236b",
        "dbrx:132b",
        "wizardlm:70b",
        "llama3.3:70b-instruct-fp16",
    ), "large-v3"),
}


def _validate_tier_models(tier_name: str, models: dict) -> dict:
    values = [model for model in models.values() if model]
    duplicates = sorted({model for model in values if values.count(model) > 1})
    if duplicates:
        raise ValueError(f"{tier_name} has duplicate model assignments: {', '.join(duplicates)}")
    return models


TIER_MODELS = {tier_name: _validate_tier_models(tier_name, models) for tier_name, models in RAW_TIER_MODELS.items()}


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

    # ── tier selection (cpu + gpu, each tiny→mega) ────
    if vram > 0 or is_apple:
        eff_vram = vram if vram > 0 else int(ram * 1024)
        if eff_vram >= 48000:
            tier = "gpu_mega"
        elif eff_vram >= 24000:
            tier = "gpu_large"
        elif eff_vram >= 16000:
            tier = "gpu_medium"
        elif eff_vram >= 8000:
            tier = "gpu_small"
        else:
            tier = "gpu_tiny"
    else:
        if ram >= 64:
            tier = "cpu_mega"
        elif ram >= 32:
            tier = "cpu_large"
        elif ram >= 16:
            tier = "cpu_medium"
        elif ram >= 8:
            tier = "cpu_small"
        else:
            tier = "cpu_tiny"

    return {
        "os":             os_name,
        "arch":           arch,
        "ram_gb":         round(ram, 1),
        "gpus":           gpus,
        "tier":           tier,
        "models":         TIER_MODELS[tier],
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