# PAIO-Omni · router.py  v3.2
"""
Provider + model sequencing — now a fixed 5-tier chain, confirmed order:

    ZenMux -> OpenRouter (ranked) -> Groq (ranked) -> Ollama Cloud (ranked) -> Ollama local

Every tier below ZenMux is a ranked list you set in onboarding.py;
"what's first runs first, on failure the next one runs" all the way
down each list before moving to the next tier.

Behavior change from v3.1, flagged here since it's a real shift: this
no longer asks you out loud to choose between Groq/Ollama when
OpenRouter fails, and it no longer sticks to whatever tier last worked
for the rest of the session. With 5 fixed tiers now fully predetermined
by onboarding rather than a runtime choice, and since cost is your top
priority (ZenMux/OpenRouter are the cheap tiers), EVERY turn starts
back at the top of the chain — a transient failure shouldn't
permanently downgrade you to a worse/pricier/offline tier for the rest
of a session once the cheap options are working again. It still speaks
a brief status line when it has to fall further than ZenMux, so you
know what's actually answering you.

jev_router.py still owns a separate decision — which ROLE fits a
message. This module only decides which ACTUAL provider/model answers
it. Two different jobs, kept apart on purpose.
"""

import cloud_llm
import llm
import memory


def _try_ranked_list(provider: str, models: list, text, history, mode_key,
                      vault_path, speak_fn, state_fn) -> tuple:
    """Returns (answer, None) on success, or (None, last_exception) if
    every model in the list failed."""
    last_error = None
    for model in models:
        try:
            answer = cloud_llm.chat(
                text, history, mode_key, vault_path,
                provider=provider, model=model, speak_fn=speak_fn, state_fn=state_fn,
            )
            return answer, None
        except Exception as e:
            print(f"  [router] {provider}/{model} failed ({e}) — trying next in list ...")
            last_error = e
    return None, last_error


def _try_ollama_cloud(text, history, mode_key, hw_models, vault_path, speak_fn, state_fn) -> tuple:
    models = cloud_llm.model_priority("ollama_cloud")
    if not models:
        return None, "no ollama_cloud models saved — run onboarding.py"
    last_error = None
    for model in models:
        try:
            if state_fn:
                state_fn("thinking")
            answer = llm.chat(text, history, mode_key, hw_models, vault_path=vault_path,
                               speak_fn=speak_fn, model_override=model)
            return answer, None
        except Exception as e:
            print(f"  [router] ollama_cloud/{model} failed ({e}) — trying next in list ...")
            last_error = e
    return None, last_error


def respond(text: str, history: list, mode_key: str, hw_models: dict,
            vault_path: str, speak_fn=None, state_fn=None) -> str:
    """Walks the full chain top to bottom every turn. Local Ollama at the
    very end always has to work — no further fallback past it."""

    # 1. ZenMux — single hand-picked endpoint, not a ranked list.
    try:
        return cloud_llm.chat(
            text, history, mode_key, vault_path,
            provider="zenmux", model=cloud_llm.ZENMUX_MODEL,
            speak_fn=speak_fn, state_fn=state_fn,
        )
    except Exception as e:
        print(f"  [router] ZenMux failed ({e}) — trying OpenRouter ...")

    # 2. OpenRouter — ranked list.
    models = cloud_llm.model_priority("openrouter")
    if models:
        answer, error = _try_ranked_list("openrouter", models, text, history, mode_key,
                                          vault_path, speak_fn, state_fn)
        if answer is not None:
            return answer
        print(f"  [router] OpenRouter list exhausted ({error}) — trying Groq ...")
    else:
        print("  [router] No OpenRouter models saved — trying Groq ...")

    # 3. Groq — ranked list.
    models = cloud_llm.model_priority("groq")
    if models:
        answer, error = _try_ranked_list("groq", models, text, history, mode_key,
                                          vault_path, speak_fn, state_fn)
        if answer is not None:
            return answer
        print(f"  [router] Groq list exhausted ({error}) — trying Ollama Cloud ...")
    else:
        print("  [router] No Groq models saved — trying Ollama Cloud ...")

    # 4. Ollama Cloud — ranked list, routed through the local Ollama daemon.
    answer, error = _try_ollama_cloud(text, history, mode_key, hw_models,
                                       vault_path, speak_fn, state_fn)
    if answer is not None:
        return answer

    # 5. Ollama local — the last resort, has to work.
    if speak_fn:
        speak_fn("Everything cloud-side is unreachable right now — falling back to local Ollama.")
    print(f"  [router] Ollama Cloud exhausted ({error}) — falling back to local Ollama.")
    if state_fn:
        state_fn("thinking")
    return llm.chat(text, history, mode_key, hw_models, vault_path=vault_path, speak_fn=speak_fn)


def summarize_with_active_provider(prompt: str) -> str:
    """Used by memory.compact_if_needed — tries ZenMux first (cheapest),
    then OpenRouter's top pick, falling back to a trivial truncation if
    nothing is reachable. This doesn't need the full chain — it's a
    background housekeeping call, not a user-facing turn."""
    try:
        return cloud_llm.summarize(prompt, provider="zenmux", model=cloud_llm.ZENMUX_MODEL)
    except Exception:
        pass
    try:
        models = cloud_llm.model_priority("openrouter")
        if models:
            return cloud_llm.summarize(prompt, provider="openrouter", model=models[0])
    except Exception:
        pass
    return prompt[-800:]  # last resort: keep the tail rather than lose everything
