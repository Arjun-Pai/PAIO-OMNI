# PAIO-Omni · cloud_llm.py  v3.1
"""
OpenRouter (primary) + Groq (fallback), both OpenAI-compatible. Replaces
v3.0's single-model-per-provider design (ToRouter/Groq) with a ranked
list per provider, set once during onboarding.py and saved in
config.json as openrouter_model_priority / groq_model_priority.

router.py owns walking that ranked list ("what's first runs first; on
failure, the next one runs") — this module just knows how to call one
specific (provider, model) pair.

This module owns:
  - full-transcript context (no truncation — these providers have large
    enough context windows that this is cheap and simple)
  - token-compaction at 90% of the response cap
  - the advanced, tool-calling memory path (see memory.CLOUD_TOOLS)
  - reporting "thinking" vs "making" back to the caller via state_fn, so
    the bubble UI can show a genuinely different animation for plain
    generation vs. an active vault tool call

Provider config (API keys) comes from a .env file (see .env.example)
via python-dotenv. Model *lists* come from config.json (see onboarding.py).
"""

import json as _json
import os

import config
import memory
import rag
import personality as persona_lib
import roles as mode_lib

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from openai import OpenAI
    _OPENAI_SDK = True
except ImportError:
    _OPENAI_SDK = False

MAX_TOOL_ROUNDS = 5

# OpenRouter asks callers to identify themselves via these two headers —
# not required to function, but recommended so requests aren't
# deprioritized, and it's free to include.
_OPENROUTER_REFERER = "https://paio-omni.local"
_OPENROUTER_TITLE = "PAIO-Omni"


def _provider_base(name: str) -> dict:
    if name == "zenmux":
        return {
            "base_url": os.environ.get("ZENMUX_API_BASE", "https://zenmux.ai/api/v1"),
            "api_key": os.environ.get("ZENMUX_API_KEY", ""),
            "default_headers": {},
        }
    if name == "openrouter":
        return {
            "base_url": os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1"),
            "api_key": os.environ.get("OPENROUTER_API_KEY", ""),
            "default_headers": {
                "HTTP-Referer": _OPENROUTER_REFERER,
                "X-Title": _OPENROUTER_TITLE,
            },
        }
    if name == "groq":
        return {
            "base_url": os.environ.get("GROQ_API_BASE", "https://api.groq.com/openai/v1"),
            "api_key": os.environ.get("GROQ_API_KEY", ""),
            "default_headers": {},
        }
    raise ValueError(f"Unknown cloud provider: {name}")


def _client_for(provider: str):
    if not _OPENAI_SDK:
        raise RuntimeError("openai package not installed. Run: pip install openai")
    cfg = _provider_base(provider)
    if not cfg["api_key"]:
        raise RuntimeError(f"No API key set for {provider} (check your .env)")
    return OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"],
                   default_headers=cfg["default_headers"])


# ZenMux is a single hand-picked endpoint, not a ranked list — see
# onboarding.py, which still tests it live during setup like everything
# else, it just doesn't get a drag-reorder dialog since there's only one.
ZENMUX_MODEL = os.environ.get("ZENMUX_MODEL", "z-ai/glm-5.3-free")


def model_priority(provider: str) -> list:
    """The ranked model list from onboarding.py, in fallback order.
    Empty list means onboarding hasn't run yet — router.py treats that
    as 'this provider has nothing to try'."""
    cfg = config.load_user_config()
    key = f"{provider}_model_priority"
    return cfg.get(key) or []


def _build_messages(text: str, history: list, mode_key: str, vault_path: str) -> list:
    system = persona_lib.get_system(mode_key)
    boot = memory.boot_context(vault_path) if vault_path else ""
    relevant = rag.semantic_search(vault_path, text) if vault_path else ""

    context_blocks = []
    if boot:
        context_blocks.append("Vault context (read at session start):\n" + boot)
    if relevant:
        context_blocks.append("Notes relevant to this message:\n" + relevant)

    messages = [{"role": "system", "content": system}]
    if context_blocks:
        messages.append({"role": "system", "content": "\n\n".join(context_blocks)})

    for entry in history:  # full, untruncated transcript
        messages.append(entry)
    messages.append({"role": "user", "content": text})
    return messages


def _run_with_tools(client, model: str, messages: list, vault_path: str, state_fn=None) -> str:
    """Non-streamed so tool calls are simple to resolve; the final answer
    is spoken once it's ready. Falls back to a plain call (no tools) if
    the provider/model rejects the tools parameter. Reports "thinking"
    before each generation and "making" while a tool call is actually
    being executed, so the bubble shows a genuinely different animation
    for "composing a reply" vs. "writing to the vault"."""
    tools = memory.CLOUD_TOOLS if vault_path else None

    for _round in range(MAX_TOOL_ROUNDS):
        if state_fn:
            state_fn("thinking")

        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": config.MAX_RESPONSE_TOKENS,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            if tools:
                # Some models/gateways reject `tools` — retry once without it.
                tools = None
                continue
            raise e

        choice = resp.choices[0]
        finish_reason = choice.finish_reason
        msg = choice.message

        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            if state_fn:
                state_fn("making")
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ]})
            for tc in tool_calls:
                try:
                    args = _json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                result = memory.execute_tool(vault_path, tc.function.name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
            continue  # let the model see tool results and respond again

        answer = (msg.content or "").strip()

        # Token compaction: if we hit (or are close to) the cap, ask for a
        # one-sentence wrap-up instead of leaving the thought half-cut.
        usage = getattr(resp, "usage", None)
        completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        near_cap = (
            finish_reason == "length"
            or completion_tokens >= config.MAX_RESPONSE_TOKENS * config.COMPACT_AT_FRACTION
        )
        if near_cap and answer:
            wrap_messages = messages + [
                {"role": "assistant", "content": answer},
                {"role": "user", "content": "Wrap up your remaining point in one sentence."},
            ]
            try:
                wrap_resp = client.chat.completions.create(
                    model=model, messages=wrap_messages, max_tokens=80,
                )
                wrap_text = (wrap_resp.choices[0].message.content or "").strip()
                if wrap_text:
                    answer = answer + " " + wrap_text
            except Exception:
                pass

        return answer

    return "I got stuck in a memory-tool loop — try that again?"


def chat(text: str, history: list, mode_key: str, vault_path: str,
         provider: str, model: str, speak_fn=None, state_fn=None) -> str:
    """Single attempt against one specific (provider, model) pair. Raises
    on failure — router.py walks the ranked list on top of this."""
    client = _client_for(provider)
    messages = _build_messages(text, history, mode_key, vault_path)
    answer = _run_with_tools(client, model, messages, vault_path, state_fn=state_fn)
    if speak_fn and answer:
        speak_fn(answer)
    return answer


def summarize(prompt: str, provider: str, model: str) -> str:
    """Used by memory.compact_if_needed as a summarize_fn when the cloud
    path is the active provider."""
    client = _client_for(provider)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
    )
    return (resp.choices[0].message.content or "").strip()
