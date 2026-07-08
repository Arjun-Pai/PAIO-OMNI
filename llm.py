# PAIO-Omni · llm.py  v0.4
import requests
import json
import config
import modes as mode_lib

_SENTENCE_END = frozenset(".!?。\n")
_MIN_SENTENCE  = 8    # Reduced from 20 to speed up streaming on slow CPUs


def check_ollama() -> bool:
    try:
        r = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def list_local_models() -> list:
    try:
        r = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def chat(text: str, history: list, mode_key: str, hw_models: dict,
         speak_fn=None, vision_ctx: str = None) -> str:

    model  = mode_lib.get_model(mode_key, hw_models)
    system = mode_lib.get_system(mode_key)
    label  = mode_lib.MODES.get(mode_key, {}).get("name", "PAIO")

    messages = [{"role": "system", "content": system}]
    for entry in history:
        messages.append(entry)

    content = text
    if vision_ctx:
        content = f"{text}\n\nVision context: {vision_ctx}"
    messages.append({"role": "user", "content": content})

    try:
        resp = requests.post(
            f"{config.OLLAMA_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": True},
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        msg = "Ollama isn't running. Start it with: ollama serve"
        if speak_fn:
            speak_fn(msg)
        return msg
    except Exception as e:
        msg = f"Ollama error: {e}"
        if speak_fn:
            speak_fn(msg)
        return msg

    full = ""
    buf  = ""
    print(f"\nPAIO [{label}]: ", end="", flush=True)

    for raw in resp.iter_lines():
        if not raw:
            continue
        try:
            data  = json.loads(raw)
            chunk = data.get("message", {}).get("content", "")
        except json.JSONDecodeError:
            continue

        if chunk:
            print(chunk, end="", flush=True)
            full += chunk
            buf  += chunk

            if speak_fn:
                while True:
                    cut = -1
                    for i, ch in enumerate(buf):
                        if ch in _SENTENCE_END and i >= _MIN_SENTENCE:
                            cut = i
                            break
                    if cut == -1:
                        break
                    sentence = buf[:cut + 1].strip()
                    buf = buf[cut + 1:].lstrip()
                    if sentence:
                        speak_fn(sentence)

        if data.get("done"):
            break

    print()
    if speak_fn and buf.strip():
        speak_fn(buf.strip())

    return full.strip()
