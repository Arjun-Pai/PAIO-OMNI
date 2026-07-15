# PAIO-Omni · llm.py  v0.4
import requests
import json
import re
import subprocess
import config
import modes as mode_lib

def _looks_like_url_only(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    t = t.strip("`[]() ")
    return bool(re.fullmatch(r"https?://\S+", t))


def _pick_available_model(requested: str, hw_models: dict) -> str:
    local = list_local_models()
    if not local:
        return requested

    if requested in local:
        return requested

    # Prefer another hardware-profile model that is installed.
    for m in dict.fromkeys(hw_models.values()):
        if m and m in local:
            return m

    # Last resort: first locally installed model.
    return local[0]


def _messages_to_prompt(messages: list) -> str:
    lines = []
    for m in messages:
        role = m.get("role", "user").upper()
        content = m.get("content", "")
        lines.append(f"{role}: {content}")
    lines.append("ASSISTANT:")
    return "\n\n".join(lines)


def _list_local_models_cli() -> list:
    try:
        out = subprocess.check_output(
            ["ollama", "list"],
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.DEVNULL,
        )
        names = []
        for line in out.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if parts:
                names.append(parts[0])
        return names
    except Exception:
        return []


def _chat_via_cli(model: str, messages: list) -> str:
    try:
        prompt = _messages_to_prompt(messages)
        out = subprocess.check_output(
            ["ollama", "run", model, prompt],
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.STDOUT,
            timeout=180,
        )
        return out.strip()
    except Exception:
        return ""


def check_ollama() -> bool:
    try:
        r = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def list_local_models() -> list:
    try:
        r = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        if models:
            return models
        return _list_local_models_cli()
    except Exception:
        return _list_local_models_cli()


def chat(text: str, history: list, mode_key: str, hw_models: dict,
         speak_fn=None) -> str:

    requested_model = mode_lib.get_model(mode_key, hw_models)

    local_models = list_local_models()
    if not local_models:
        msg = f"No local Ollama models found. Run: ollama pull {requested_model}"
        if speak_fn:
            speak_fn(msg)
        return msg

    model = _pick_available_model(requested_model, hw_models)
    system = mode_lib.get_system(mode_key)
    label  = mode_lib.MODES.get(mode_key, {}).get("name", "PAIO")

    messages = [{"role": "system", "content": system}]
    for entry in history:
        messages.append(entry)

    messages.append({"role": "user", "content": text})

    if model != requested_model:
        print(f"  [LLM] Fallback model: {requested_model} -> {model}")

    api_mode = "chat"
    try:
        resp = requests.post(
            f"{config.OLLAMA_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": True},
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status == 404:
            api_mode = "generate"
            print("  [LLM] /api/chat unavailable, using /api/generate fallback")
            try:
                resp = requests.post(
                    f"{config.OLLAMA_URL}/api/generate",
                    json={"model": model, "prompt": _messages_to_prompt(messages), "stream": True},
                    stream=True,
                    timeout=120,
                )
                resp.raise_for_status()
            except Exception:
                cli_answer = _chat_via_cli(model, messages)
                if cli_answer:
                    print("  [LLM] Using Ollama CLI fallback")
                    return cli_answer
                msg = "Ollama error: /api/chat and /api/generate both unavailable"
                if speak_fn:
                    speak_fn(msg)
                return msg
        else:
            msg = f"Ollama error: {e}"
            if speak_fn:
                speak_fn(msg)
            return msg
    except requests.exceptions.ConnectionError:
        msg = "Ollama isn't running. Start it with: ollama serve"
        if speak_fn:
            speak_fn(msg)
        return msg
    except Exception as e:
        cli_answer = _chat_via_cli(model, messages)
        if cli_answer:
            print("  [LLM] Using Ollama CLI fallback")
            return cli_answer
        msg = f"Ollama error: {e}"
        if speak_fn:
            speak_fn(msg)
        return msg

    full = ""
    print(f"\nPAIO [{label}]: ", end="", flush=True)

    for raw in resp.iter_lines():
        if not raw:
            continue
        try:
            data  = json.loads(raw)
            if api_mode == "chat":
                chunk = data.get("message", {}).get("content", "")
            else:
                chunk = data.get("response", "")
        except json.JSONDecodeError:
            continue

        if chunk:
            print(chunk, end="", flush=True)
            full += chunk

        if data.get("done"):
            break

    print()

    answer = full.strip()

    # Some models occasionally emit only a bare URL; retry once for a direct answer.
    if _looks_like_url_only(answer):
        try:
            if api_mode == "chat":
                retry_messages = messages + [{
                    "role": "system",
                    "content": "Respond with a direct plain-text answer. Do not return only a URL.",
                }]
                retry = requests.post(
                    f"{config.OLLAMA_URL}/api/chat",
                    json={"model": model, "messages": retry_messages, "stream": False},
                    timeout=120,
                )
            else:
                retry_prompt = (
                    _messages_to_prompt(messages)
                    + "\n\nSYSTEM: Respond with a direct plain-text answer. Do not return only a URL."
                    + "\n\nASSISTANT:"
                )
                retry = requests.post(
                    f"{config.OLLAMA_URL}/api/generate",
                    json={"model": model, "prompt": retry_prompt, "stream": False},
                    timeout=120,
                )
            retry.raise_for_status()
            retry_json = retry.json()
            if api_mode == "chat":
                retry_answer = retry_json.get("message", {}).get("content", "").strip()
            else:
                retry_answer = retry_json.get("response", "").strip()
            if retry_answer:
                answer = retry_answer
        except Exception:
            pass

    if speak_fn and answer:
        speak_fn(answer)

    return answer
