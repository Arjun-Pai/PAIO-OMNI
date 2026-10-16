# PAIO-Omni · orchestrator.py  v3.2
"""
The main application. The Bubble widget lives on the Qt main thread;
everything else (STT, TTS, Jev, ensemble/router/cloud/local LLM calls,
vault I/O) runs on a background thread and talks back to the UI only
through Qt signals.

v3.2 additions:
- Complexity-scaled answering.
- Mixture-of-experts handling.
- Barge-in interruption handling.
- Runtime logs stored in the PAIO user data directory.
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

import config
import ensemble
import hardware
import jev_router
import llm
import memory
import personality as persona_lib
import rag
import roles
import router
import stt
import tts
import wakeword
from bubble import Bubble, IDLE, LISTENING, THINKING, MAKING


_LOG_PATH = config.LOG_PATH


class _Tee:
    """Mirror console output to the PAIO runtime log."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            try:
                stream.write(data)
                stream.flush()
            except Exception:
                pass

    def flush(self):
        for stream in self.streams:
            try:
                stream.flush()
            except Exception:
                pass


def _enable_logging():
    try:
        os.makedirs(os.path.dirname(str(_LOG_PATH)), exist_ok=True)

        log_file = open(
            _LOG_PATH,
            "a",
            encoding="utf-8",
        )

        sys.stdout = _Tee(sys.__stdout__, log_file)
        sys.stderr = _Tee(sys.__stderr__, log_file)

    except Exception as exc:
        print(f"  [log] could not open PAIO log: {exc}")


class Bridge(QObject):
    """Signals used to communicate with the Bubble widget."""

    state_changed = Signal(str)
    text_ready = Signal(str)
    expand_requested = Signal()
    collapse_requested = Signal()


def _resolve_vault() -> str | None:
    vault_path = memory.find_vault()

    if vault_path:
        print(f"  Vault    : {vault_path}")
        return vault_path

    print(
        "\n  Couldn't find the Brain vault "
        "(checked configured defaults)."
    )

    entered = input(
        "  Enter the full path to your Brain vault "
        "or press Enter to continue without one: "
    ).strip().strip('"')

    if entered and os.path.isdir(entered):
        memory.remember_vault_path(entered)
        print(f"  Vault    : {entered} (saved)")
        return entered

    print(
        "  Continuing without vault memory — "
        "facts won't persist this run."
    )
    return None


def _check_obsidian_installed():
    if os.name == "nt":
        common_paths = [
            os.path.expandvars(
                r"%LOCALAPPDATA%\Obsidian\Obsidian.exe"
            ),
            r"C:\Program Files\Obsidian\Obsidian.exe",
        ]

        if not any(os.path.exists(path) for path in common_paths):
            print(
                "  Note: Obsidian doesn't look installed — "
                "get it at https://obsidian.md"
            )

    elif sys.platform == "darwin":
        if not os.path.exists("/Applications/Obsidian.app"):
            print(
                "  Note: Obsidian doesn't look installed — "
                "get it at https://obsidian.md"
            )


def _calibrate_mic_if_needed():
    cfg = config.load_user_config()

    if cfg.get("mic_threshold"):
        config.VAD_THRESHOLD = cfg["mic_threshold"]
        return

    print(
        "\n  First run — calibrating mic. "
        "Stay quiet for 3 seconds ..."
    )

    try:
        import sounddevice as sd

        recording = sd.rec(
            int(3 * config.SAMPLE_RATE),
            samplerate=config.SAMPLE_RATE,
            channels=1,
            dtype="float32",
        )

        sd.wait()

        noise_floor = float(np.sqrt(np.mean(recording**2)))
        threshold = max(noise_floor * 4, 0.008)

        config.VAD_THRESHOLD = threshold
        cfg["mic_threshold"] = threshold
        config.save_user_config(cfg)

        print(f"  Mic calibrated (threshold: {threshold:.4f})\n")

    except Exception as exc:
        print(f"  Mic calibration skipped ({exc})\n")


def startup():
    _enable_logging()

    print("\n╔══════════════════════════════════════════════╗")
    print("║          PAIO-Omni  v3.2                     ║")
    print("║  OpenRouter + Groq + Ollama · Jev · RAG      ║")
    print("╚══════════════════════════════════════════════╝\n")

    print(f"Runtime data: {config.get_runtime_dir()}")

    print("Detecting hardware ...")

    hw = hardware.detect()
    print(f"  {hardware.summary(hw)}\n")

    vault_path = _resolve_vault()
    _check_obsidian_installed()

    if vault_path:
        print("  Updating vault index (RAG) ...")
        count = rag.update_index(vault_path)
        print(f"  Re-embedded {count} note(s).")

    cfg = config.load_user_config()

    configured = any(
        cfg.get(key)
        for key in (
            "openrouter_model_priority",
            "groq_model_priority",
            "ollama_cloud_model_priority",
        )
    )

    if not configured:
        print("\n  No setup found yet.")
        print("  Run the guided setup before launching PAIO:")
        print("\n      paio setup\n")
        print("  Or, from the source checkout:")
        print("\n      python onboarding.py\n")
        sys.exit(1)

    tts.load()

    whisper_model = hw["models"].get(
        "whisper",
        "tiny.en",
    )

    stt.load(whisper_model=whisper_model)

    _calibrate_mic_if_needed()

    if not llm.check_ollama():
        print(
            "  Note: Ollama isn't running — that's fine as long as "
            "OpenRouter/Groq are reachable."
        )
        print(
            "  Offline fallback needs Ollama running with: "
            "ollama serve"
        )

    print(f"\n  Whisper  : {whisper_model}")
    print(f"  Tier     : {hw['tier']}")
    print(f"  Piper    : {tts._PIPER_EXE}")
    print(f"  TTS model: {tts._PIPER_MODEL}")

    return hw, vault_path


def _beep():
    try:
        import sounddevice as sd

        time_values = np.linspace(
            0,
            0.12,
            int(config.SAMPLE_RATE * 0.12),
            False,
        )

        tone = 0.15 * np.sin(
            2 * np.pi * 880 * time_values
        )

        sd.play(
            tone.astype(np.float32),
            samplerate=config.SAMPLE_RATE,
        )

    except Exception:
        pass


def _capture_one_utterance(timeout: float = 15.0):
    stt.start_listener()
    time.sleep(0.3)

    audio = stt.get_utterance(timeout=timeout)

    stt.stop()
    return audio


def _infer_interruption_reason(
    original_question: str,
    remaining: list,
    new_utterance: str,
) -> str | None:
    """Return a short, explicitly inferred interruption reason."""
    unsaid = " ".join(remaining).strip()

    prompt = (
        f'PAIO was answering "{original_question}" and got cut off '
        f'before saying: "{unsaid}". '
        f'The person then said: "{new_utterance}". '
        "In under 8 words, guess why they likely interrupted. "
        "Just the guess, nothing else."
    )

    try:
        import cloud_llm

        return cloud_llm.chat(
            prompt,
            [],
            "brief",
            None,
            provider="zenmux",
            model=cloud_llm.ZENMUX_MODEL,
        ).strip()

    except Exception:
        return None


def _speak_and_handle_interrupt(
    bridge: Bridge,
    hw: dict,
    vault_path: str | None,
    history: list,
    original_question: str,
) -> list:
    """Play queued TTS while watching for a barge-in interruption."""
    watcher = wakeword.BargeInWatcher(
        on_interrupt=tts.interrupt,
    )

    watcher.start()

    tts.wait()

    watcher.stop()

    interruption = tts.get_and_clear_interruption()

    if not interruption:
        return history

    print(
        "\n  (interrupted — listening for what "
        "you want to say instead)"
    )

    bridge.state_changed.emit(LISTENING)

    stt.clear_queue()
    stt.unmute()

    audio = _capture_one_utterance(timeout=15.0)

    new_text = (
        stt.transcribe(audio).strip()
        if audio is not None
        else ""
    )

    if vault_path:
        reason = None

        if new_text:
            reason = _infer_interruption_reason(
                original_question,
                interruption["remaining"],
                new_text,
            )

        memory.log_interruption(
            vault_path,
            original_question,
            interruption["spoken"],
            interruption["remaining"],
            inferred_reason=reason,
        )

    if new_text:
        return _handle_turn(
            bridge,
            new_text,
            history,
            hw,
            vault_path,
        )

    bridge.state_changed.emit(IDLE)
    return history


def _handle_turn(
    bridge: Bridge,
    text: str,
    history: list,
    hw: dict,
    vault_path: str | None,
) -> list:
    print(f"\nYou: {text}")

    decision = jev_router.detect_full(text)

    mode_key = decision["role"]
    complexity = decision["complexity"]

    print(
        f"  Role: {roles.mode_label(mode_key)}"
        f"   Complexity: {complexity}"
    )

    stt.mute()

    if complexity == "simple":
        response = router.respond(
            text=text,
            history=history,
            mode_key=mode_key,
            hw_models=hw["models"],
            vault_path=vault_path,
            speak_fn=tts.speak,
            state_fn=bridge.state_changed.emit,
        )

    else:
        response = ensemble.answer(
            text=text,
            history=history,
            complexity=complexity,
            primary_role=mode_key,
            hw_models=hw["models"],
            vault_path=vault_path,
            speak_fn=tts.speak,
            state_fn=bridge.state_changed.emit,
        )

    bridge.text_ready.emit(response)

    history.append(
        {
            "role": "user",
            "content": text,
        }
    )

    history.append(
        {
            "role": "assistant",
            "content": response,
        }
    )

    history = history[-(config.MAX_HISTORY_TURNS * 2):]

    state = memory.load_session_state()

    memory.record_turn(
        state,
        "user",
        text,
    )

    memory.record_turn(
        state,
        "assistant",
        response,
    )

    memory.compact_if_needed(
        state,
        router.summarize_with_active_provider,
    )

    if vault_path:
        memory.log_session_summary(
            vault_path,
            f"{text[:80]}",
        )

        rag.update_index(vault_path)

    history = _speak_and_handle_interrupt(
        bridge,
        hw,
        vault_path,
        history,
        text,
    )

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

            command_audio = _capture_one_utterance(
                timeout=15.0,
            )

            text = (
                stt.transcribe(command_audio)
                if command_audio is not None
                else ""
            )

        if text and text.strip():
            history = _handle_turn(
                bridge,
                text.strip(),
                history,
                hw,
                vault_path,
            )

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
        # Clicking the bubble manually starts listening.
        _run_flow("click", None)

    bubble.triggered.connect(_on_click)

    def _background_main():
        # Session-opening greeting.
        joke = (
            memory.get_session_joke(vault_path)
            if vault_path
            else ""
        )

        if joke:
            opener_text = persona_lib.session_open_prompt(joke)

            bridge.state_changed.emit(THINKING)

            opener_response = router.respond(
                text=opener_text,
                history=[],
                mode_key="casual",
                hw_models=hw["models"],
                vault_path=vault_path,
                speak_fn=tts.speak,
                state_fn=bridge.state_changed.emit,
            )

            tts.wait()

            history.append(
                {
                    "role": "assistant",
                    "content": opener_response,
                }
            )

            bridge.state_changed.emit(IDLE)

        print(
            "\n👂  PAIO is up — say 'hey PAIO', "
            "hold Home, or click the bubble.\n"
        )

        wakeword.start_hotkey_watcher()

        idle = wakeword.IdleListener(_on_trigger)
        idle.start()

    import threading

    threading.Thread(
        target=_background_main,
        daemon=True,
        name="paio-main-flow",
    ).start()

    bubble.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run()
```

Verify the file before running it:

```bash
python -m py_compile orchestrator.py
```

Note: this version requires the updated `config.py` to provide:

```python
config.LOG_PATH
config.get_runtime_dir()
```

Those are included in the complete `config.py` I provided in the previous batch.
