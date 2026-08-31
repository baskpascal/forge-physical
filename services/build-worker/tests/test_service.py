from pathlib import Path

from hardware_build.models import ComponentInstance, HardwareIR, ProductSpec, ToolResult
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
    monkeypatch.setattr(
        "hardware_build.orchestrator.run_wokwi",
        lambda *_args, **_kwargs: ToolResult(
            status="passed",
            summary="validated",
            evidence={"checks": ["scenario validated"]},
        ),
    )
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


def test_update_rejects_composed_motion_and_gps_without_creating_child(tmp_path: Path):
    store = LocalJsonBuildStore(tmp_path)
    settings = Settings(build_data_dir=tmp_path, build_artifact_dir=tmp_path / "artifacts")
    original = create_build(
        "Build a supported low voltage desk monitor",
        dispatch=False,
        store=store,
        settings=settings,
    )
    build_files_before = set(store.root.glob("*.json"))

    try:
        update_build(
            original.build_id,
            "Remove motion sensing and add GPS",
            dispatch=False,
            store=store,
            settings=settings,
        )
    except ValueError as exc:
        assert "Unsupported prototype update" in str(exc)
    else:
        raise AssertionError("Composed updates must fail before creating a child")

    assert set(store.root.glob("*.json")) == build_files_before


def test_update_rejects_duplicate_motion_from_parent_prompt_without_creating_child(tmp_path: Path):
    store = LocalJsonBuildStore(tmp_path)
    settings = Settings(build_data_dir=tmp_path, build_artifact_dir=tmp_path / "artifacts")
    original = create_build(
        "Build a desk monitor with an MPU6050 motion sensor",
        dispatch=False,
        store=store,
        settings=settings,
    )
    build_files_before = set(store.root.glob("*.json"))

    try:
        update_build(
            original.build_id,
            "Add motion sensing",
            dispatch=False,
            store=store,
            settings=settings,
        )
    except ValueError as exc:
        assert "already present" in str(exc)
    else:
        raise AssertionError("Duplicate motion updates must fail before creating a child")

    assert set(store.root.glob("*.json")) == build_files_before


def test_update_rejects_duplicate_motion_from_persisted_parent_state(tmp_path: Path):
    store = LocalJsonBuildStore(tmp_path)
    settings = Settings(build_data_dir=tmp_path, build_artifact_dir=tmp_path / "artifacts")
    original = create_build(
        "Build a supported low voltage desk monitor",
        dispatch=False,
        store=store,
        settings=settings,
    )
    parent = store.get(original.build_id)
    parent.product_spec = ProductSpec(
        intent=parent.prompt,
        description="Monitor with inertial sensing",
        features=["motion sensing"],
    )
    parent.hardware = HardwareIR(
        board=ComponentInstance(ref="board", component_id="esp32-s3-devkit", label="Board"),
        components=[ComponentInstance(ref="motion", component_id="mpu6050", label="IMU")],
        connections=[],
        power=[],
    )
    store.save(parent)
    build_files_before = set(store.root.glob("*.json"))

    try:
        update_build(
            original.build_id,
            "Integrate an IMU sensor",
            dispatch=False,
            store=store,
            settings=settings,
        )
    except ValueError as exc:
        assert "already present" in str(exc)
    else:
        raise AssertionError("Persisted parent state must prevent a duplicate child")

    assert set(store.root.glob("*.json")) == build_files_before


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


def test_engineering_agent_receives_real_compiler_evidence(tmp_path: Path, monkeypatch):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = Settings(
        build_data_dir=tmp_path / "data",
        build_artifact_dir=tmp_path / "artifacts",
        max_repair_attempts=1,
    )
    response = create_build(
        "Build a desk monitor with a screen and temperature sensor",
        dispatch=False,
        store=store,
        settings=settings,
    )
    compile_calls = 0
    received: dict[str, str] = {}

    def compile_with_one_failure(_settings, firmware_dir):
        nonlocal compile_calls
        compile_calls += 1
        if compile_calls == 1:
            return ToolResult(
                status="failed",
                summary="compiler rejected generated firmware",
                evidence={"exit_code": 1, "output": "main.cpp: no member named begin_broken"},
            )
        binary = firmware_dir / ".pio" / "build" / "esp32-s3-devkitc-1" / "firmware.bin"
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_bytes(b"repaired-firmware")
        return ToolResult(
            status="passed",
            summary="compiled after repair",
            evidence={"exit_code": 0, "firmware_bin": str(binary)},
        )

    async def repair_from_evidence(source: str, compiler_output: str, _settings):
        received.update(source=source, compiler_output=compiler_output)
        return {
            "find": "void setup()",
            "replace": "void setup()",
            "explanation": "Repair grounded in the compiler diagnostic.",
        }

    monkeypatch.setattr("hardware_build.orchestrator.compile_firmware", compile_with_one_failure)
    monkeypatch.setattr("hardware_build.orchestrator.propose_repair", repair_from_evidence)

    BuildOrchestrator(store, settings).run(response.build_id)

    assert "void setup()" in received["source"]
    assert "begin_broken" in received["compiler_output"]
    repair_events = [
        event for event in store.events(response.build_id) if event.type == "agent.repair.started"
    ]
    assert repair_events[0].metadata == {"agent": "EngineeringAgent", "attempt": 1}
    assert store.get(response.build_id).firmware.status == "passed"


def test_http_dispatch_requires_a_secret(tmp_path: Path):
    store = LocalJsonBuildStore(tmp_path)
    settings = Settings(worker_dispatch_url="https://worker.invalid")
    try:
        dispatch_build("build-id", settings, store)
    except RuntimeError as exc:
        assert "INTERNAL_WORKER_TOKEN" in str(exc)
    else:
        raise AssertionError("HTTP dispatch must be disabled without authentication")
