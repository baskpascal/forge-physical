from pathlib import Path

from hardware_build.enclosure import generate_enclosure
from hardware_build.planning import deterministic_hardware_ir, deterministic_product_spec


def test_enclosure_exports_nonempty_stl_files(tmp_path: Path):
    hardware = deterministic_hardware_ir(deterministic_product_spec("desk monitor with display, knob and sensor"))
    result = generate_enclosure(hardware, tmp_path)
    assert result.status == "passed"
    for filename in ("base.stl", "lid.stl"):
        text = (tmp_path / filename).read_text(encoding="ascii")
        assert text.startswith("solid") and "facet normal" in text
