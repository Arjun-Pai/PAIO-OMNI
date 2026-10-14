# PAIO-Omni · orchestrator.py  v3.2
"""
The main application. The Bubble widget lives on the Qt main thread;
everything else (STT, TTS, Jev, ensemble/router/cloud/local LLM calls,
vault I/O) runs on a background thread and talks back to the UI only
through Qt signals (Bridge below), which is the safe, standard way to
cross threads in Qt — never call a QWidget method directly from a
worker thread.

v3.2 additions: complexity-scaled answering (jev_router.detect_full()
now also returns a complexity level; "complicated"/"very_complicated"
route through ensemble.py instead of router.py directly) and barge-in
interruption handling (see _speak_and_handle_interrupt) — talk over
PAIO mid-answer and it stops, listens, and silently logs what it didn't
get to say, without ever asking you why out loud.
"""

import os
import sys
import time

import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

import hardware
import roles
import personality as persona_lib
import config
import stt
import tts
import llm
import router
import ensemble
import memory
import rag
import jev_router
import wakeword
from bubble import Bubble, IDLE, LISTENING, THINKING, MAKING

_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paio.log")


class _Tee:
    """Mirrors console output to paio.log so a session can be reviewed
    after the fact without needing the terminal open and watched live."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass

    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass


def _enable_logging():
    try:
        log_file = open(_LOG_PATH, "a", encoding="utf-8")
        sys.stdout = _Tee(sys.__stdout__, log_file)
        sys.stderr = _Tee(sys.__stderr__, log_file)
    except Exception as e:
        print(f"  [log] could not open paio.log: {e}")


class Bridge(QObject):
    """The only thing worker threads are allowed to touch. Connect these
    signals to Bubble's methods on the main thread; Qt marshals the call
    across threads automatically because Bubble lives in a different
    thread than whatever emits these."""
    state_changed = Signal(str)
    text_ready = Signal(str)
    expand_requested = Signal()
    collapse_requested = Signal()


def _resolve_vault() -> str:
    vault_path = memory.find_vault()
    if vault_path:
        print(f"  Vault    : {vault_path}")
        return vault_path

    print("\n  Couldn't find the Brain vault (checked D:\\Brain and defaults).")
    entered = input("  Enter the full path to your Brain vault: ").strip().strip('"')
    if entered and os.path.isdir(entered):
        memory.remember_vault_path(entered)
        print(f"  Vault    : {entered} (saved)")
        return entered

    print("  Continuing without vault memory — facts won't persist this run.")
    return None


def _check_obsidian_installed():
    if os.name == "nt":
        common = [
            os.path.expandvars(r"%LOCALAPPDATA%\Obsidian\Obsidian.exe"),
            r"C:\Program Files\Obsidian\Obsidian.exe",
        ]
        if not any(os.path.exists(p) for p in common):
            print("  Note: Obsidian doesn't look installed — get it at https://obsidian.md")
    elif sys.platform == "darwin":
        if not os.path.exists("/Applications/Obsidian.app"):
            print("  Note: Obsidian doesn't look installed — get it at https://obsidian.md")


def _calibrate_mic_if_needed():
    cfg = config.load_user_config()
    if cfg.get("mic_threshold"):
        config.VAD_THRESHOLD = cfg["mic_threshold"]
        return

    print("\n  First run — calibrating mic. Stay quiet for 3 seconds ...")
    try:
        import sounddevice as sd
        recording = sd.rec(int(3 * config.SAMPLE_RATE), samplerate=config.SAMPLE_RATE,
                            channels=1, dtype="float32")
        sd.wait()
        noise_floor = float(np.sqrt(np.mean(recording ** 2)))
        threshold = max(noise_floor * 4, 0.008)
        config.VAD_THRESHOLD = threshold
        cfg["mic_threshold"] = threshold
        config.save_user_config(cfg)
        print(f"  Mic calibrated (threshold: {threshold:.4f})\n")
    except Exception as e:
        print(f"  Mic calibration skipped ({e})\n")


def startup():
    _enable_logging()
    print("\n╔══════════════════════════════════════════════╗")
    print("║          PAIO-Omni  v3.1                     ║")
    print("║  OpenRouter + Groq + Ollama · Jev · RAG      ║")
    print("╚══════════════════════════════════════════════╝\n")

    print("Detecting hardware ...")
    hw = hardware.detect()
    print(f"  {hardware.summary(hw)}\n")

    vault_path = _resolve_vault()
    _check_obsidian_installed()

    if vault_path:
        print("  Updating vault index (RAG) ...")
        n = rag.update_index(vault_path)
        print(f"  Re-embedded {n} note(s) (unchanged notes are skipped).")

    cfg = config.load_user_config()
    if not any(cfg.get(k) for k in ("openrouter_model_priority", "groq_model_priority",
                                     "ollama_cloud_model_priority")):
        print("\n  No setup found yet. Run onboarding.py first — it handles installing")
        print("  dependencies, API keys, and model priority in one guided pass:")
        print("\n      python onboarding.py\n")
        sys.exit(1)

    tts.load()
    whisper_m = hw["models"].get("whisper", "tiny.en")
    stt.load(whisper_model=whisper_m)

    _calibrate_mic_if_needed()

    if not llm.check_ollama():
        print("  Note: Ollama isn't running — that's fine as long as OpenRouter/Groq")
        print("  are reachable. Offline fallback needs: ollama serve")

    print(f"\n  Whisper  : {whisper_m}")
    print(f"  Tier     : {hw['tier']}")
    return hw, vault_path


def _beep():
    try:
        import sounddevice as sd
        t = np.linspace(0, 0.12, int(config.SAMPLE_RATE * 0.12), False)
        tone = 0.15 * np.sin(2 * np.pi * 880 * t)
        sd.play(tone.astype(np.float32), samplerate=config.SAMPLE_RATE)
    except Exception:
        pass


def _capture_one_utterance(timeout: float = 15.0):
    stt.start_listener()
    time.sleep(0.3)
    audio = stt.get_utterance(timeout=timeout)
    stt.stop()
    return audio


def _infer_interruption_reason(original_question: str, remaining: list, new_utterance: str) -> str:
    """One cheap, fast call — a guess, never presented as fact. If this
    fails for any reason, the interruption still gets logged, just
    without a guessed reason."""
    unsaid = " ".join(remaining).strip()
    prompt = (
        f'PAIO was answering "{original_question}" and got cut off before saying: '
        f'"{unsaid}". The person then said: "{new_utterance}". '
        "In under 8 words, guess why they likely interrupted. Just the guess, nothing else."
    )
    try:
        import cloud_llm
        return cloud_llm.chat(prompt, [], "brief", None,
                               provider="zenmux", model=cloud_llm.ZENMUX_MODEL).strip()
    except Exception:
        return None


def _speak_and_handle_interrupt(bridge: Bridge, hw: dict, vault_path: str,
                                 history: list, original_question: str) -> list:
    """Plays whatever's queued in TTS while watching for a barge-in. If
    interrupted: stops speaking, listens for what you actually wanted to
    say, silently logs what got cut off and a best-guess reason (never
    asks you about it out loud), then processes your new message as the
    next turn. Returns the (possibly further-updated) history."""
    watcher = wakeword.BargeInWatcher(on_interrupt=tts.interrupt)
    watcher.start()
    tts.wait()
    watcher.stop()

    interruption = tts.get_and_clear_interruption()
    if not interruption:
        return history

    print("\n  (interrupted — listening for what you want to say instead)")
    bridge.state_changed.emit(LISTENING)
    stt.clear_queue()
    stt.unmute()
    audio = _capture_one_utterance(timeout=15.0)
    new_text = stt.transcribe(audio).strip() if audio is not None else ""

    if vault_path:
        reason = None
        if new_text:
            reason = _infer_interruption_reason(
                original_question, interruption["remaining"], new_text)
        memory.log_interruption(
            vault_path, original_question,
            interruption["spoken"], interruption["remaining"], inferred_reason=reason,
        )

    if new_text:
        return _handle_turn(bridge, new_text, history, hw, vault_path)

    bridge.state_changed.emit(IDLE)
    return history


def _handle_turn(bridge: Bridge, text: str, history: list, hw: dict, vault_path: str) -> list:
    print(f"\nYou: {text}")
    decision = jev_router.detect_full(text)
    mode_key, complexity = decision["role"], decision["complexity"]
    print(f"  Role: {roles.mode_label(mode_key)}   Complexity: {complexity}")

    stt.mute()
    if complexity == "simple":
        response = router.respond(
            text=text, history=history, mode_key=mode_key, hw_models=hw["models"],
            vault_path=vault_path, speak_fn=tts.speak,
            state_fn=bridge.state_changed.emit,
        )
    else:
        # complicated / very_complicated -> ensemble.py's mixture-of-experts
        # path. Real latency/cost tradeoff, only taken when Jev (or its
        # fallback heuristic) judges it's actually worth it.
        response = ensemble.answer(
            text=text, history=history, complexity=complexity, primary_role=mode_key,
            hw_models=hw["models"], vault_path=vault_path, speak_fn=tts.speak,
            state_fn=bridge.state_changed.emit,
        )
    bridge.text_ready.emit(response)

    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": response})
    history = history[-(config.MAX_HISTORY_TURNS * 2):]

    # Record this turn's memory NOW, before watching for a possible
    # interrupt below — that watch can recursively handle a whole new
    # turn (if you talk over PAIO), and that recursive turn needs to be
    # recorded AFTER this one chronologically. Recording here, rather
    # than after _speak_and_handle_interrupt returns, is what guarantees
    # that order instead of logging this turn twice out of sequence.
    state = memory.load_session_state()
    memory.record_turn(state, "user", text)
    memory.record_turn(state, "assistant", response)
    memory.compact_if_needed(state, router.summarize_with_active_provider)

    if vault_path:
        memory.log_session_summary(vault_path, f"{text[:80]}")
        rag.update_index(vault_path)  # picks up whatever the tool-calling path just wrote

    history = _speak_and_handle_interrupt(bridge, hw, vault_path, history, text)

    stt.clear_queue()
    stt.unmute()
    bridge.state_changed.emit(IDLE)
    return history


def run():
    app = QApplication(sys.argv)
    bubble = Bubble()
    bridge = Bridge()
    bridge.state_changed.connect(bubble.set_state)
    bridge.text_ready.connect(bubble.show_text)
    bridge.expand_requested.connect(bubble.expand)
    bridge.collapse_requested.connect(bubble.collapse)

    hw, vault_path = startup()
    history = []

    def _run_flow(kind: str, audio):
        nonlocal history
        bridge.expand_requested.emit()
        bridge.state_changed.emit(LISTENING)
        _beep()

        if kind == "hotkey" and audio is not None:
            text = stt.transcribe(audio)
        else:
            print("\n👂  Listening for your command ...")
            command_audio = _capture_one_utterance(timeout=15.0)
            text = stt.transcribe(command_audio) if command_audio is not None else ""

        if text and text.strip():
            history = _handle_turn(bridge, text.strip(), history, hw, vault_path)
        else:
            bridge.state_changed.emit(THINKING)
            tts.speak("Didn't catch that.")
            tts.wait()
            bridge.state_changed.emit(IDLE)

        bridge.collapse_requested.emit()
        idle = wakeword.IdleListener(_on_trigger)
        idle.start()

    def _on_trigger(kind, audio):
        _run_flow(kind, audio)

    def _on_click():
        # Clicking the bubble is a manual wake — behaves like the voice
        # trigger (start listening immediately), just without needing
        # the wake phrase first.
        _run_flow("click", None)

    bubble.triggered.connect(_on_click)

    def _background_main():
        # Session-opening greeting: informal, in-character, works in a joke.
        joke = memory.get_session_joke(vault_path) if vault_path else ""
        if joke:
            opener_text = persona_lib.session_open_prompt(joke)
            bridge.state_changed.emit(THINKING)
            opener_response = router.respond(
                text=opener_text, history=[], mode_key="casual", hw_models=hw["models"],
                vault_path=vault_path, speak_fn=tts.speak,
                state_fn=bridge.state_changed.emit,
            )
            tts.wait()
            history.append({"role": "assistant", "content": opener_response})
            bridge.state_changed.emit(IDLE)

        print("\n👂  PAIO is up — say 'hey PAIO', hold Home, or click the bubble.\n")
        wakeword.start_hotkey_watcher()
        idle = wakeword.IdleListener(_on_trigger)
        idle.start()

    import threading
    threading.Thread(target=_background_main, daemon=True, name="paio-main-flow").start()

    bubble.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
