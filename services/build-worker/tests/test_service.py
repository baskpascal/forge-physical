from pathlib import Path

from hardware_build.models import ToolResult
from hardware_build.orchestrator import BuildOrchestrator
from hardware_build.service import create_build, dispatch_build, update_build
from hardware_build.settings import Settings
from hardware_build.storage import LocalJsonBuildStore


def test_build_state_machine_completes_with_real_tool_contracts(tmp_path: Path, monkeypatch):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = Settings(build_data_dir=tmp_path / "data", build_artifact_dir=tmp_path / "artifacts")
    response = create_build("Build a desk monitor with OLED, rotary knob, temperature sensor and USB power", dispatch=False, store=store, settings=settings)

    def compiled(_settings, firmware_dir):
        binary = firmware_dir / ".pio" / "build" / "esp32-s3-devkitc-1" / "firmware.bin"
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_bytes(b"real-test-binary")
        return ToolResult(status="passed", summary="compiled", evidence={"exit_code": 0, "firmware_bin": str(binary)})

    monkeypatch.setattr("hardware_build.orchestrator.compile_firmware", compiled)
    BuildOrchestrator(store, settings).run(response.build_id)
    build = store.get(response.build_id)
    event_types = [event.type for event in store.events(response.build_id)]
    assert build.status == "completed"
    assert build.verification.firmware_compilation == "passed"
    assert "motion read" not in build.verification.scenario_checks
    assert event_types[0] == "build.created"
    assert "electronics.verified" in event_types and "build.completed" in event_types


def test_start_returns_before_worker_when_dispatch_disabled(tmp_path: Path):
    store = LocalJsonBuildStore(tmp_path)
    settings = Settings(build_data_dir=tmp_path, build_artifact_dir=tmp_path / "artifacts")
    response = create_build("Build a supported low voltage desk monitor", dispatch=False, store=store, settings=settings)
    assert response.status == "queued"
    assert store.get(response.build_id).progress == 0


def test_update_creates_immutable_child_version(tmp_path: Path):
    store = LocalJsonBuildStore(tmp_path)
    settings = Settings(build_data_dir=tmp_path, build_artifact_dir=tmp_path / "artifacts")
    original = create_build(
        "Build a supported low voltage desk monitor",
        dispatch=False,
        store=store,
        settings=settings,
    )
    parent_before = store.get(original.build_id).model_dump(mode="json")

    updated = update_build(
        original.build_id,
        "Add motion sensing",
        dispatch=False,
        store=store,
        settings=settings,
    )

    child = store.get(updated.build_id)
    assert updated.build_id != original.build_id
    assert child.version == 2
    assert child.parent_build_id == original.build_id
    assert child.prompt.endswith("Requested update: Add motion sensing")
    assert store.get(original.build_id).model_dump(mode="json") == parent_before


def test_update_rejects_unsupported_change_without_mutating_parent(tmp_path: Path):
    store = LocalJsonBuildStore(tmp_path)
    settings = Settings(build_data_dir=tmp_path, build_artifact_dir=tmp_path / "artifacts")
    original = create_build(
        "Build a supported low voltage desk monitor",
        dispatch=False,
        store=store,
        settings=settings,
    )
    parent_before = store.get(original.build_id).model_dump(mode="json")

    try:
        update_build(
            original.build_id,
            "Add a GPS receiver",
            dispatch=False,
            store=store,
            settings=settings,
        )
    except ValueError as exc:
        assert "Unsupported prototype update" in str(exc)
    else:
        raise AssertionError("Unsupported updates must fail explicitly")

    assert store.get(original.build_id).model_dump(mode="json") == parent_before


def test_motion_build_verification_records_additional_scenario_checks(
    tmp_path: Path, monkeypatch
):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = Settings(
        build_data_dir=tmp_path / "data",
        build_artifact_dir=tmp_path / "artifacts",
    )
    response = create_build(
        "Build a desk monitor and add motion sensing",
        dispatch=False,
        store=store,
        settings=settings,
    )

    def compiled(_settings, firmware_dir):
        binary = firmware_dir / ".pio" / "build" / "esp32-s3-devkitc-1" / "firmware.bin"
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_bytes(b"motion-firmware")
        return ToolResult(
            status="passed",
            summary="compiled",
            evidence={"exit_code": 0, "firmware_bin": str(binary)},
        )

    monkeypatch.setattr("hardware_build.orchestrator.compile_firmware", compiled)
    BuildOrchestrator(store, settings).run(response.build_id)

    build = store.get(response.build_id)
    assert build.verification is not None
    assert build.verification.scenario_checks[-2:] == [
        "motion sensor initialization",
        "motion read",
    ]
    verification_path = (
        settings.build_artifact_dir / response.build_id / "hardware" / "verification.json"
    )
    assert "motion read" in verification_path.read_text(encoding="utf-8")


def test_failed_simulation_never_marks_build_completed(tmp_path: Path, monkeypatch):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = Settings(build_data_dir=tmp_path / "data", build_artifact_dir=tmp_path / "artifacts")
    response = create_build(
        "Build a desk monitor with OLED, rotary knob, temperature sensor and USB power",
        dispatch=False,
        store=store,
        settings=settings,
    )

    def compiled(_settings, firmware_dir):
        binary = firmware_dir / ".pio" / "build" / "esp32-s3-devkitc-1" / "firmware.bin"
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_bytes(b"real-test-binary")
        return ToolResult(
            status="passed",
            summary="compiled",
            evidence={"exit_code": 0, "firmware_bin": str(binary)},
        )

    monkeypatch.setattr("hardware_build.orchestrator.compile_firmware", compiled)
    monkeypatch.setattr(
        "hardware_build.orchestrator.run_wokwi",
        lambda *_args, **_kwargs: ToolResult(
            status="failed",
            summary="Wokwi scenario failed",
            evidence={"exit_code": 1},
        ),
    )
    BuildOrchestrator(store, settings).run(response.build_id)

    build = store.get(response.build_id)
    event_types = [event.type for event in store.events(response.build_id)]
    assert build.status == "needs_review"
    assert build.verification.simulation == "failed"
    assert "build.needs_review" in event_types
    assert "build.completed" not in event_types


def test_http_dispatch_requires_a_secret(tmp_path: Path):
    store = LocalJsonBuildStore(tmp_path)
    settings = Settings(worker_dispatch_url="https://worker.invalid")
    try:
        dispatch_build("build-id", settings, store)
    except RuntimeError as exc:
        assert "INTERNAL_WORKER_TOKEN" in str(exc)
    else:
        raise AssertionError("HTTP dispatch must be disabled without authentication")
