# PAIO-Omni · llm.py  v3.1  (local Ollama path — offline fallback)
import requests
import json
import re
import subprocess
import config
import roles as mode_lib
import personality as persona_lib
import memory
import rag


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
    for m in dict.fromkeys(hw_models.values()):
        if m and m in local:
            return m
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
            ["ollama", "list"], text=True, encoding="utf-8",
            errors="replace", stderr=subprocess.DEVNULL,
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
            ["ollama", "run", model, prompt], text=True, encoding="utf-8",
            errors="replace", stderr=subprocess.STDOUT, timeout=180,
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
        return models if models else _list_local_models_cli()
    except Exception:
        return _list_local_models_cli()


def _one_shot(model: str, messages: list) -> str:
    try:
        resp = requests.post(
            f"{config.OLLAMA_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "").strip()
    except Exception:
        return ""


def chat(text: str, history: list, mode_key: str, hw_models: dict,
         vault_path: str = None, speak_fn=None, model_override: str = None) -> str:
    """model_override: used for Ollama Cloud (:cloud-suffixed tags) — the
    exact tag is used as-is, skipping the hardware-tier role lookup and
    the local-model substitution logic below (a cloud tag isn't
    something to swap for whatever happens to be pulled locally)."""

    if model_override:
        model = model_override
        requested_model = model_override
    else:
        requested_model = mode_lib.get_model(mode_key, hw_models)

        local_models = list_local_models()
        if not local_models:
            msg = f"No local Ollama models found. Run: ollama pull {requested_model}"
            if speak_fn:
                speak_fn(msg)
            return msg

        model = _pick_available_model(requested_model, hw_models)

    system = persona_lib.get_system(mode_key)
    label = mode_lib.MODES.get(mode_key, {}).get("name", "PAIO")

    messages = [{"role": "system", "content": system}]

    if vault_path:
        boot = memory.boot_context(vault_path)
        relevant = rag.semantic_search(vault_path, text)
        ctx = "\n\n".join(b for b in (boot, relevant) if b)
        if ctx:
            messages.append({"role": "system", "content": "Vault context:\n" + ctx})

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
            stream=True, timeout=120,
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
                    stream=True, timeout=120,
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
    word_cap = int(config.MAX_RESPONSE_TOKENS * 0.75)
    compact_at = word_cap * config.COMPACT_AT_FRACTION
    print(f"\nPAIO [{label}]: ", end="", flush=True)

    for raw in resp.iter_lines():
        if not raw:
            continue
        try:
            data = json.loads(raw)
            chunk = data.get("message", {}).get("content", "") if api_mode == "chat" else data.get("response", "")
        except json.JSONDecodeError:
            continue

        if chunk:
            print(chunk, end="", flush=True)
            full += chunk

        if len(full.split()) >= compact_at:
            # Close to the response cap — stop early and wrap up in one line.
            try:
                resp.close()
            except Exception:
                pass
            break

        if data.get("done"):
            break

    print()
    answer = full.strip()

    if len(answer.split()) >= compact_at:
        wrap_messages = messages + [
            {"role": "assistant", "content": answer},
            {"role": "user", "content": "Wrap up your remaining point in one sentence."},
        ]
        wrap = _one_shot(model, wrap_messages)
        if wrap:
            answer = answer + " " + wrap

    if _looks_like_url_only(answer):
        retry = _one_shot(model, messages + [{
            "role": "system",
            "content": "Respond with a direct plain-text answer. Do not return only a URL.",
        }])
        if retry:
            answer = retry

    if vault_path:
        memory.simple_extract_and_save(vault_path, text)

    if speak_fn and answer:
        speak_fn(answer)

    return answer
