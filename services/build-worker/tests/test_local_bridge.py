import json
from pathlib import Path

import pytest

from hardware_build.drone import build_version, create_version, init_project
from hardware_build.drone import test_version as run_test_version
from hardware_build.local_bridge import (
    BridgeSafetyError,
    DeviceIdentity,
    admit_build,
    write_parameter_backup,
)


def _artifact(tmp_path: Path) -> tuple[Path, str]:
    init_project(tmp_path)
    record = create_version(tmp_path, "make a stable inspection drone for my farm")
    build_version(tmp_path, record["id"])
    run_test_version(tmp_path, record["id"])
    return Path(record["root"]), record["id"]


def test_bridge_rejects_unverified_simulation_but_keeps_provenance(tmp_path: Path) -> None:
    root, build_id = _artifact(tmp_path)

    decision = admit_build(root, build_id)

    assert decision.status == "rejected"
    assert decision.physical_deployment == "unavailable"
    assert "Simulation verification did not pass" in " ".join(decision.reasons)
    assert decision.artifact_hashes["parameter_overlay"] != "missing"


def test_bridge_rejects_tampered_generated_overlay(tmp_path: Path) -> None:
    root, build_id = _artifact(tmp_path)
    overlay = root / "autopilot/overlay/coup_quad_alpha.params"
    overlay.write_text("MPC_ACC_HOR\t99\n", encoding="utf-8")

    decision = admit_build(root, build_id)

    assert decision.status == "rejected"
    assert "Artifact provenance mismatch" in " ".join(decision.reasons)


def test_parameter_backup_is_device_bound_and_refuses_empty_exports(tmp_path: Path) -> None:
    device = DeviceIdentity(
        board_id="PX4_FMU_V6X",
        serial_number="PX4-TEST-001",
        hardware_uid="0011223344556677",
        transport="usb",
    )
    target = write_parameter_backup(
        tmp_path / "backups", device, "MPC_ACC_HOR\t2.0\n", "px4-param-show"
    )

    backup = json.loads(target.read_text(encoding="utf-8"))
    assert backup["device_fingerprint"] == device.fingerprint
    assert backup["physical_deployment"] == "unavailable"
    with pytest.raises(BridgeSafetyError, match="empty"):
        write_parameter_backup(tmp_path / "backups", device, " ", "px4-param-show")


def test_device_identity_does_not_accept_network_only_or_non_px4_targets() -> None:
    with pytest.raises(BridgeSafetyError, match="transport"):
        DeviceIdentity("PX4_FMU_V6X", "PX4-TEST-001", "udp").validate()
    with pytest.raises(BridgeSafetyError, match="PX4"):
        DeviceIdentity("APM", "APM-TEST-001", "usb", autopilot="ArduPilot").validate()
