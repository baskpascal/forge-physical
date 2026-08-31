from __future__ import annotations

import hashlib
import json
import re

from .models import HardwareIR

FINGERPRINT_VERSION = "coup-build-v2"
VALIDATOR_VERSION = "electrical-v1"
FIRMWARE_GENERATOR_VERSION = "firmware-v2-threshold"
SIMULATION_GENERATOR_VERSION = "wokwi-v2-threshold"
ENCLOSURE_GENERATOR_VERSION = "enclosure-v2-dimensions"


def _hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def temperature_threshold_c(prompt: str) -> float:
    """Return the last requested temperature threshold, or the safe golden default."""
    normalized = " ".join(prompt.lower().split())
    controls = re.findall(
        r"(?:above|below|over|under|threshold|at)\s*(?:of\s*)?(-?\d+(?:\.\d+)?)\s*°?c?",
        normalized,
    )
    return float(controls[-1]) if controls else 30.0


def _firmware_controls(prompt: str) -> list[object]:
    normalized = " ".join(prompt.lower().split())
    behavior = [
        word
        for word in ("alarm", "warning", "temperature", "motion", "orientation")
        if word in normalized
    ]
    return [temperature_threshold_c(prompt), *sorted(behavior)]


def enclosure_dimensions_mm(prompt: str) -> tuple[float, float, float]:
    """Derive bounded deterministic enclosure dimensions from the latest update."""
    normalized = " ".join(prompt.lower().split())
    latest = normalized.rsplit("requested update:", 1)[-1]
    dimensions = re.findall(
        r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*mm",
        latest,
    )
    if dimensions:
        width, depth, height = (float(value) for value in dimensions[-1])
        # Preserve room for the supported board and fixed USB/display clearances.
        return max(70.0, width), max(50.0, depth), max(24.0, height)
    scale = 1.1 if re.search(r"\b(?:larger|bigger|increase|expand)\b", latest) else 1.0
    if re.search(r"\b(?:smaller|compact|decrease|shrink)\b", latest):
        scale = 0.9
    return tuple(round(value * scale, 1) for value in (84.0, 64.0, 30.0))


def build_fingerprints(hardware: HardwareIR, prompt: str) -> dict[str, str]:
    hardware_payload = hardware.model_dump(mode="json", by_alias=True)
    hardware_hash = _hash([FINGERPRINT_VERSION, VALIDATOR_VERSION, "hardware", hardware_payload])
    firmware_hash = _hash(
        [
            FINGERPRINT_VERSION,
            FIRMWARE_GENERATOR_VERSION,
            "firmware",
            hardware_hash,
            _firmware_controls(prompt),
        ]
    )
    return {
        "hardware_hash": hardware_hash,
        "firmware_hash": firmware_hash,
        "simulation_hash": _hash(
            [
                FINGERPRINT_VERSION,
                SIMULATION_GENERATOR_VERSION,
                "simulation",
                hardware_hash,
                firmware_hash,
            ]
        ),
        "enclosure_hash": _hash(
            [
                FINGERPRINT_VERSION,
                ENCLOSURE_GENERATOR_VERSION,
                "enclosure",
                hardware_hash,
                enclosure_dimensions_mm(prompt),
            ]
        ),
    }


def reusable_phases(current: dict[str, str], parent: dict[str, str]) -> set[str]:
    mapping = {
        "hardware_hash": "hardware",
        "firmware_hash": "firmware",
        "simulation_hash": "simulation",
        "enclosure_hash": "enclosure",
    }
    return {phase for key, phase in mapping.items() if current.get(key) == parent.get(key)}
