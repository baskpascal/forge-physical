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


def test_worker_entrypoint_change_routes_only_worker():
    result = MODULE.classify(["services/build-worker/src/hardware_build/run_job.py"])
    assert result["worker"] and result["deploy"]
    assert not result["api"] and not result["web"] and not result["toolchain"]


def test_hardware_module_imported_by_api_routes_both_runtimes():
    result = MODULE.classify(["services/build-worker/src/hardware_build/firmware.py"])
    assert result["api"] and result["worker"] and result["deploy"]


def test_api_entrypoint_change_routes_only_api():
    result = MODULE.classify(["services/build-worker/src/hardware_build/api.py"])
    assert result["api"] and result["deploy"]
    assert not result["worker"] and not result["web"]


def test_shared_queue_change_routes_api_and_worker():
    result = MODULE.classify(["services/build-worker/src/hardware_build/storage.py"])
    assert result["api"] and result["worker"] and result["deploy"]
    assert not result["web"] and not result["toolchain"]


def test_api_artifact_module_change_routes_api_and_worker():
    result = MODULE.classify(["services/build-worker/src/hardware_build/artifacts.py"])
    assert result["api"] and result["worker"]


def test_backend_tests_do_not_deploy():
    result = MODULE.classify(["services/build-worker/tests/test_service.py"])
    assert not result["deploy"]


def test_cloud_build_entrypoints_route_to_their_own_runtime():
    web = MODULE.classify(["cloudbuild.web.yaml"])
    backend = MODULE.classify(["cloudbuild.image.yaml"])

    assert web["web"] and web["config"] and not web["api"] and not web["worker"]
    assert backend["api"] and backend["worker"] and backend["config"]
    assert not backend["web"]


def test_unknown_production_input_fails_safe_to_full_app_deploy():
    result = MODULE.classify(["new-runtime-manifest.toml"])
    assert result["api"] and result["worker"] and result["web"] and result["deploy"]
