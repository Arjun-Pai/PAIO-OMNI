"""PAIO-Omni TTS using Piper (bryce medium).

Expected default files:
  models/piper/piper.exe
  models/piper/en_US-bryce-medium.onnx
  models/piper/en_US-bryce-medium.onnx.json
"""

import os
import queue
import re
import subprocess
import tempfile
import threading

import sounddevice as sd
import soundfile as sf

_tts_queue = queue.Queue()
_worker_thread = None
_loaded = False
_warned_not_loaded = False

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PIPER_DIR = os.path.join(_BASE_DIR, "models", "piper")


def _first_existing(*paths: str) -> str:
    for p in paths:
        if p and os.path.exists(p):
            return p
    return paths[0] if paths else ""


_DEFAULT_EXE = _first_existing(
    os.path.join(_PIPER_DIR, "piper.exe"),
    os.path.join(_PIPER_DIR, "piper", "piper.exe"),
)

_DEFAULT_MODEL = _first_existing(
    os.path.join(_PIPER_DIR, "en_US-bryce-medium.onnx"),
    os.path.join(_PIPER_DIR, "mv2.onnx"),
    os.path.join(_PIPER_DIR, "piper", "en_US-bryce-medium.onnx"),
    os.path.join(_PIPER_DIR, "piper", "mv2.onnx"),
)


def _auto_config_for_model(model_path: str) -> str:
    if model_path.endswith(".onnx"):
        same_stem = model_path + ".json"
        if os.path.exists(same_stem):
            return same_stem

    candidates = [
        os.path.join(_PIPER_DIR, "en_US-bryce-medium.onnx.json"),
        os.path.join(_PIPER_DIR, "piper", "en_US-bryce-medium.onnx.json"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return model_path + ".json"

_PIPER_EXE = os.environ.get("PAIO_PIPER_EXE", _DEFAULT_EXE)
_PIPER_MODEL = os.environ.get("PAIO_PIPER_MODEL", _DEFAULT_MODEL)
_PIPER_CONFIG = os.environ.get("PAIO_PIPER_CONFIG", _auto_config_for_model(_PIPER_MODEL))


def _tts_worker():
    while True:
        text = _tts_queue.get()
        if text is None:
            _tts_queue.task_done()
            break

        wav_path = None
        try:
            fd, wav_path = tempfile.mkstemp(prefix="paio_tts_", suffix=".wav")
            os.close(fd)

            cmd = [
                _PIPER_EXE,
                "--model",
                _PIPER_MODEL,
                "--config",
                _PIPER_CONFIG,
                "--output_file",
                wav_path,
            ]
            subprocess.run(cmd, input=text.encode("utf-8"), check=True, stdout=subprocess.DEVNULL)

            data, sample_rate = sf.read(wav_path, dtype="float32", always_2d=True)
            sd.play(data, samplerate=sample_rate)
            sd.wait()

        except Exception as e:
            print(f"  [TTS Worker] error: {e}")
        finally:
            if wav_path and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except OSError:
                    pass
            _tts_queue.task_done()


def load():
    global _worker_thread, _loaded

    print("  Loading Piper TTS engine ...")

    if not os.path.exists(_PIPER_EXE):
        print(f"  [TTS] Missing Piper executable: {_PIPER_EXE}")
        print("  [TTS] Download Piper and place piper.exe + DLLs in models/piper")
        _loaded = False
        return

    if not os.path.exists(_PIPER_MODEL):
        print(f"  [TTS] Missing voice model: {_PIPER_MODEL}")
        print("  [TTS] Download en_US-bryce-medium.onnx and .onnx.json into models/piper")
        _loaded = False
        return

    if not os.path.exists(_PIPER_CONFIG):
        print(f"  [TTS] Missing voice config: {_PIPER_CONFIG}")
        _loaded = False
        return

    _worker_thread = threading.Thread(target=_tts_worker, daemon=True)
    _worker_thread.start()
    _loaded = True
    print("  ✓ TTS Background Worker ready (Piper bryce medium)")


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


def _clean(text: str) -> str:
    text = re.sub(r"[\*#`_-]", "", text)
    text = text.replace("\n", " ").strip()
    return text