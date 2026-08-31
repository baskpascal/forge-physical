from pathlib import Path

from hardware_build.artifacts import ArtifactWorkspace
from hardware_build.incremental import (
    build_fingerprints,
    enclosure_dimensions_mm,
    reusable_phases,
    temperature_threshold_c,
)
from hardware_build.models import Build
from hardware_build.planning import deterministic_hardware_ir, deterministic_product_spec
from hardware_build.settings import Settings


def _hardware(prompt: str):
    return deterministic_hardware_ir(deterministic_product_spec(prompt), prompt)


def test_threshold_change_invalidates_firmware_but_not_hardware_or_enclosure():
    before = build_fingerprints(
        _hardware("temperature alarm above 30C"), "temperature alarm above 30C"
    )
    after = build_fingerprints(
        _hardware("temperature alarm above 35C"), "temperature alarm above 35C"
    )

    phases = reusable_phases(after, before)
    assert {"hardware", "enclosure"} <= phases
    assert "firmware" not in phases and "simulation" not in phases


def test_name_only_change_is_a_full_safe_cache_hit():
    hardware = _hardware("temperature alarm above 30C")
    before = build_fingerprints(hardware, "temperature alarm above 30C named Alpha")
    after = build_fingerprints(hardware, "temperature alarm above 30C named Beta")
    assert reusable_phases(after, before) == {"hardware", "firmware", "simulation", "enclosure"}


def test_enclosure_change_invalidates_only_the_enclosure():
    hardware = _hardware("temperature alarm above 30C")
    before = build_fingerprints(hardware, "temperature alarm above 30C")
    after = build_fingerprints(
        hardware,
        "temperature alarm above 30C\n\nRequested update: enclosure 100x80x35 mm",
    )

    phases = reusable_phases(after, before)
    assert {"hardware", "firmware", "simulation"} <= phases
    assert "enclosure" not in phases
    assert enclosure_dimensions_mm("Requested update: enclosure 100x80x35 mm") == (
        100.0,
        80.0,
        35.0,
    )


def test_latest_threshold_controls_the_fingerprint_and_generated_behavior():
    prompt = "temperature alarm above 30C\n\nRequested update: threshold 35C"
    assert temperature_threshold_c(prompt) == 35.0


def test_artifact_cache_hit_copies_content_and_records_hash(tmp_path: Path):
    settings = Settings(build_artifact_dir=tmp_path)
    parent = Build(id="parent", prompt="prototype")
    source = tmp_path / parent.id / "hardware/enclosure/base.stl"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"solid deterministic")
    parent.artifact_paths["enclosure_base"] = "parent/hardware/enclosure/base.stl"

    paths, hashes = ArtifactWorkspace(settings, "child").reuse_from(parent, ("enclosure_base",))

    assert paths["enclosure_base"] == "child/hardware/enclosure/base.stl"
    assert len(hashes["enclosure_base"]) == 64
    assert (tmp_path / paths["enclosure_base"]).read_bytes() == b"solid deterministic"


def test_artifact_cache_miss_is_explicit(tmp_path: Path):
    paths, hashes = ArtifactWorkspace(Settings(build_artifact_dir=tmp_path), "child").reuse_from(
        Build(id="parent", prompt="prototype"), ("enclosure_base",)
    )
    assert paths == {} and hashes == {}
