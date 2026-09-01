"""Run backend commands with repository-managed Python tooling when present."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHONS = (
    ROOT / ".venv" / "Scripts" / "python.exe",
    ROOT / ".venv" / "bin" / "python",
)
PLATFORMIO_COMMANDS = (
    ROOT / ".platformio-venv" / "Scripts" / "platformio.exe",
    ROOT / ".platformio-venv" / "bin" / "platformio",
)


def main() -> int:
    if len(sys.argv) == 1:
        print("Usage: python scripts/run-backend.py <python arguments>", file=sys.stderr)
        return 2
    python = next((candidate for candidate in VENV_PYTHONS if candidate.exists()), Path(sys.executable))
    environment = os.environ.copy()
    if "PLATFORMIO_CMD" not in environment:
        platformio = next((candidate for candidate in PLATFORMIO_COMMANDS if candidate.exists()), None)
        if platformio:
            environment["PLATFORMIO_CMD"] = str(platformio)
    return subprocess.call([str(python), *sys.argv[1:]], cwd=ROOT, env=environment)


if __name__ == "__main__":
    raise SystemExit(main())
