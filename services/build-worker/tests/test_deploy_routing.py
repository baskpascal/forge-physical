from __future__ import annotations

import importlib.util
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPOSITORY_ROOT / "scripts/detect-deploy-changes.py"
SPEC = importlib.util.spec_from_file_location("deploy_changes", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_docs_only_change_does_not_deploy():
    result = MODULE.classify(["README.md", "docs/architecture.md"])
    assert result == {
        "api": False,
        "worker": False,
        "web": False,
        "toolchain": False,
        "config": False,
        "deploy": False,
    }


def test_web_only_change_routes_only_web():
    result = MODULE.classify(["apps/web/components/build-room.tsx"])
    assert result["web"] and result["deploy"]
    assert not result["api"] and not result["worker"]


def test_worker_tooling_change_routes_worker_and_toolchain():
    result = MODULE.classify(["services/build-worker/tooling/platformio-cache/platformio.ini"])
    assert result["worker"] and result["toolchain"]
    assert not result["api"] and not result["web"]
