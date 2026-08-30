from __future__ import annotations

import os

from .orchestrator import run_build


def main() -> None:
    build_id = os.environ.get("BUILD_ID")
    if not build_id:
        raise SystemExit("BUILD_ID is required for the Cloud Run Job")
    run_build(build_id)


if __name__ == "__main__":
    main()
