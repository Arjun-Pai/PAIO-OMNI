"""Command-line entry point for PAIO-Omni.

Supported commands:

    paio
    paio setup
    paio start
    paio check
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _source_root() -> Path:
    """Return the repository/source root when running from a checkout."""
    return Path(__file__).resolve().parent.parent


def _find_script(filename: str) -> Path | None:
    """Find a PAIO script in a source checkout."""
    root = _source_root()
    candidate = root / filename
    return candidate if candidate.exists() else None


def _configuration_exists() -> bool:
    """Return whether onboarding appears to have completed."""
    try:
        import config

        cfg = config.load_user_config()
        return any(
            cfg.get(key)
            for key in (
                "openrouter_model_priority",
                "groq_model_priority",
                "ollama_cloud_model_priority",
            )
        )
    except Exception:
        return False


def _run_python_script(script: Path) -> int:
    return subprocess.call([sys.executable, str(script)])


def _run_setup() -> int:
    script = _find_script("onboarding.py")

    if script is None:
        print(
            "PAIO setup could not locate onboarding.py.\n"
            "If PAIO was installed as a wheel, reinstall it from the repository "
            "root with:\n\n"
            "    pip install .\n"
        )
        return 1

    return _run_python_script(script)


def _run_start() -> int:
    script = _find_script("orchestrator.py")

    if script is None:
        print(
            "PAIO could not locate orchestrator.py.\n"
            "Run this command from a PAIO source checkout or reinstall PAIO "
            "from the repository root."
        )
        return 1

    if not _configuration_exists():
        print("PAIO has not been configured yet.")
        print("Run `paio setup` first.")
        return 1

    return _run_python_script(script)


def _run_check() -> int:
    print("PAIO-Omni installation check")
    print("----------------------------")

    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {sys.platform}")

    ollama = shutil.which("ollama")
    print(f"Ollama: {'found at ' + ollama if ollama else 'not found'}")

    try:
        import tts

        print(f"Piper executable: {tts._PIPER_EXE}")
        print(
            "Piper executable status: "
            + ("found" if os.path.exists(tts._PIPER_EXE) else "missing")
        )
        print(f"Piper model: {tts._PIPER_MODEL}")
        print(
            "Piper model status: "
            + ("found" if os.path.exists(tts._PIPER_MODEL) else "missing")
        )
        print(f"Piper config: {tts._PIPER_CONFIG}")
        print(
            "Piper config status: "
            + ("found" if os.path.exists(tts._PIPER_CONFIG) else "missing")
        )
    except Exception as exc:
        print(f"Piper check failed: {exc}")

    print()
    if _configuration_exists():
        print("PAIO configuration: found")
    else:
        print("PAIO configuration: not found")
        print("Run `paio setup` before launching PAIO.")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paio",
        description="Install, check, and launch PAIO-Omni.",
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "setup",
        help="Run the interactive PAIO setup process.",
    )
    subparsers.add_parser(
        "start",
        help="Launch PAIO after setup has completed.",
    )
    subparsers.add_parser(
        "check",
        help="Check Ollama, Piper, and PAIO configuration.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    command = args.command

    if command == "setup":
        return _run_setup()

    if command == "start":
        return _run_start()

    if command == "check":
        return _run_check()

    # `paio` with no command should guide a new user through setup.
    if not _configuration_exists():
        return _run_setup()

    return _run_start()


if __name__ == "__main__":
    raise SystemExit(main())