# PAIO-Omni 3.2
<img width="1366" height="678" alt="image" src="https://github.com/user-attachments/assets/5e27d4da-ca6d-4b05-abb7-1e56c9a3aaf5" />

Your real-life Jarvis — a native floating orb, trained on your own
voice, that remembers you, thinks in your own personality, scales its
own effort to how hard your question actually is, and never has a
single point of failure.

## Setup — one command

```
pip install -r requirements.txt
python onboarding.py
```

`onboarding.py` is the entire installer — it replaces the old
`launcher.py` completely, and it's also how you change anything later
(API keys, model priority order, hardware-tier models). Nothing else in
this project handles setup. It walks through, in order:

1. Installs missing Python packages.
2. Installs Ollama if missing, starts it, and signs you in for Ollama
   Cloud (`ollama signin` — opens a browser once).
3. Asks for each API key one at a time — **ZenMux, OpenRouter, Groq,
   TypeSafe/Jev** — tests each one live with a real minimal request the
   moment you enter it, tells you pass/fail, and writes `.env` itself.
4. Fetches live model lists (OpenRouter, Groq) and shows a drag-to-
   reorder dialog for each, plus one for Ollama Cloud. ZenMux gets no
   dialog — it's a single hand-picked endpoint, not a ranked list.
5. Checks disk space, then pulls all 13 models for your detected
   hardware tier.
6. Offers to launch PAIO immediately.

## The fallback chain

**ZenMux → OpenRouter (ranked) → Groq (ranked) → Ollama Cloud (ranked) → Ollama local**

Every tier from OpenRouter down is a list you personally ranked in
onboarding — "what's first runs first, on failure the next one runs,"
all the way down each list before moving to the next tier.

**Real behavior change from v3.1, worth knowing**: this no longer asks
you out loud to pick between Groq/Ollama when something fails, and it
no longer sticks to whatever tier last worked for the rest of a
session. With 5 fixed tiers now fully predetermined by onboarding
rather than a runtime choice, and since cost is your top priority
(ZenMux/OpenRouter are the cheap tiers), **every turn starts back at
the top of the chain** — a transient failure shouldn't permanently
downgrade you to a worse or pricier tier once the cheap options are
working again. It still speaks a brief status line when it has to fall
past ZenMux, so you know what's actually answering you.

Ollama Cloud routes through the exact same local Ollama daemon and API
your local models use (`:cloud`-suffixed tags) — it's not a separate
client, just a different model name once you're signed in.

## Complexity-scaled answering (new)

Every message gets classified two ways by Jev in one call: which
**role** fits it (unchanged from v3.1), and how **complex** it is —
simple, complicated, or very_complicated. That second classification
now changes *how many models* answer you, not just which one:

| Complexity | What happens | Cost |
|---|---|---|
| Simple | One model, the normal fallback chain above | 1 call |
| Complicated | **Mixture of experts** — 3 different models (different roles, different angles) answer in parallel, then one more call synthesizes them into a single final answer | 4 calls |
| Very complicated | **Parallel tracks of mixture of experts** — 2 independent 3-expert groups run fully in parallel, each synthesized on its own, then one meta-synthesis combines both group answers | 9 calls |

This is a genuine latency/cost tradeoff, which is exactly why the
fallback heuristic (used only if Jev itself is unreachable) is
deliberately conservative — it defaults to "simple" unless a message is
clearly long or multi-part, since triggering a 9-call ensemble on a
guess would be the wrong failure mode. See `ensemble.py` for the expert
selection logic (each complexity tier pulls in roles that genuinely
complement the primary one Jev picked — e.g. a coding question also
consults `scientist` and `deep`, not two more copies of `coder`).

## Barge-in — talk over PAIO and it actually listens

While PAIO is speaking, interrupting it (hold Home, or just start
talking loud enough) cuts off playback within about 50ms — mid-sentence,
not just between sentences — and PAIO starts listening for what you
actually want to say. **It never asks you why you interrupted.**
Instead, it silently logs to today's daily note: what it was answering,
exactly what it didn't get to say, and a one-line guessed reason
inferred from what you said next — clearly marked as a guess, not
presented as fact.

Two ways to trigger it, with an honest caveat on one of them:
- **Home key** (reliable): hold it while PAIO is talking, same key as
  push-to-talk when idle.
- **Voice** (best-effort): sustained mic energy well above your
  calibrated ambient level, held for 300ms+, before it counts as an
  interruption. This is a real limitation worth understanding — without
  proper acoustic echo cancellation, PAIO's own voice bleeding into the
  mic through speaker/mic proximity is a known, hard problem. The
  threshold and sustain requirement in `wakeword.py`'s `BargeInWatcher`
  are there specifically to avoid PAIO interrupting itself; if it still
  happens too often on your hardware, the Home key is the reliable
  fallback.

## Customizing how the orb looks

All drawing logic lives in **`orb_visuals.py`** — four functions, one
per state (`idle`, `listening`, `thinking`, `making`), each just given a
`QPainter` and a `QRectF` to draw into. Right now all four draw a plain
black circle, on purpose — `bubble.py` owns everything mechanical
(dragging, click-vs-drag detection, expand/collapse, the animation
clock), and never needs to change no matter what you put in these four
functions. Edit `orb_visuals.py` freely; nothing else needs to know.

```python
def idle(painter, rect, phase):
    # phase: float 0..1, loops continuously — drive any animation off it
    ...

def listening(painter, rect, phase, ripple):
    # ripple: float 0..1, resets to 0 each time listening starts
    ...
```

## GLM-4.7-Flash

Confirmed real and in Ollama's library (~August 2026). Added to the
local matrix at `gpu_mega`/`fast`, replacing a tiny model
(`exaone3.5:2.4b`) that was oddly placed in the most powerful tier.

## Free/cheap GLM access — a reality check

No provider currently offers a guaranteed *permanent* unlimited free
tier for GLM-5.3-Flash — ZenMux's current $0 pricing and Z.ai's
promotional free access are both real today, but explicitly not stated
as permanent anywhere. That's exactly why ZenMux sits at the *top* of a
5-tier chain rather than being the only option — if it stops being
free, `router.py` just falls through to OpenRouter without you needing
to do anything.

## Building the executable

Unchanged mechanism — PyInstaller can't cross-compile, so run the
matching script once per platform:

- Windows: `build_windows.bat` → `dist\PAIO-Omni\PAIO-Omni.exe`
- macOS: `build_macos.sh` → `dist/PAIO-Omni/PAIO-Omni` (Gatekeeper will
  flag it unsigned the first time — right-click → Open, or
  `xattr -d com.apple.quarantine` it)
- Linux: `build_linux.sh` → `dist/PAIO-Omni/PAIO-Omni`

The spec now builds from `onboarding.py` (the new entry point) instead
of the old `launcher.py`. Copy your real `.env` into `dist/PAIO-Omni/`
next to the executable afterward — it isn't baked into the build.

## Files

| File | What it does |
|---|---|
| `onboarding.py` | **The entry point.** Full installer + ongoing settings/reconfiguration |
| `orchestrator.py` | PySide6 main app — boot, session opener, turn handling, barge-in |
| `bubble.py` | The native floating orb widget — mechanics only |
| `orb_visuals.py` | **Edit this to change how the orb looks.** Four drawing functions |
| `ensemble.py` | Mixture-of-experts / parallel-MoE for complicated questions |
| `router.py` | Walks the ZenMux → OpenRouter → Groq → Ollama Cloud → Ollama local chain |
| `jev_router.py` | Jev classification — role AND complexity, one call |
| `roles.py` | The 13 role definitions and system prompts |
| `cloud_llm.py` | ZenMux + OpenRouter + Groq client (OpenAI-compatible) |
| `llm.py` | Local Ollama client — also handles Ollama Cloud (`:cloud` tags) |
| `rag.py` | Semantic search over the vault (sentence-transformers + chromadb) |
| `memory.py` | Vault I/O, daily notes, jokes, rolling summary, interruption log |
| `personality.py` / `personality.md` | PAIO's persistent voice |
| `wakeword.py` / `wakeword_train.py` | Wake word + barge-in watcher (ViolaWake) |
| `hardware.py` | Detects your machine's tier, the 130-model matrix |
| `tester.py` | Benchmarks every configured model, HTML report |
| `stt.py` / `tts.py` | Speech-to-text (Whisper) / interruptible text-to-speech (Piper) |
| `config.py` | All the tunables in one place |

## Known limitations

- The RAG embedding model (`all-MiniLM-L6-v2`) downloads on first use if
  building the `.exe` — needs internet once, then it's cached.
- Ollama Cloud's model list in `onboarding.py` is hand-maintained, not
  live-fetched — no confirmed public catalog endpoint exists for it,
  unlike OpenRouter/Groq which both document a real one. Update
  `OLLAMA_CLOUD_CANDIDATES` in `onboarding.py` by hand if the roster
  changes (Ollama does deprecate/replace cloud models periodically).
- Voice-based barge-in is best-effort, per the caveat above — Home key
  is the reliable interrupt.
- `ensemble.py`'s multi-call paths add real latency (roughly 2-4x a
  single call for "complicated," more for "very_complicated") — by
  design, only for messages actually judged to need it.
