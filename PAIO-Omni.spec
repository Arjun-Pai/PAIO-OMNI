# PAIO-Omni PyInstaller build specification.
#
# Piper assets are included when the models/piper directory exists.
# Large Piper binaries and voice files are normally downloaded separately
# and should not be committed to the source repository.

from pathlib import Path


PROJECT_ROOT = Path(SPEC).resolve().parent
PIPER_DIR = PROJECT_ROOT / "models" / "piper"


def existing_data(path: Path, destination: str):
    if path.exists():
        return [(str(path), destination)]
    return []


datas = [
    *existing_data(PROJECT_ROOT / "personality.md", "."),
    *existing_data(PROJECT_ROOT / ".env.example", "."),
    *existing_data(PROJECT_ROOT / "my_voice.wav", "."),
    *existing_data(PIPER_DIR, "models/piper"),
]

hiddenimports = [
    "violawake_sdk",
    "pynput.keyboard._win32",
    "pynput.keyboard._darwin",
    "pynput.keyboard._xorg",
    "chromadb.telemetry.product.posthog",
    "sentence_transformers",
    "onnxruntime",
]

a = Analysis(
    ["onboarding.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PAIO-Omni",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)
