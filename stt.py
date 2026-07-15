import threading
import queue
import numpy as np

try:
    import sounddevice as sd
    _SD = True
except ImportError:
    _SD = False

try:
    from faster_whisper import WhisperModel
    _WHISPER = True
except ImportError:
    _WHISPER = False

import config

_model       = None
_audio_queue = queue.Queue()
_stop_event  = threading.Event()
_mute_event  = threading.Event()


def load(whisper_model: str):
    global _model
    if not _WHISPER:
        raise RuntimeError("faster-whisper not installed. Run: pip install faster-whisper")
    print(f"  Loading Whisper {whisper_model}  (first run downloads model) ...")
    try:
        _model = WhisperModel(whisper_model, device="cpu", compute_type="int8")
    except Exception:
        print("  int8 failed, retrying with float32 ...")
        _model = WhisperModel(whisper_model, device="cpu", compute_type="float32")
    print("  ✓ STT ready")


def _listener():
    RATE        = config.SAMPLE_RATE
    CHUNK       = int(RATE * 0.08)
    THRESH      = config.VAD_THRESHOLD
    MIN_SPEECH  = int(RATE * 0.3)
    SILENCE_END = int(RATE * config.SILENCE_DURATION)
    MAX_SPEECH  = int(RATE * config.MAX_RECORD_SECS)

    collecting  = False
    buffer      = []
    silent_samp = 0

    def _cb(indata, frames, time_info, status):
        nonlocal collecting, buffer, silent_samp
        if _mute_event.is_set():
            return
        chunk = indata[:, 0].copy()
        energy = float(np.sqrt(np.mean(chunk ** 2)))

        if not collecting:
            if energy > THRESH:
                collecting  = True
                silent_samp = 0
                buffer      = [chunk]
        else:
            buffer.append(chunk)
            total = sum(len(c) for c in buffer)
            if energy < THRESH:
                silent_samp += len(chunk)
                if silent_samp >= SILENCE_END and total >= MIN_SPEECH:
                    audio = np.concatenate(buffer)
                    _audio_queue.put(audio)
                    collecting  = False
                    buffer      = []
                    silent_samp = 0
            else:
                silent_samp = 0
            if total >= MAX_SPEECH:
                audio = np.concatenate(buffer)
                _audio_queue.put(audio)
                collecting  = False
                buffer      = []
                silent_samp = 0

    try:
        with sd.InputStream(
            samplerate=RATE,
            channels=1,
            dtype="float32",
            blocksize=CHUNK,
            callback=_cb,
            device=None,
        ):
            print("  ✓ Microphone open — listening ...")
            _stop_event.wait()
    except Exception as e:
        print(f"  [STT] Microphone error: {e}")


def start_listener():
    if not _SD:
        raise RuntimeError("sounddevice not installed. Run: pip install sounddevice")
    t = threading.Thread(target=_listener, daemon=True, name="paio-listener")
    t.start()
    return t


def get_utterance(timeout: float = None) -> np.ndarray | None:
    try:
        return _audio_queue.get(timeout=timeout)
    except queue.Empty:
        return None


def mute():
    _mute_event.set()
    while not _audio_queue.empty():
        try:
            _audio_queue.get_nowait()
        except queue.Empty:
            break


def unmute():
    """Resume the listener (call after TTS playback)."""
    # Flush any audio chunks captured while speaking to prevent bleeding/barge-in
    while not _audio_queue.empty():
        try:
            _audio_queue.get_nowait()
        except queue.Empty:
            break
    _mute_event.clear()


def stop():
    _stop_event.set()


def transcribe(audio: np.ndarray) -> str:
    if _model is None:
        raise RuntimeError("Call stt.load() first.")
    segments, _ = _model.transcribe(
        audio,
        beam_size=5,
        language="en",
        vad_filter=True,
    )
    return " ".join(s.text.strip() for s in segments).strip()
