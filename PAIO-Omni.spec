# PAIO-Omni.spec — PyInstaller build spec, shared across all three OS
# build scripts. Run via the matching build_*.{bat,sh} for your platform
# rather than calling pyinstaller directly, so the right extra-data paths
# (Piper models, .env) are bundled correctly.
#
# Note: sentence-transformers downloads its embedding model
# (all-MiniLM-L6-v2) to a local cache on first use rather than bundling
# it here — the built executable will need internet on its very first
# RAG-indexing run to fetch it (one-time, then cached).

# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['onboarding.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('models', 'models'),
        ('personality.md', '.'),
        ('.env.example', '.'),
        ('my_voice.wav', '.'),
    ],
    hiddenimports=[
        'violawake_sdk',
        'pynput.keyboard._win32',
        'pynput.keyboard._darwin',
        'pynput.keyboard._xorg',
        'chromadb.telemetry.product.posthog',
        'sentence_transformers',
        'onnxruntime',
    ],
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
    name='PAIO-Omni',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,   # keep the console — bubble.py manages the window itself
    icon=None,
)
