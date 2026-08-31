from __future__ import annotations

import hashlib
import json
import re

from .models import HardwareIR

FINGERPRINT_VERSION = "coup-build-v1"


def _hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _firmware_controls(prompt: str) -> list[str]:
    normalized = " ".join(prompt.lower().split())
    controls = re.findall(
        r"(?:above|below|over|under|threshold|at)\s*(?:of\s*)?(-?\d+(?:\.\d+)?)\s*°?c?",
        normalized,
    )
    behavior = [
        word
        for word in ("alarm", "warning", "temperature", "motion", "orientation")
        if word in normalized
    ]
    return sorted([*controls, *behavior])


def build_fingerprints(hardware: HardwareIR, prompt: str) -> dict[str, str]:
    hardware_payload = hardware.model_dump(mode="json", by_alias=True)
    hardware_hash = _hash([FINGERPRINT_VERSION, "hardware", hardware_payload])
    firmware_hash = _hash(
        [FINGERPRINT_VERSION, "firmware", hardware_hash, _firmware_controls(prompt)]
    )
    return {
        "hardware_hash": hardware_hash,
        "firmware_hash": firmware_hash,
        "simulation_hash": _hash(
            [FINGERPRINT_VERSION, "simulation", hardware_hash, firmware_hash]
        ),
        "enclosure_hash": _hash([FINGERPRINT_VERSION, "enclosure", hardware_hash]),
    }


def reusable_phases(current: dict[str, str], parent: dict[str, str]) -> set[str]:
    mapping = {
        "hardware_hash": "hardware",
        "firmware_hash": "firmware",
        "simulation_hash": "simulation",
        "enclosure_hash": "enclosure",
    }
    return {phase for key, phase in mapping.items() if current.get(key) == parent.get(key)}
