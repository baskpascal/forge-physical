from __future__ import annotations

import json

from .orchestrator import BuildOrchestrator
from .service import create_build, status_payload
from .settings import get_settings
from .storage import get_store

DEMO_PROMPT = "Build a small desk environmental monitor with a screen, rotary knob and temperature sensor. Use an ESP32 and USB power."


def main() -> None:
    settings, store = get_settings(), get_store()
    response = create_build(DEMO_PROMPT, dispatch=False, store=store, settings=settings)
    BuildOrchestrator(store, settings).run(response.build_id)
    result = status_payload(response.build_id, store)
    print(json.dumps({"build_id": response.build_id, "status": result["status"], "stage": result["stage"], "verification": result["verification"], "build_url": response.build_url}, indent=2))
    if result["status"] not in {"completed", "needs_review"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
