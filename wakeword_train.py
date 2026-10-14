# PAIO-Omni · wakeword_train.py  v3.1
"""
Trains a real "hey PAIO" wake-word model from your own recordings, using
ViolaWake rather than raw openWakeWord.

Why ViolaWake and not openWakeWord directly: openWakeWord's own custom-
training pipeline is in genuinely rough shape as of 2026 — it's pinned to
2022-era PyTorch/TensorFlow versions that no longer install cleanly on a
modern Python, and every community fix for it reaches for Docker or a
WSL2+CUDA box just to get a training run started. ViolaWake is a newer,
actively-maintained, Apache-2.0 alternative built for exactly this case —
training a custom wake word from a small number of real recordings, with
built-in TTS-based synthetic augmentation to fill out the rest — and it
exports a plain ONNX file, so the runtime side (wakeword.py) stays just
as lightweight as the openWakeWord plan would have been.

Usage:
    1. Drop 10 (or more) recordings of yourself saying "hey PAIO" into
       the voices/ folder (.wav, 16kHz mono is ideal but not required).
    2. Run: python wakeword_train.py
    3. It writes models/hey_paio.onnx — config.py already points at it.

This will take a while (ViolaWake generates synthetic TTS positives and
confusable negatives on top of your real samples before training) —
it's not instant, but it's a one-time cost, not a per-boot one.
"""

import os
import subprocess
import sys

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VOICES_DIR = os.path.join(_BASE_DIR, "voices")
MODEL_OUT = os.path.join(_BASE_DIR, "models", "hey_paio.onnx")
WAKE_WORD = "hey paio"


def _check_voices():
    if not os.path.isdir(VOICES_DIR):
        os.makedirs(VOICES_DIR, exist_ok=True)
    samples = [f for f in os.listdir(VOICES_DIR) if f.lower().endswith((".wav", ".mp3", ".m4a"))]
    if not samples:
        print(f"No recordings found in {VOICES_DIR}.")
        print('Add at least a handful of "hey PAIO" recordings (10 is a good start) and re-run.')
        sys.exit(1)
    print(f"Found {len(samples)} recording(s) in {VOICES_DIR}.")
    return samples


def main():
    _check_voices()
    os.makedirs(os.path.dirname(MODEL_OUT), exist_ok=True)

    print("\nDownloading ViolaWake's base temporal_cnn model (one-time) ...")
    subprocess.run([sys.executable, "-m", "violawake_download", "--model", "temporal_cnn"],
                   check=False)

    print(f'\nTraining "{WAKE_WORD}" from {VOICES_DIR} — this generates synthetic')
    print("positives/negatives on top of your real recordings, then trains.")
    print("Expect this to take a while on CPU; grab a coffee.\n")

    result = subprocess.run([
        "violawake-train",
        "--word", WAKE_WORD,
        "--positives", VOICES_DIR,
        "--output", MODEL_OUT,
        "--epochs", "50",
    ])

    if result.returncode != 0 or not os.path.exists(MODEL_OUT):
        print("\nTraining didn't produce a model file. Common causes:")
        print("  - ViolaWake isn't installed: pip install \"violawake[audio,download]\"")
        print("  - Too few/too quiet recordings in voices/ — try re-recording a few")
        print("    in a quieter room, or add more than 10 samples.")
        sys.exit(1)

    print(f"\nDone. Trained model written to {MODEL_OUT}")
    print("config.py already points WAKE_MODEL at this path — no further setup needed.")
    print('Optionally sanity-check it: violawake-eval --model "%s" --test-dir voices/'
          % MODEL_OUT)


if __name__ == "__main__":
    main()
