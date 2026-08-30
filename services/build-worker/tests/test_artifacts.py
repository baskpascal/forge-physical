from pathlib import Path

from hardware_build.artifacts import (
    artifact_files,
    artifact_media_type,
    build_public_artifact_paths,
    public_artifact_path,
)
from hardware_build.models import Build


def test_artifact_allowlist_excludes_platformio_intermediates(tmp_path: Path):
    included = [
        "hardware/product.json",
        "hardware/firmware/src/main.cpp",
        "hardware/firmware/.pio/build/esp32-s3-devkitc-1/firmware.bin",
        "hardware/enclosure/base.stl",
    ]
    excluded = [
        "hardware/firmware/.pio/build/esp32-s3-devkitc-1/main.cpp.o",
        "hardware/firmware/.pio/libdeps/cache.dat",
    ]
    for relative in included + excluded:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test")
    assert {path.relative_to(tmp_path).as_posix() for path in artifact_files(tmp_path)} == set(included)


def test_public_artifact_path_rejects_traversal_and_internal_files():
    assert public_artifact_path("hardware/enclosure/base.stl") == "hardware/enclosure/base.stl"
    assert public_artifact_path("hardware/../data/build.json") is None
    assert public_artifact_path("../hardware/enclosure/base.stl") is None
    assert public_artifact_path(r"hardware\enclosure\base.stl") is None
    assert public_artifact_path("hardware/firmware/.pio/libdeps/cache.dat") is None
    assert public_artifact_path("data/build.json") is None


def test_artifact_media_types_are_stable_across_platforms():
    assert artifact_media_type("hardware/enclosure/base.stl") == "model/stl"
    assert artifact_media_type("hardware/product.json") == "application/json"
    assert artifact_media_type("hardware/firmware/src/main.cpp").startswith("text/plain")


def test_build_artifact_allowlist_accepts_only_recorded_public_paths():
    build = Build(
        id="build-1",
        prompt="Build a desk monitor",
        artifact_paths={
            "base": "build-1/hardware/enclosure/base.stl",
            "internal": "build-1/hardware/firmware/.pio/libdeps/cache.dat",
            "other_build": "build-2/hardware/enclosure/lid.stl",
        },
    )

    assert build_public_artifact_paths(build) == {"hardware/enclosure/base.stl"}
