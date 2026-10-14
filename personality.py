# PAIO-Omni · personality.py  v3.1
"""Loads personality.md once and prepends it to every role's system prompt
(role now chosen by Jev — see jev_router.py — not modes.py, which no
longer exists), so PAIO sounds like itself regardless of role, provider,
or model."""

import os
import roles as mode_lib

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PERSONALITY_PATH = os.path.join(_BASE_DIR, "personality.md")

_cached = None


def _load() -> str:
    global _cached
    if _cached is None:
        try:
            with open(_PERSONALITY_PATH, "r", encoding="utf-8") as f:
                _cached = f.read()
        except FileNotFoundError:
            _cached = ""
    return _cached


def get_system(mode_key: str) -> str:
    personality = _load()
    mode_system = mode_lib.get_system(mode_key)
    if not personality:
        return mode_system
    return personality + "\n\n---\n\n" + mode_system


def session_open_prompt(joke: str) -> str:
    """A one-off instruction used only for the very first turn of a
    session — greet informally and naturally work the joke in."""
    base = (
        "This is the start of a new session with Mr. Pai. Greet him "
        "casually and briefly, in character, and naturally weave in the "
        "following line without announcing it's a joke. Keep the whole "
        "greeting to 1-2 sentences, then ask what he's working on.\n\n"
        f"Line to work in: {joke}"
    )
    return base
