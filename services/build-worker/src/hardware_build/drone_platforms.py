"""Explicit contracts for Drone Alpha platforms that are not yet supported.

This module is intentionally separate from the Alpha compiler.  It gives CLI,
API, and future MCP adapters a single truthful description of deferred
platforms without accidentally making either one a runnable target.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Final


class DeferredPlatformError(ValueError):
    """Raised when a caller asks Alpha to use a platform outside its contract."""


@dataclass(frozen=True)
class PlatformValidationProfile:
    """A product contract, not an implementation or deployment recipe."""

    identifier: str
    display_name: str
    category: str
    lifecycle: str
    verification: str
    deployment: str
    purpose: str
    alpha_boundary: str
    promotion_gates: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


GAZEBO_HARMONIC: Final = PlatformValidationProfile(
    identifier="gazebo-harmonic",
    display_name="Gazebo Harmonic",
    category="simulation",
    lifecycle="deferred",
    verification="unavailable",
    deployment="not_applicable",
    purpose="Future visual-world, camera, and sensor regression scenarios for PX4.",
    alpha_boundary="PX4 SIH remains the only Drone Alpha simulation gate.",
    promotion_gates=(
        "Pin a PX4-Gazebo compatibility matrix and container image digest.",
        "Provide a headless CI scenario with deterministic world assets.",
        "Record sensor assertions and runtime provenance in verification.json.",
        "Demonstrate that the visual scenario adds coverage beyond SIH.",
    ),
    limitations=(
        "No Gazebo runtime, world asset, camera assertion, or passed result is shipped in Alpha.",
        "Gazebo simulation would still not verify physical flight.",
    ),
)

MODALAI_VOXL: Final = PlatformValidationProfile(
    identifier="modalai-voxl",
    display_name="ModalAI VOXL",
    category="companion-compute",
    lifecycle="deferred",
    verification="unavailable",
    deployment="unavailable",
    purpose="Future companion-compute profile for perception and mission applications.",
    alpha_boundary="No VOXL image, SDK, transport, device access, or deployment command exists in Alpha.",
    promotion_gates=(
        "Select a specific supported VOXL hardware and OS/SDK release.",
        "Define a signed local-bridge and device-identity model.",
        "Run a hardware-in-the-loop acceptance suite on the selected device.",
        "Separate companion-app verification from PX4 flight-controller verification.",
    ),
    limitations=(
        "A generated MAVSDK module is not a VOXL deployment artifact.",
        "Companion-compute tests would not authorize or prove physical flight.",
    ),
)

_PROFILES: Final[dict[str, PlatformValidationProfile]] = {
    GAZEBO_HARMONIC.identifier: GAZEBO_HARMONIC,
    MODALAI_VOXL.identifier: MODALAI_VOXL,
}


def list_deferred_platforms() -> tuple[PlatformValidationProfile, ...]:
    """Return all known future profiles in a stable order for adapters."""

    return tuple(_PROFILES[key] for key in sorted(_PROFILES))


def get_deferred_platform(identifier: str) -> PlatformValidationProfile:
    """Resolve a declared future profile without implying it can run."""

    try:
        return _PROFILES[identifier]
    except KeyError as exc:
        raise DeferredPlatformError(f"Unknown Drone Alpha platform profile: {identifier}") from exc


def require_runnable_platform(identifier: str) -> PlatformValidationProfile:
    """Reject deferred profiles until their promotion gates are implemented."""

    profile = get_deferred_platform(identifier)
    raise DeferredPlatformError(
        f"{profile.display_name} is {profile.lifecycle} in COUP Drone Alpha; "
        f"verification is {profile.verification} and deployment is {profile.deployment}. "
        "Use the PX4 SIH COUP Quad Alpha profile for the supported simulation path."
    )
