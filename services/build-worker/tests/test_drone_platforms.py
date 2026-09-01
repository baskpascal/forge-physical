import pytest

from hardware_build.drone_platforms import (
    DeferredPlatformError,
    get_deferred_platform,
    list_deferred_platforms,
    require_runnable_platform,
)


def test_deferred_profiles_are_explicitly_non_runnable_and_non_verified() -> None:
    profiles = {profile.identifier: profile for profile in list_deferred_platforms()}

    assert set(profiles) == {"gazebo-harmonic", "modalai-voxl"}
    for profile in profiles.values():
        assert profile.lifecycle == "deferred"
        assert profile.verification == "unavailable"
        assert "not_verified" not in profile.purpose
        assert profile.promotion_gates
        assert profile.limitations

    assert profiles["gazebo-harmonic"].deployment == "not_applicable"
    assert profiles["modalai-voxl"].deployment == "unavailable"


def test_deferred_platforms_cannot_be_requested_as_runnable_targets() -> None:
    with pytest.raises(DeferredPlatformError, match="Gazebo Harmonic is deferred"):
        require_runnable_platform("gazebo-harmonic")
    with pytest.raises(DeferredPlatformError, match="ModalAI VOXL is deferred"):
        require_runnable_platform("modalai-voxl")


def test_unknown_deferred_platform_is_rejected() -> None:
    with pytest.raises(DeferredPlatformError, match="Unknown Drone Alpha platform profile"):
        get_deferred_platform("arbitrary-drone")
