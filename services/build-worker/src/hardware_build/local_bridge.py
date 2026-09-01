"""Safety boundary for the future local COUP-to-flight-controller bridge.

This module deliberately does *not* open a serial port, flash firmware, or set PX4
parameters.  It is the admission and provenance contract that a later ``coupd``
daemon must satisfy before those capabilities can be enabled.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class BridgeSafetyError(ValueError):
    """Raised when a local bridge request is not safe to admit."""


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class DeviceIdentity:
    """Identity obtained locally from a controller; never inferred from a prompt."""

    board_id: str
    serial_number: str
    transport: str
    autopilot: str = "PX4"
    hardware_uid: str | None = None

    def validate(self) -> None:
        if self.autopilot != "PX4":
            raise BridgeSafetyError("COUP Drone Alpha only admits a PX4 controller.")
        if self.transport not in {"usb", "serial"}:
            raise BridgeSafetyError("Local bridge transport must be usb or serial.")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,80}", self.board_id):
            raise BridgeSafetyError("Device board_id is invalid.")
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{3,160}", self.serial_number):
            raise BridgeSafetyError("Device serial_number is invalid.")
        if self.hardware_uid and not re.fullmatch(r"[A-Za-z0-9_.:-]{8,200}", self.hardware_uid):
            raise BridgeSafetyError("Device hardware_uid is invalid.")

    @property
    def fingerprint(self) -> str:
        self.validate()
        return _digest(asdict(self))


@dataclass(frozen=True)
class BridgeAdmission:
    """A read-only admission decision for a future physical deployment."""

    status: str
    build_id: str
    artifact_root: str
    artifact_hashes: dict[str, str]
    reasons: tuple[str, ...]
    physical_deployment: str = "unavailable"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BridgeSafetyError(f"Missing {label}: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise BridgeSafetyError(f"Invalid {label}: {path.name}") from exc


def admit_build(artifact_root: Path, build_id: str) -> BridgeAdmission:
    """Verify immutable Alpha artifacts before a local bridge may even inspect them.

    Admission proves only simulation/build provenance.  It explicitly does not
    authorize flashing, parameter application, arming, or physical flight.
    """

    root = artifact_root.resolve()
    lock = _read_json(root / "coup.lock", "lock file")
    manifest = _read_json(root / "drone" / "manifest.json", "manifest")
    build = _read_json(root / "build" / "result.json", "build result")
    verification = _read_json(root / "verification" / "report.json", "verification report")
    overlay = root / "autopilot" / "overlay" / "coup_quad_alpha.params"
    scenario = root / "tests" / "scenarios" / "conservative_inspection.yaml"
    spec = root / "drone" / "spec.yaml"

    reasons: list[str] = []
    px4 = lock.get("px4")
    if (
        not isinstance(px4, dict)
        or px4.get("version") != "v1.17.0"
        or px4.get("commit") != "d6f12ad1c4f70ad3230afd7d86e971421e02fef4"
        or lock.get("vehicle") != "sihsim_quadx"
    ):
        reasons.append("Artifact is not locked to the supported COUP Quad Alpha PX4 profile.")
    if build.get("status") != "passed":
        reasons.append("Generated companion application build did not pass.")
    if verification.get("status") != "passed":
        reasons.append("Simulation verification did not pass; physical deployment remains unavailable.")
    for path, manifest_key in ((overlay, "overlay_hash"), (scenario, "scenario_hash")):
        if not path.exists():
            reasons.append(f"Required artifact is missing: {path.relative_to(root)}")
        elif manifest.get(manifest_key) != _digest(path.read_text(encoding="utf-8")):
            reasons.append(f"Artifact provenance mismatch: {path.relative_to(root)}")

    hashes = {
        "lock": _digest(lock),
        "manifest": _digest(manifest),
        "drone_spec": hashlib.sha256(spec.read_bytes()).hexdigest() if spec.exists() else "missing",
        "parameter_overlay": hashlib.sha256(overlay.read_bytes()).hexdigest() if overlay.exists() else "missing",
    }
    return BridgeAdmission(
        status="ready_for_local_review" if not reasons else "rejected",
        build_id=build_id,
        artifact_root=str(root),
        artifact_hashes=hashes,
        reasons=tuple(reasons),
    )


def write_parameter_backup(
    destination: Path,
    identity: DeviceIdentity,
    parameter_export: str,
    source: str,
) -> Path:
    """Persist a device-bound parameter export before a future change operation.

    ``coupd`` must obtain ``parameter_export`` from the connected device.  This
    function never talks to hardware and refuses an empty or ambiguous backup.
    """

    identity.validate()
    if source not in {"px4-param-show", "mavlink-parameter-export"}:
        raise BridgeSafetyError("Backup source is not a recognized PX4 parameter export.")
    if not parameter_export.strip():
        raise BridgeSafetyError("Refusing to record an empty parameter backup.")
    if len(parameter_export.encode("utf-8")) > 5_000_000:
        raise BridgeSafetyError("Parameter backup is unexpectedly large.")

    destination.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "coup.dev/local-bridge-backup/v1alpha1",
        "created_at": datetime.now(UTC).isoformat(),
        "device": asdict(identity),
        "device_fingerprint": identity.fingerprint,
        "source": source,
        "parameter_export": parameter_export,
        "parameter_export_sha256": hashlib.sha256(parameter_export.encode("utf-8")).hexdigest(),
        "physical_deployment": "unavailable",
    }
    target = destination / f"px4-parameters-{identity.fingerprint[:16]}.json"
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target
