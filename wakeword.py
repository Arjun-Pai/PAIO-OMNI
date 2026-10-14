# PAIO-Omni · wakeword.py  v3.1
"""
Two ways to wake PAIO from its minimized/idle state:

  1. Voice — "hey PAIO", detected by a real custom-trained model (see
     wakeword_train.py) via ViolaWake, not a stand-in phrase. v3.0 used
     openWakeWord's bundled "hey_jarvis" model as a placeholder because
     training a real one needed openWakeWord's own custom-training
     pipeline, which turned out to be in bad shape in 2026 (see
     wakeword_train.py's docstring for why). ViolaWake replaces both the
     training path AND this runtime detection — if it isn't installed,
     or the trained model file doesn't exist yet, voice-wake is silently
     disabled and the hotkey still works.
  2. Hotkey — hold Home to record, release to end the utterance
     (push-to-talk; skips silence detection entirely).

Only one physical input stream runs at a time. While idle, this module
owns the microphone (lightweight — just wake-word scoring or silently
buffering during a hotkey hold). Once triggered, the orchestrator stops
this idle stream and hands the microphone to stt.py for the actual
command capture.
"""

import os
import threading
import time

import numpy as np

try:
    import sounddevice as sd
    _SD = True
except ImportError:
    _SD = False

try:
    from pynput import keyboard as _kb
    _PYNPUT = True
except ImportError:
    _PYNPUT = False

try:
    from violawake_sdk import WakeDetector
    _VIOLAWAKE = True
except ImportError:
    _VIOLAWAKE = False

import config

_RATE = config.SAMPLE_RATE
_CHUNK = 320  # ViolaWake's docs use 20ms chunks @ 16kHz (0.02 * 16000)

_hotkey_held = threading.Event()
_hotkey_key = getattr(_kb.Key, config.HOTKEY, None) if _PYNPUT else None


def _on_key_press(key):
    if key == _hotkey_key:
        _hotkey_held.set()


def _on_key_release(key):
    if key == _hotkey_key:
        _hotkey_held.clear()


def start_hotkey_watcher():
    """Starts a background global-hotkey watcher. No-op if pynput is
    unavailable (push-to-talk simply won't fire; wake word still can)."""
    if not _PYNPUT:
        print("  [wakeword] pynput not installed — Home-key push-to-talk disabled.")
        return None
    listener = _kb.Listener(on_press=_on_key_press, on_release=_on_key_release)
    listener.daemon = True
    listener.start()
    return listener


class IdleListener:
    """Owns the mic while PAIO is minimized. Calls on_trigger(kind, audio)
    where kind is "hotkey" or "voice", and audio is the captured buffer
    for "hotkey" (None for "voice" — the wake phrase itself isn't the
    command; the caller starts stt's normal listener next)."""

    def __init__(self, on_trigger):
        self.on_trigger = on_trigger
        self._stream = None
        self._stop = threading.Event()
        self._detector = None

        if _VIOLAWAKE:
            if os.path.exists(config.WAKE_MODEL):
                try:
                    self._detector = WakeDetector(
                        model=config.WAKE_MODEL,
                        threshold=config.WAKE_THRESHOLD,
                        confirm_count=config.WAKE_CONFIRM_COUNT,
                    )
                except Exception as e:
                    print(f"  [wakeword] could not load trained model: {e}")
            else:
                print(f"  [wakeword] no trained model at {config.WAKE_MODEL} — "
                      f"run wakeword_train.py first. Voice-wake disabled; hotkey still works.")

        self._ptt_buffer = []
        self._ptt_active = False
        self._pending_trigger = None  # set by _callback, fired by run() after the stream truly closes

    def _detect(self, chunk_f32: np.ndarray) -> bool:
        try:
            return bool(self._detector.detect(chunk_f32))
        except Exception:
            # Defensive fallback in case the installed ViolaWake version
            # expects int16 PCM rather than float32 — try once before
            # giving up on this chunk.
            try:
                int16 = (chunk_f32 * 32767).astype(np.int16)
                return bool(self._detector.detect(int16))
            except Exception:
                return False

    def _callback(self, indata, frames, time_info, status):
        if self._stop.is_set():
            return
        chunk = indata[:, 0].copy()

        held = _hotkey_held.is_set()
        if held and not self._ptt_active:
            self._ptt_active = True
            self._ptt_buffer = [chunk]
            return
        if held and self._ptt_active:
            self._ptt_buffer.append(chunk)
            return
        if not held and self._ptt_active:
            # Just released — finalize and hand off.
            self._ptt_active = False
            audio = np.concatenate(self._ptt_buffer) if self._ptt_buffer else None
            self._ptt_buffer = []
            self._pending_trigger = ("hotkey", audio)
            self._stop.set()
            return

        if self._detector is not None:
            if self._detect(chunk):
                self._pending_trigger = ("voice", None)
                self._stop.set()
                return

    def run(self):
        if not _SD:
            print("  [wakeword] sounddevice not installed — cannot idle-listen.")
            return
        self._stop.clear()
        self._pending_trigger = None
        try:
            with sd.InputStream(
                samplerate=_RATE, channels=1, dtype="float32",
                blocksize=_CHUNK, callback=self._callback, device=None,
            ):
                while not self._stop.is_set():
                    time.sleep(0.05)
            # Stream is now fully closed (we've exited the `with` block) —
            # safe for the trigger handler to open its own InputStream
            # without a race against this one still shutting down.
        except Exception as e:
            print(f"  [wakeword] microphone error: {e}")

        if self._pending_trigger is not None:
            kind, audio = self._pending_trigger
            self.on_trigger(kind, audio)

    def start(self):
        t = threading.Thread(target=self.run, daemon=True, name="paio-idle-listener")
        t.start()
        return t

    def stop(self):
        self._stop.set()


class BargeInWatcher:
    """Runs only while PAIO is speaking — watches for either the Home
    key or sustained mic energy, and calls on_interrupt() the moment
    either fires. Voice-based barge-in is best-effort: without real
    acoustic echo cancellation, PAIO's own voice bleeding into the mic
    through speaker/mic proximity is a known, hard-to-fully-solve
    problem, which is why this requires a threshold well above normal
    ambient level AND sustained detection (not a single blip) before
    triggering — the Home key remains the reliable way to interrupt.
    """

    _VOICE_THRESHOLD_MULTIPLIER = 3.0   # well above calibrated ambient VAD_THRESHOLD
    _SUSTAIN_SECONDS = 0.3               # must stay above threshold this long to count

    def __init__(self, on_interrupt):
        self.on_interrupt = on_interrupt
        self._stop = threading.Event()
        self._above_threshold_since = None

    def _callback(self, indata, frames, time_info, status):
        if self._stop.is_set():
            return

        if _hotkey_held.is_set():
            self._stop.set()
            threading.Thread(target=self.on_interrupt, daemon=True).start()
            return

        chunk = indata[:, 0]
        rms = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) else 0.0
        threshold = config.VAD_THRESHOLD * self._VOICE_THRESHOLD_MULTIPLIER

        now = time.monotonic()
        if rms > threshold:
            if self._above_threshold_since is None:
                self._above_threshold_since = now
            elif now - self._above_threshold_since >= self._SUSTAIN_SECONDS:
                self._stop.set()
                threading.Thread(target=self.on_interrupt, daemon=True).start()
        else:
            self._above_threshold_since = None

    def run(self):
        if not _SD:
            return
        self._stop.clear()
        self._above_threshold_since = None
        try:
            with sd.InputStream(
                samplerate=_RATE, channels=1, dtype="float32",
                blocksize=_CHUNK, callback=self._callback, device=None,
            ):
                while not self._stop.is_set():
                    time.sleep(0.05)
        except Exception as e:
            print(f"  [wakeword] barge-in watcher microphone error: {e}")

    def start(self):
        t = threading.Thread(target=self.run, daemon=True, name="paio-bargein-watcher")
        t.start()
        return t

    def stop(self):
        self._stop.set()
