import json
from pathlib import Path
from types import SimpleNamespace

from hardware_build.planning import deterministic_hardware_ir, deterministic_product_spec
from hardware_build.settings import Settings
from hardware_build.simulation import generate_wokwi, run_wokwi


def test_motion_build_generates_mpu6050_wokwi_circuit_and_scenario(tmp_path: Path):
    hardware = deterministic_hardware_ir(
        deterministic_product_spec("Build a desk monitor and add motion sensing")
    )

    files = generate_wokwi(hardware, tmp_path / "firmware", tmp_path / "simulation")

    diagram = json.loads(files["diagram"].read_text(encoding="utf-8"))
    assert any(part["type"] == "wokwi-mpu6050" for part in diagram["parts"])
    assert ["esp:8", "motion:SDA", "green", ["h140"]] in diagram["connections"]
    assert ["esp:9", "motion:SCL", "blue", ["h150"]] in diagram["connections"]
    scenario = files["scenario"].read_text(encoding="utf-8")
    assert "CHECK:MOTION_INIT:PASS" in scenario
    assert "CHECK:MOTION_READ:PASS" in scenario


def test_base_build_does_not_claim_motion_checks(tmp_path: Path):
    hardware = deterministic_hardware_ir(deterministic_product_spec("Build a desk monitor"))

    files = generate_wokwi(hardware, tmp_path / "firmware", tmp_path / "simulation")

    diagram = json.loads(files["diagram"].read_text(encoding="utf-8"))
    assert all(part["type"] != "wokwi-mpu6050" for part in diagram["parts"])
    assert "CHECK:MOTION" not in files["scenario"].read_text(encoding="utf-8")


def test_wokwi_result_reports_motion_checks(tmp_path: Path, monkeypatch):
    hardware = deterministic_hardware_ir(
        deterministic_product_spec("Build a desk monitor and add motion sensing")
    )
    simulation_dir = tmp_path / "simulation"
    generate_wokwi(hardware, tmp_path / "firmware", simulation_dir)
    monkeypatch.setattr("hardware_build.simulation.shutil.which", lambda _command: "wokwi-cli")
    monkeypatch.setattr(
        "hardware_build.simulation.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="CHECK:BOOT:PASS\nCHECK:OLED_INIT:PASS\nCHECK:SENSOR_INIT:PASS\nCHECK:TEMPERATURE_READ:PASS\nCHECK:MOTION_INIT:PASS\nCHECK:MOTION_READ:PASS",
            stderr="",
        ),
    )

    result = run_wokwi(Settings(wokwi_cli_token="test-token"), simulation_dir, True)

    assert result.status == "passed"
    assert "motion sensor initialization" in result.evidence["checks"]
    assert "motion read" in result.evidence["checks"]


def test_temperature_alarm_wokwi_project_has_real_sensor_and_led_assertions(tmp_path: Path):
    hardware = deterministic_hardware_ir(
        deterministic_product_spec("Create an ESP32 temperature alarm with an LED above 30C")
    )
    files = generate_wokwi(hardware, tmp_path / "firmware", tmp_path / "simulation")

    diagram = json.loads(files["diagram"].read_text(encoding="utf-8"))
    assert {part["type"] for part in diagram["parts"]} >= {"wokwi-dht22", "wokwi-led", "wokwi-resistor"}
    scenario = files["scenario"].read_text(encoding="utf-8")
    assert "control: temperature" in scenario
    assert "value: 25" in scenario and "value: 35" in scenario
    assert "expected: 0" in scenario and "expected: 1" in scenario
    assert "TEMP_NORMAL" in scenario and "TEMP_ALERT" in scenario
