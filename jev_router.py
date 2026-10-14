# PAIO-Omni · jev_router.py  v3.2
"""
Jev (TypeSafe AI's System One model) makes two decisions per message in
ONE call (Jev's API supports multiple named "questions" in a single
request, so this doesn't cost an extra round-trip):

  - "role": which of the 13 roles in roles.py fits this message —
    fully replaces v3.0's modes.py keyword scoring.
  - "complexity": simple / complicated / very_complicated — feeds
    ensemble.py's decision on whether to answer with one model, a
    mixture-of-experts (multiple models, synthesized), or a parallel
    mixture-of-experts (multiple MoE groups, each synthesized, then
    synthesized again).

API (per TypeSafe's docs, api.typesafe.ai):
  POST /v1/systemone
  { "model": "jev-latest",
    "state": "<message>",
    "questions": { "role": {...}, "complexity": {...} } }

Needs TYPESAFE_API_KEY in .env. If it's missing, the call fails, or the
response doesn't come back in a shape we recognize, this falls back to
plain heuristics — never a hard failure. Jev only decides role and
complexity; router.py's provider sequencing and ensemble.py's expert
selection are separate, always-on logic regardless of what Jev picks.
"""

import os

import requests

import roles

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
_MODEL = "jev-latest"
_TIMEOUT = 4.0  # Jev is built to be fast — if it's not, fall back rather than stall a turn

_COMPLEXITY_LEVELS = ("simple", "complicated", "very_complicated")
_COMPLEXITY_CRITERIA = {
    "simple": "A short, direct question or request with one clear answer — factual "
              "lookups, quick tasks, casual chat, single-step requests.",
    "complicated": "Requires weighing multiple angles, some domain expertise, or "
                   "synthesizing a few related considerations — the kind of question "
                   "where a second opinion would genuinely help.",
    "very_complicated": "Multi-part, high-stakes, or spans several distinct domains "
                        "at once (e.g. technical + strategic + creative in one ask) — "
                        "the kind of question worth getting several independent takes "
                        "on before combining them.",
}

_MANUAL_OVERRIDES = {
    # "use the coder model" style manual override phrases, checked before
    # ever calling Jev — cheap, deterministic, and lets you correct a bad
    # routing habit without waiting on a network call.
    "use the coder model": "coder",
    "use coder mode": "coder",
    "switch to coder": "coder",
    "use the fast model": "fast",
    "use the deep model": "deep",
    "use the scientist model": "scientist",
    "use the teacher model": "teacher",
    "use the creative model": "creative",
    "use the strict model": "strict",
    "use the debate model": "debate",
    "use the executive model": "executive",
    "use the professional model": "professional",
    "use the formal model": "formal",
    "use the casual model": "casual",
    "use the brief model": "brief",
}


def _check_manual_override(text: str) -> str | None:
    lower = text.lower().strip()
    for phrase, role_key in _MANUAL_OVERRIDES.items():
        if phrase in lower:
            return role_key
    return None


def _fallback_role(text: str) -> str:
    """Same tail logic v3.0's modes.py used when keyword scoring came up
    empty — kept as the last resort when Jev itself is unreachable."""
    word_count = len(text.split())
    if word_count <= 4:
        return "brief"
    if word_count <= 10:
        return "fast"
    if word_count >= 20:
        return "deep"
    return "fast"


def _fallback_complexity(text: str) -> str:
    """Heuristic used only if Jev is unreachable. Deliberately
    conservative — defaults to "simple" unless there's a clear signal,
    since running an ensemble costs real time and money and shouldn't
    trigger on a guess."""
    word_count = len(text.split())
    multi_part = text.count("?") > 1 or " and " in text.lower() and word_count > 25
    if word_count > 60 or (multi_part and word_count > 40):
        return "very_complicated"
    if word_count > 25 or multi_part:
        return "complicated"
    return "simple"


def _find_choice_in_response(data, key: str, valid_values: set) -> str | None:
    """Defensive parse: walk the response looking for the named
    question's answer, or (failing that) any string value that's one of
    the valid values for it. Written this way because exact response
    nesting isn't nailed down across all of Jev's docs/SDKs — robust to
    minor shape differences rather than brittle to one path."""
    if isinstance(data, dict):
        if key in data:
            direct = _extract_value(data[key], valid_values)
            if direct:
                return direct
        for v in data.values():
            found = _find_choice_in_response(v, key, valid_values)
            if found:
                return found
    if isinstance(data, list):
        for v in data:
            found = _find_choice_in_response(v, key, valid_values)
            if found:
                return found
    if isinstance(data, str) and data in valid_values:
        return data
    return None


def _extract_value(node, valid_values: set) -> str | None:
    if isinstance(node, str) and node in valid_values:
        return node
    if isinstance(node, dict):
        for v in node.values():
            found = _extract_value(v, valid_values)
            if found:
                return found
    if isinstance(node, list):
        for v in node:
            found = _extract_value(v, valid_values)
            if found:
                return found
    return None


def detect_full(text: str, extra_context: str = "") -> dict:
    """Returns {"role": ..., "complexity": ...}. Both decided in one
    Jev call. Manual role overrides skip Jev's role question entirely
    but still ask it about complexity (an override doesn't tell us
    whether to run an ensemble)."""
    override = _check_manual_override(text)

    api_key = os.environ.get("TYPESAFE_API_KEY", "")
    if not api_key:
        return {
            "role": override or _fallback_role(text),
            "complexity": _fallback_complexity(text),
        }

    state = text if not extra_context else f"{extra_context}\n\nMessage: {text}"
    questions = {
        "complexity": {
            "type": "choice",
            "instructions": "How complex is this message to answer well?",
            "criteria": _COMPLEXITY_CRITERIA,
        }
    }
    if not override:
        questions["role"] = {
            "type": "choice",
            "instructions": "Which role best fits handling this message?",
            "criteria": {key: mode["desc"] for key, mode in roles.MODES.items()},
        }

    payload = {"model": _MODEL, "state": state, "questions": questions}

    try:
        resp = requests.post(
            _ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload, timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [jev] unavailable this turn, falling back ({e})")
        return {
            "role": override or _fallback_role(text),
            "complexity": _fallback_complexity(text),
        }

    complexity = _find_choice_in_response(data, "complexity", set(_COMPLEXITY_LEVELS))
    role = override or _find_choice_in_response(data, "role", set(roles.ROLE_KEYS))

    return {
        "role": role or _fallback_role(text),
        "complexity": complexity or _fallback_complexity(text),
    }


def detect(text: str, extra_context: str = "") -> str:
    """Backward-compatible: just the role, for call sites that don't
    care about complexity."""
    return detect_full(text, extra_context)["role"]

