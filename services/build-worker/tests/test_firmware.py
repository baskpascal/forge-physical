from pathlib import Path

from hardware_build.firmware import deterministic_repair, generate_firmware
from hardware_build.planning import deterministic_hardware_ir, deterministic_product_spec


def test_firmware_generation_and_known_repair(tmp_path: Path):
    hardware = deterministic_hardware_ir(deterministic_product_spec("Build an OLED desk temperature monitor with a knob"))
    files = generate_firmware(hardware, tmp_path)
    assert "CHECK:BOOT:PASS" in files["source"].read_text(encoding="utf-8")
    source = files["source"].read_text(encoding="utf-8").replace("display.begin", "display.begin_broken", 1)
    files["source"].write_text(source, encoding="utf-8")
    assert deterministic_repair(files["source"], "no member named begin_broken")
    assert "begin_broken" not in files["source"].read_text(encoding="utf-8")
