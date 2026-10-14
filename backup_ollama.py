import subprocess

# 1. Store model map in a dictionary
cpu_tiny = {
    "fast": "qwen2.5:0.5b",
    "brief": "qwen:0.5b",
    "deep": "deepseek-r1:1.5b",
    "casual": "gemma2:2b",
    "professional": "llama3.2:1b",
    "formal": "phi3.5",  # Fixed tag
    "executive": "mistral:7b",
    "strict": "granite3-dense:2b",
    "debate": "aya:8b",
    "scientist": "qwen2.5:1.5b",
    "creative": "dolphin-llama3:8b",
    "teacher": "smollm2:135m",
    "coder": "qwen2.5-coder:0.5b",
}

# 2. Extract model tag values into a list
cpu_tiny_models = list(cpu_tiny.values())

# 3. Download models sequentially with error handling
for index, model in enumerate(cpu_tiny_models, start=1):
    print(f"\n[{index}/{len(cpu_tiny_models)}] Pulling {model}...")
    try:
        subprocess.run(["ollama", "pull", model], check=True)
        print(f"✓ Successfully pulled {model}")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to pull {model}: Exit code {e.returncode}")