# PAIO-Omni · hardware.py  v3.2
"""
Detects this machine's tier and returns the matching model set.

130 cells (10 tiers x 13 roles), every single tag distinct across the
whole matrix — no model, at any size or quant, is reused anywhere else.
Where a role's natural model family ran out of distinct sizes before
reaching the largest tiers, the ladder continues into other
well-established (if sometimes older) community models rather than
reusing anything. `tester.py` is what actually tells you which of
these are worth keeping long-term for your hardware.

v3.2: gpu_mega/fast swapped from exaone3.5:2.4b (a tiny model oddly
placed in the most powerful tier) to glm-4.7-flash, confirmed real and
in Ollama's library as of ~August 2026.

onboarding.py pulls all 13 models for your detected tier on setup —
see its disk-space check before that runs on cpu_mega/gpu_mega.
"""
import platform
import subprocess

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

ROLE_KEYS = (
    "fast", "brief", "deep", "casual", "professional", "formal",
    "executive", "strict", "debate", "scientist", "creative", "teacher",
    "coder",
)

WHISPER_BY_TIER = {
    "cpu_tiny": "tiny.en", "gpu_tiny": "small.en",
    "cpu_small": "base.en", "gpu_small": "medium.en",
    "cpu_medium": "small.en", "gpu_medium": "medium.en",
    "cpu_large": "medium.en", "gpu_large": "medium.en",
    "cpu_mega": "large-v3", "gpu_mega": "large-v3",
}

RAW_TIER_MODELS = {
    "cpu_tiny": {
        "fast": "qwen2.5:0.5b", "brief": "qwen:0.5b", "deep": "deepseek-r1:1.5b",
        "casual": "gemma2:2b", "professional": "llama3.2:1b", "formal": "phi3.5:mini",
        "executive": "mistral:7b", "strict": "granite3-dense:2b", "debate": "aya:8b",
        "scientist": "qwen3:0.6b", "creative": "dolphin-llama3:8b",
        "teacher": "smollm2:135m", "coder": "qwen2.5-coder:0.5b",
    },
    "gpu_tiny": {
        "fast": "qwen2.5:1.5b", "brief": "qwen:1.8b", "deep": "deepseek-r1:7b",
        "casual": "gemma2:9b", "professional": "llama3.2:3b", "formal": "phi3:medium",
        "executive": "mistral-nemo:12b", "strict": "granite3-dense:8b", "debate": "aya:35b",
        "scientist": "qwen3:1.7b", "creative": "dolphin-llama3:70b",
        "teacher": "smollm2:360m", "coder": "qwen2.5-coder:1.5b",
    },
    "cpu_small": {
        "fast": "qwen2.5:3b", "brief": "qwen:4b", "deep": "deepseek-r1:8b",
        "casual": "gemma2:27b", "professional": "llama3.1:8b", "formal": "phi4-mini:3.8b",
        "executive": "ministral:3b", "strict": "command-r7b:7b", "debate": "internlm2:7b",
        "scientist": "qwen3:4b", "creative": "zephyr:7b",
        "teacher": "smollm2:1.7b", "coder": "qwen2.5-coder:3b",
    },
    "gpu_small": {
        "fast": "qwen2.5:7b", "brief": "qwen:7b", "deep": "deepseek-r1:14b",
        "casual": "gemma3:1b", "professional": "llama3.1:70b", "formal": "phi4:14b",
        "executive": "ministral:8b", "strict": "command-r:35b", "debate": "internlm2:20b",
        "scientist": "qwen3:8b", "creative": "nous-hermes2:10.7b",
        "teacher": "tinyllama:1.1b", "coder": "qwen2.5-coder:7b",
    },
    "cpu_medium": {
        "fast": "qwen2.5:14b", "brief": "qwen:14b", "deep": "deepseek-r1:32b",
        "casual": "gemma3:4b", "professional": "llama3.3:70b", "formal": "granite3-moe:1b",
        "executive": "mixtral:8x7b", "strict": "command-r-plus:104b", "debate": "falcon:7b",
        "scientist": "qwen3:14b", "creative": "nous-hermes2:34b",
        "teacher": "danube3:500m", "coder": "qwen2.5-coder:14b",
    },
    "gpu_medium": {
        "fast": "qwen2.5:32b", "brief": "qwen:32b", "deep": "deepseek-r1:70b",
        "casual": "gemma3:12b", "professional": "granite3.1-dense:2b", "formal": "granite3-moe:3b",
        "executive": "mixtral:8x22b", "strict": "llama-guard3:1b", "debate": "falcon:40b",
        "scientist": "qwen3:30b-a3b", "creative": "solar:10.7b",
        "teacher": "danube3:4b", "coder": "qwen2.5-coder:32b",
    },
    "cpu_large": {
        "fast": "qwen2.5:72b", "brief": "qwen:72b", "deep": "qwen2-math:7b",
        "casual": "gemma3:27b", "professional": "granite3.1-dense:8b", "formal": "codestral:22b",
        "executive": "notux:8x7b", "strict": "llama-guard3:8b", "debate": "falcon:180b",
        "scientist": "qwen3:32b", "creative": "openchat:7b",
        "teacher": "wizardlm2:7b", "coder": "starcoder2:3b",
    },
    "gpu_large": {
        "fast": "olmo2:7b", "brief": "vicuna:7b", "deep": "qwen2-math:72b",
        "casual": "orca-mini:3b", "professional": "exaone3.5:7.8b", "formal": "athene-v2:72b",
        "executive": "notus:7b", "strict": "shieldgemma:2b", "debate": "aya-expanse:8b",
        "scientist": "yi:6b", "creative": "neural-chat:7b",
        "teacher": "stable-code:3b", "coder": "starcoder2:7b",
    },
    "cpu_mega": {
        "fast": "olmo2:13b", "brief": "vicuna:13b", "deep": "openthinker:7b",
        "casual": "orca-mini:7b", "professional": "exaone3.5:32b", "formal": "hermes3:8b",
        "executive": "samantha-mistral:7b", "strict": "shieldgemma:9b", "debate": "aya-expanse:32b",
        "scientist": "yi:9b", "creative": "airoboros:7b",
        "teacher": "yi-coder:1.5b", "coder": "starcoder2:15b",
    },
    "gpu_mega": {
        "fast": "glm-4.7-flash", "brief": "vicuna:33b", "deep": "openthinker:32b",
        "casual": "orca-mini:13b", "professional": "reflection:70b", "formal": "hermes3:70b",
        "executive": "dolphin-mistral:7b", "strict": "wizardlm:70b", "debate": "dbrx:132b",
        "scientist": "yi:34b", "creative": "xwinlm:7b",
        "teacher": "yi-coder:9b", "coder": "deepseek-coder-v2:16b",
    },
}


def _validate_tier_models(tier_name: str, models: dict) -> dict:
    values = list(models.values())
    duplicates = sorted({v for v in values if values.count(v) > 1})
    if duplicates:
        raise ValueError(f"{tier_name} has duplicate model assignments: {', '.join(duplicates)}")
    return models


def _validate_global_uniqueness(tiers: dict) -> None:
    seen = {}
    for tier_name, models in tiers.items():
        for role, tag in models.items():
            if tag in seen:
                raise ValueError(
                    f"Model '{tag}' used in both {seen[tag]} and {tier_name}/{role} — "
                    f"the whole point of this matrix is that this never happens."
                )
            seen[tag] = f"{tier_name}/{role}"


TIER_MODELS = {name: _validate_tier_models(name, dict(models, **{"whisper": WHISPER_BY_TIER[name]}))
               for name, models in RAW_TIER_MODELS.items()}
_validate_global_uniqueness({name: {k: v for k, v in m.items() if k != "whisper"}
                              for name, m in TIER_MODELS.items()})


def all_models_for_tier(tier: str) -> list:
    """The 13 model tags (no whisper) for one tier — what onboarding.py pulls."""
    return [v for k, v in TIER_MODELS[tier].items() if k != "whisper"]


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
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            timeout=4, stderr=subprocess.DEVNULL,
        ).decode().strip().splitlines()
        return int(out[0]) if out else 0
    except Exception:
        return 0


def detect() -> dict:
    os_name = platform.system()
    arch = platform.machine()
    ram = _ram_gb()
    gpus = []

    is_apple = (os_name == "Darwin" and arch in ("arm64", "aarch64"))
    vram = _nvidia_vram_mb()

    if vram:
        gpus = [{"type": "nvidia", "name": "NVIDIA GPU", "vram_mb": vram}]
    elif is_apple:
        gpus = [{"type": "metal", "name": "Apple Silicon", "vram_mb": int(ram * 1024)}]

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
        "os": os_name, "arch": arch, "ram_gb": round(ram, 1),
        "gpus": gpus, "tier": tier, "models": TIER_MODELS[tier],
    }


def summary(profile: dict) -> str:
    gpus = profile.get("gpus") or []
    gpu_str = ""
    if gpus:
        g = gpus[0]
        vram = f" {g['vram_mb']//1024}GB" if g.get("vram_mb") else ""
        gpu_str = f" · {g.get('name','GPU')}{vram}"
    return (f"{profile['os']} {profile['arch']} · "
            f"{profile['ram_gb']:.0f} GB RAM{gpu_str} · "
            f"Tier: {profile['tier']}")
