# PAIO-Omni · memory.py  v3.1
"""
Everything to do with the Brain vault (Obsidian) and cross-session memory.

Note lookup (v3.1): semantic search only, via rag.py — see relevant_notes()
below, which is now a thin wrapper around rag.semantic_search(). No keyword
fallback on any tier, per the v3.1 plan.

Two tiers of "smart memory handling", matching which LLM provider answered
the turn:
  - Cloud (ToRouter / Groq): the model gets real tool-calling access
    (read_note / write_note / append_note / list_notes) and decides for
    itself what's worth saving, following the vault's own frontmatter and
    folder-index rules. See CLOUD_TOOLS + execute_tool().
  - Local (Ollama): no tool-calling reliability to lean on, so this module
    does simple, rule-based fact extraction instead (simple_extract_and_save).

Both paths write through the same primitives (read_note/write_note/etc.)
so the vault stays consistent no matter which provider handled the turn.
"""

import json
import os
import random
import re
from datetime import datetime, timedelta

import config

_MONTHS = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
]

VAULT_FOLDERS = [
    "00 - Inbox",
    "01 - Daily Notes",
    "02 - Projects",
    "03 - People",
    "04 - Personal",
    "05 - Resources",
    "06 - Archive",
]

_SESSION_STATE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "session_state.json"
)


# ------------------------------------------------------------------ #
# Vault discovery
# ------------------------------------------------------------------ #

def find_vault() -> str | None:
    """Locate the Brain vault: saved config first, then default guesses."""
    cfg = config.load_user_config()
    saved = cfg.get("vault_path")
    if saved and os.path.isdir(saved) and _looks_like_vault(saved):
        return saved

    for candidate in config.DEFAULT_VAULT_CANDIDATES:
        if os.path.isdir(candidate) and _looks_like_vault(candidate):
            cfg["vault_path"] = candidate
            config.save_user_config(cfg)
            return candidate

    return None


def _looks_like_vault(path: str) -> bool:
    return os.path.exists(os.path.join(path, "VAULT-INDEX.md"))


def remember_vault_path(path: str) -> None:
    cfg = config.load_user_config()
    cfg["vault_path"] = path
    config.save_user_config(cfg)


# ------------------------------------------------------------------ #
# Low-level note I/O (sandboxed to the vault root)
# ------------------------------------------------------------------ #

def _safe_path(vault_path: str, rel_path: str) -> str:
    rel_path = rel_path.replace("\\", "/").lstrip("/")
    full = os.path.normpath(os.path.join(vault_path, rel_path))
    if not full.startswith(os.path.normpath(vault_path)):
        raise ValueError(f"Path escapes vault root: {rel_path}")
    return full


def read_note(vault_path: str, rel_path: str) -> str:
    full = _safe_path(vault_path, rel_path)
    if not os.path.exists(full):
        return ""
    with open(full, "r", encoding="utf-8") as f:
        return f.read()


def write_note(vault_path: str, rel_path: str, content: str) -> None:
    full = _safe_path(vault_path, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def append_note(vault_path: str, rel_path: str, text: str) -> None:
    existing = read_note(vault_path, rel_path)
    if existing and not existing.endswith("\n"):
        existing += "\n"
    write_note(vault_path, rel_path, existing + text + "\n")


def list_notes(vault_path: str, folder: str = "") -> list:
    full = _safe_path(vault_path, folder) if folder else vault_path
    out = []
    for root, _dirs, files in os.walk(full):
        for fn in files:
            if fn.endswith(".md"):
                rel = os.path.relpath(os.path.join(root, fn), vault_path)
                out.append(rel.replace("\\", "/"))
    return out


def note_full_path(vault_path: str, rel_path: str) -> str:
    """Public accessor for the on-disk path of a note — used by rag.py to
    check file mtimes without reaching into memory.py's private helpers."""
    return _safe_path(vault_path, rel_path)


# ------------------------------------------------------------------ #
# Boot context — read at the start of every session
# ------------------------------------------------------------------ #

def boot_context(vault_path: str) -> str:
    parts = []
    index = read_note(vault_path, "VAULT-INDEX.md")
    if index:
        parts.append("### VAULT-INDEX.md\n" + index)

    priorities = read_note(vault_path, "Active Priorities.md")
    if priorities:
        parts.append("### Active Priorities.md\n" + priorities)

    last_note_path, last_note = _most_recent_daily_note(vault_path)
    if last_note:
        parts.append(f"### Most recent daily note ({last_note_path})\n" + last_note)

    return "\n\n".join(parts)


def relevant_notes(vault_path: str, user_text: str, max_notes: int = 3) -> str:
    """Removed in v3.1 — semantic search (rag.semantic_search) replaces
    this everywhere, with no keyword fallback, on every hardware tier.
    Kept as a stub only so an old import doesn't hard-crash; callers
    should be calling rag.semantic_search() directly now."""
    import rag
    return rag.semantic_search(vault_path, user_text, top_k=max_notes)


# ------------------------------------------------------------------ #
# Daily notes
# ------------------------------------------------------------------ #

def _daily_note_rel_path(date: datetime) -> str:
    month_folder = f"{date.month:02d} - {_MONTHS[date.month - 1]} {date.year}"
    filename = date.strftime("%Y-%m-%d") + ".md"
    return f"01 - Daily Notes/{month_folder}/{filename}"


def _most_recent_daily_note(vault_path: str, lookback_days: int = 5):
    today = datetime.now()
    for delta in range(1, lookback_days + 1):
        d = today - timedelta(days=delta)
        rel = _daily_note_rel_path(d)
        content = read_note(vault_path, rel)
        if content:
            return rel, content
    return None, None


def _new_daily_note_body(date: datetime) -> str:
    weekday = date.strftime("%A")
    month = _MONTHS[date.month - 1]
    now_time = date.strftime("%I:%M %p").lstrip("0")
    return (
        "---\n"
        "status: active\n"
        "project: personal\n"
        "type: log\n"
        "---\n"
        f"# {weekday}, {month} {date.day}, {date.year}\n\n"
        "## Index\n"
        "- **Session** — in progress.\n\n"
        f"## Session 1 — {now_time}\n\n"
        "### In Progress\n-\n\n"
        "### Done\n-\n\n"
        "### Notes\n-\n\n"
        "### Profile Updates\n-\n"
    )


def get_or_create_today_note(vault_path: str) -> str:
    today = datetime.now()
    rel = _daily_note_rel_path(today)
    if not read_note(vault_path, rel):
        write_note(vault_path, rel, _new_daily_note_body(today))
    return rel


def log_session_summary(vault_path: str, summary_line: str, notes: list = None) -> None:
    """Append a bullet to today's Notes section — the compact record of
    what this session covered, so the next session can pick up the thread."""
    rel = get_or_create_today_note(vault_path)
    content = read_note(vault_path, rel)

    bullet = f"- {summary_line}"
    if "### Notes\n-\n" in content:
        content = content.replace("### Notes\n-\n", f"### Notes\n{bullet}\n", 1)
    else:
        content += f"\n{bullet}\n"

    if notes:
        for n in notes:
            content += f"- {n}\n"

    write_note(vault_path, rel, content)


def log_interruption(vault_path: str, original_question: str, spoken: list,
                      remaining: list, inferred_reason: str = None) -> None:
    """Silent record of a barge-in — you talked over PAIO mid-answer.
    Never asked about out loud (per your instruction); just logged so a
    later session (or you, browsing the vault) can see what got cut off
    and PAIO's best guess at why, clearly marked as a guess rather than
    a confirmed fact."""
    if not vault_path:
        return
    rel = get_or_create_today_note(vault_path)
    content = read_note(vault_path, rel)

    unsaid = " ".join(remaining).strip()
    reason_line = f" (guessed reason: {inferred_reason})" if inferred_reason else " (reason unclear)"
    bullet = (
        f"- Interrupted while answering \"{original_question[:80]}\" — "
        f"left unsaid: \"{unsaid[:200]}\"{reason_line}"
    )

    if "### Notes\n-\n" in content:
        content = content.replace("### Notes\n-\n", f"### Notes\n{bullet}\n", 1)
    else:
        content += f"\n{bullet}\n"

    write_note(vault_path, rel, content)



# ------------------------------------------------------------------ #
# Jokes
# ------------------------------------------------------------------ #

def get_session_joke(vault_path: str, hint: str = "") -> str:
    raw = read_note(vault_path, "05 - Resources/Jokes.md")
    if not raw:
        return ""
    lines = [
        re.sub(r"^\d+\.\s*", "", ln).strip()
        for ln in raw.splitlines()
        if re.match(r"^\d+\.\s", ln.strip())
    ]
    if not lines:
        return ""

    if hint:
        hint_words = set(re.findall(r"[a-z0-9']+", hint.lower()))
        scored = []
        for joke in lines:
            joke_words = set(re.findall(r"[a-z0-9']+", joke.lower()))
            score = len(hint_words & joke_words)
            if score:
                scored.append((score, joke))
        if scored:
            scored.sort(reverse=True)
            top = [j for s, j in scored if s == scored[0][0]]
            return random.choice(top)

    return random.choice(lines)


# ------------------------------------------------------------------ #
# Simple rule-based memory writing (Ollama / local path)
# ------------------------------------------------------------------ #

_FACT_PATTERNS = [
    re.compile(r"\bremember (that )?(?P<fact>.+)", re.I),
    re.compile(r"\bmy (?P<fact>[\w\s]+ is [\w\s]+)", re.I),
    re.compile(r"\bi(?:'m| am) (?P<fact>[\w\s]+)", re.I),
    re.compile(r"\bi have (?P<fact>[\w\s]+)", re.I),
    re.compile(r"\bwe (?:decided|are going) to (?P<fact>[\w\s]+)", re.I),
]


def simple_extract_and_save(vault_path: str, user_text: str) -> None:
    """Lightweight heuristic memory write for the local Ollama path — no
    tool-calling required. Looks for durable-fact patterns and appends
    them to today's daily note. Not exhaustive by design; the cloud path
    (advanced, model-driven) does the deeper work."""
    for pattern in _FACT_PATTERNS:
        m = pattern.search(user_text)
        if m:
            fact = m.group("fact").strip().rstrip(".")
            if len(fact) > 3:
                rel = get_or_create_today_note(vault_path)
                content = read_note(vault_path, rel)
                bullet = f"- {fact}"
                if "### Notes\n-\n" in content:
                    content = content.replace("### Notes\n-\n", f"### Notes\n{bullet}\n", 1)
                else:
                    content += f"\n{bullet}\n"
                write_note(vault_path, rel, content)
            break


# ------------------------------------------------------------------ #
# Advanced tool-calling memory (cloud / ToRouter / Groq path)
# ------------------------------------------------------------------ #

CLOUD_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_note",
            "description": "Read a note from Mr. Pai's Brain vault by its relative path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path, e.g. '02 - Projects/Avenly.md'"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_note",
            "description": (
                "Create or overwrite a note in the vault. Always include valid YAML "
                "frontmatter (status/project/type) per the vault rules."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_note",
            "description": "Append text to the end of an existing note (or create it if missing).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["path", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_notes",
            "description": "List note paths in the vault, optionally under one folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "e.g. '02 - Projects'. Omit for the whole vault."},
                },
            },
        },
    },
]


def execute_tool(vault_path: str, name: str, arguments: dict) -> str:
    try:
        if name == "read_note":
            return read_note(vault_path, arguments["path"]) or "(empty or not found)"
        if name == "write_note":
            write_note(vault_path, arguments["path"], arguments["content"])
            return "ok"
        if name == "append_note":
            append_note(vault_path, arguments["path"], arguments["text"])
            return "ok"
        if name == "list_notes":
            return json.dumps(list_notes(vault_path, arguments.get("folder", "")))
        return f"unknown tool: {name}"
    except Exception as e:
        return f"error: {e}"


# ------------------------------------------------------------------ #
# Session state (crash recovery + rolling summary for the Ollama path)
# ------------------------------------------------------------------ #

def load_session_state() -> dict:
    if os.path.exists(_SESSION_STATE_PATH):
        try:
            with open(_SESSION_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"full_log": [], "rolling_summary": "", "active_provider": None}


def save_session_state(state: dict) -> None:
    try:
        with open(_SESSION_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"  [memory] could not save session_state.json: {e}")


def record_turn(state: dict, role: str, content: str) -> dict:
    state.setdefault("full_log", []).append({"role": role, "content": content})
    save_session_state(state)
    return state


def compact_if_needed(state: dict, summarize_fn, keep_recent: int = None) -> dict:
    """For the local/Ollama path: once the full log grows past the recent
    window, fold everything older into `rolling_summary` using whichever
    LLM is currently active (summarize_fn), so a small model still gets
    the substance of the whole conversation without the full transcript."""
    keep_recent = keep_recent or (config.MAX_HISTORY_TURNS * 2)
    full_log = state.get("full_log", [])
    if len(full_log) <= keep_recent:
        return state

    to_compact = full_log[:-keep_recent]
    recent = full_log[-keep_recent:]

    old_summary = state.get("rolling_summary", "")
    transcript = "\n".join(f"{t['role']}: {t['content']}" for t in to_compact)
    prompt = (
        "Compress the following into a short running summary (a few sentences), "
        "preserving anything durable — facts, decisions, open threads. "
        "Merge it with the existing summary rather than replacing it.\n\n"
        f"Existing summary:\n{old_summary}\n\nNew turns to fold in:\n{transcript}"
    )
    try:
        new_summary = summarize_fn(prompt)
    except Exception:
        new_summary = old_summary  # summarization failed — keep what we had

    state["rolling_summary"] = new_summary
    state["full_log"] = recent
    save_session_state(state)
    return state
