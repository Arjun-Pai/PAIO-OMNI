PAIO-Omni voice directories have separate purposes.

This directory is for wake-word training recordings only.

Record yourself saying the wake phrase, for example:

    Hey PAIO

Add at least 10 recordings. More varied recordings usually produce a
more useful wake-word model.

Supported formats include:

    .wav
    .mp3
    .m4a

Example:

    voices/
    ├── recording-01.wav
    ├── recording-02.wav
    ├── recording-03.wav
    └── ...

After adding recordings, run:

    python wakeword_train.py

The generated wake-word model should be written to:

    models/hey_paio.onnx

These recordings are not Piper voice files.

Piper text-to-speech files belong in:

    models/piper/

The Piper directory should contain:

    models/piper/piper.exe
    models/piper/en_US-bryce-medium.onnx
    models/piper/en_US-bryce-medium.onnx.json

on Windows, or:

    models/piper/piper
    models/piper/en_US-bryce-medium.onnx
    models/piper/en_US-bryce-medium.onnx.json

on Linux and macOS.

Do not put Piper executables or Piper .onnx files in this directory.
