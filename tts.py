"""PAIO-Omni TTS using Piper.

Expected default files:

Windows:
    models/piper/piper.exe

Linux/macOS:
    models/piper/piper

Voice files:
    models/piper/en_US-bryce-medium.onnx
    models/piper/en_US-bryce-medium.onnx.json

The paths can be overridden with:

    PAIO_PIPER_EXE
    PAIO_PIPER_MODEL
    PAIO_PIPER_CONFIG
"""

from __future__ import annotations

import os
import platform
import queue
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import sounddevice as sd
import soundfile as sf


_tts_queue = queue.Queue()
_worker_thread = None
_loaded = False
_warned_not_loaded = False

_interrupt_event = threading.Event()
_last_interruption = None
_lock = threading.Lock()

_BASE_DIR = Path(__file__).resolve().parent
_PIPER_DIR = _BASE_DIR / "models" / "piper"


def _first_existing(*paths: Path) -> str:
    for path in paths:
        if path and path.exists():
            return str(path)
    return str(paths[0]) if paths else ""


def _default_piper_executable() -> str:
    override = os.environ.get("PAIO_PIPER_EXE")
    if override:
        return override

    if platform.system() == "Windows":
        candidates = (
            _PIPER_DIR / "piper.exe",
            _PIPER_DIR / "piper" / "piper.exe",
        )
    else:
        candidates = (
            _PIPER_DIR / "piper",
            _PIPER_DIR / "piper" / "piper",
        )

    return _first_existing(*candidates)


def _default_voice_model() -> str:
    override = os.environ.get("PAIO_PIPER_MODEL")
    if override:
        return override

    candidates = (
        _PIPER_DIR / "en_US-bryce-medium.onnx",
        _PIPER_DIR / "mv2.onnx",
        _PIPER_DIR / "piper" / "en_US-bryce-medium.onnx",
        _PIPER_DIR / "piper" / "mv2.onnx",
    )

    return _first_existing(*candidates)


def _auto_config_for_model(model_path: str) -> str:
    override = os.environ.get("PAIO_PIPER_CONFIG")
    if override:
        return override

    model = Path(model_path)

    if model.suffix == ".onnx":
        same_stem = Path(f"{model}.json")
        if same_stem.exists():
            return str(same_stem)

    candidates = (
        model.parent / f"{model.name}.json",
        _PIPER_DIR / "en_US-bryce-medium.onnx.json",
        _PIPER_DIR / "piper" / "en_US-bryce-medium.onnx.json",
    )

    return _first_existing(*candidates)


_PIPER_EXE = _default_piper_executable()
_PIPER_MODEL = _default_voice_model()
_PIPER_CONFIG = _auto_config_for_model(_PIPER_MODEL)


def piper_status() -> dict:
    """Return the current Piper asset status."""
    executable = Path(_PIPER_EXE)
    model = Path(_PIPER_MODEL)
    config = Path(_PIPER_CONFIG)

    return {
        "executable": str(executable),
        "model": str(model),
        "config": str(config),
        "executable_exists": executable.exists(),
        "model_exists": model.exists(),
        "config_exists": config.exists(),
        "ready": executable.exists() and model.exists() and config.exists(),
    }


def print_piper_status() -> bool:
    status = piper_status()

    print(f"  Piper executable: {status['executable']}")
    print(f"  Piper model:      {status['model']}")
    print(f"  Piper config:     {status['config']}")

    if not status["executable_exists"]:
        if platform.system() == "Windows":
            print("  Missing Piper executable. Expected models/piper/piper.exe")
        else:
            print("  Missing Piper executable. Expected models/piper/piper")

    if not status["model_exists"]:
        print("  Missing Piper voice model (.onnx).")

    if not status["config_exists"]:
        print("  Missing Piper voice configuration (.onnx.json).")

    return bool(status["ready"])


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part for part in parts if part.strip()]


def _synthesize_to_wav(sentence: str) -> str | None:
    wav_path = None

    try:
        fd, wav_path = tempfile.mkstemp(prefix="paio_tts_", suffix=".wav")
        os.close(fd)

        command = [
            _PIPER_EXE,
            "--model",
            _PIPER_MODEL,
            "--config",
            _PIPER_CONFIG,
            "--output_file",
            wav_path,
        ]

        subprocess.run(
            command,
            input=sentence.encode("utf-8"),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        return wav_path

    except Exception as exc:
        print(f"  [TTS Worker] Piper error: {exc}")

        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass

        return None


def _play_sentence_interruptible(wav_path: str) -> bool:
    """Return False if playback was interrupted."""
    try:
        data, sample_rate = sf.read(
            wav_path,
            dtype="float32",
            always_2d=True,
        )

        sd.play(data, samplerate=sample_rate)
        stream = sd.get_stream()

        while stream is not None and stream.active:
            if _interrupt_event.is_set():
                sd.stop()
                return False

            time.sleep(0.05)

        return True

    finally:
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass


def _tts_worker():
    global _last_interruption

    while True:
        text = _tts_queue.get()

        if text is None:
            _tts_queue.task_done()
            break

        _interrupt_event.clear()
        sentences = _split_sentences(text)
        spoken = []
        interrupted_at = None

        for index, sentence in enumerate(sentences):
            if _interrupt_event.is_set():
                interrupted_at = index
                break

            wav_path = _synthesize_to_wav(sentence)

            if wav_path is None:
                continue

            completed = _play_sentence_interruptible(wav_path)

            if not completed:
                interrupted_at = index
                break

            spoken.append(sentence)

        if interrupted_at is not None:
            with _lock:
                _last_interruption = {
                    "original": text,
                    "spoken": spoken,
                    "remaining": sentences[interrupted_at:],
                }

            try:
                while True:
                    _tts_queue.get_nowait()
                    _tts_queue.task_done()
            except queue.Empty:
                pass

        _tts_queue.task_done()


def load() -> bool:
    global _worker_thread, _loaded

    print("  Loading Piper TTS engine ...")

    if not print_piper_status():
        print("  [TTS] Piper is not ready.")
        print("  See README.md for Piper installation instructions.")
        _loaded = False
        return False

    if platform.system() != "Windows":
        try:
            os.chmod(_PIPER_EXE, os.stat(_PIPER_EXE).st_mode | 0o111)
        except OSError:
            pass

    if _worker_thread is None or not _worker_thread.is_alive():
        _worker_thread = threading.Thread(
            target=_tts_worker,
            daemon=True,
            name="paio-piper-tts",
        )
        _worker_thread.start()

    _loaded = True
    print("  Piper TTS worker ready.")
    return True


def speak(text: str):
    global _warned_not_loaded

    if not _loaded:
        if not _warned_not_loaded:
            print("  [TTS] speak() ignored because Piper is not loaded.")
            _warned_not_loaded = True
        return

    clean_text = _clean(text)

    if clean_text:
        _tts_queue.put(clean_text)


def wait():
    """Block until all queued text has finished speaking."""
    _tts_queue.join()


def is_speaking() -> bool:
    stream = sd.get_stream()
    return (stream is not None and stream.active) or not _tts_queue.empty()


def interrupt():
    """Immediately interrupt current Piper playback."""
    _interrupt_event.set()


def get_and_clear_interruption() -> dict | None:
    """Return and clear the latest interruption information."""
    global _last_interruption

    with _lock:
        result = _last_interruption
        _last_interruption = None
        return result


def _clean(text: str) -> str:
    text = re.sub(r"[\*#`_-]", "", text)
    return text.replace("\n", " ").strip()
