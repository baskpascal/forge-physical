from pathlib import Path

from hardware_build.artifacts import artifact_files


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
