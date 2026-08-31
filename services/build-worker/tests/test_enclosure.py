from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from hardware_build.enclosure import generate_enclosure
from hardware_build.planning import deterministic_hardware_ir, deterministic_product_spec


def test_enclosure_exports_nonempty_stl_files(tmp_path: Path):
    hardware = deterministic_hardware_ir(
        deterministic_product_spec("desk monitor with display, knob and sensor")
    )
    result = generate_enclosure(hardware, tmp_path)
    assert result.status == "passed"
    for filename in ("base.stl", "lid.stl"):
        text = (tmp_path / filename).read_text(encoding="ascii")
        assert text.startswith("solid") and "facet normal" in text


def test_parallel_enclosure_generation_is_deterministic(tmp_path: Path):
    hardware = deterministic_hardware_ir(deterministic_product_spec("desk monitor with display"))
    directories = [tmp_path / "serial", tmp_path / "parallel"]
    generate_enclosure(hardware, directories[0])
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(generate_enclosure, hardware, directories[1]).result()
    for filename in ("base.stl", "lid.stl"):
        assert (directories[0] / filename).read_bytes() == (directories[1] / filename).read_bytes()


def test_enclosure_dimensions_change_the_stl_and_evidence(tmp_path: Path):
    hardware = deterministic_hardware_ir(deterministic_product_spec("desk monitor"))
    default = generate_enclosure(hardware, tmp_path / "default")
    larger = generate_enclosure(hardware, tmp_path / "larger", (100.0, 80.0, 35.0))

    assert larger.evidence["dimensions_mm"] == [100.0, 80.0, 35.0]
    assert default.evidence["dimensions_mm"] != larger.evidence["dimensions_mm"]
    assert (tmp_path / "default/base.stl").read_bytes() != (
        tmp_path / "larger/base.stl"
    ).read_bytes()
