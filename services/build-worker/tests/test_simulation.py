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

    result = run_wokwi(Settings(wokwi_cli_token="wok_" + "x" * 40), simulation_dir, True)

    assert result.status == "passed"
    assert "motion sensor initialization" in result.evidence["checks"]
    assert "motion read" in result.evidence["checks"]


def test_wokwi_rejects_non_ci_token_without_spawning_cli(tmp_path: Path, monkeypatch):
    invoked = False
    (tmp_path / "test.scenario.yaml").write_text(
        "name: test\nversion: 1\nsteps:\n  - wait-serial: 'READY'\n",
        encoding="utf-8",
    )

    def fail_if_invoked(*_args, **_kwargs):
        nonlocal invoked
        invoked = True
        raise AssertionError("invalid credentials must fail before spawning wokwi-cli")

    monkeypatch.setattr("hardware_build.simulation.subprocess.run", fail_if_invoked)
    result = run_wokwi(Settings(wokwi_cli_token="legacy-token"), tmp_path, True)

    assert result.status == "unavailable"
    assert "documented Wokwi CI token format" in result.summary
    assert invoked is False


def test_temperature_alarm_wokwi_project_has_real_sensor_and_led_assertions(tmp_path: Path):
    hardware = deterministic_hardware_ir(
        deterministic_product_spec("Create an ESP32 temperature alarm with an LED above 30C")
    )
    files = generate_wokwi(hardware, tmp_path / "firmware", tmp_path / "simulation")

    diagram = json.loads(files["diagram"].read_text(encoding="utf-8"))
    assert {part["type"] for part in diagram["parts"]} >= {
        "wokwi-dht22",
        "wokwi-led",
        "wokwi-resistor",
    }
    esp = next(part for part in diagram["parts"] if part["id"] == "esp")
    assert esp["attrs"]["serialInterface"] == "USB_SERIAL_JTAG"
    assert ["esp:3V3.1", "sensor:VCC", "red", ["h30"]] in diagram["connections"]
    scenario = files["scenario"].read_text(encoding="utf-8")
    assert "control: temperature" in scenario
    assert "value: 25" in scenario and "value: 35" in scenario
    assert "value: 0" in scenario and "value: 1" in scenario
    assert "TEMP_NORMAL" in scenario and "TEMP_ALERT" in scenario


def test_temperature_alarm_scenario_tracks_an_updated_threshold(tmp_path: Path):
    hardware = deterministic_hardware_ir(
        deterministic_product_spec("Create an ESP32 temperature alarm above 30C")
    )
    files = generate_wokwi(
        hardware,
        tmp_path / "firmware",
        tmp_path / "simulation",
        "Create an ESP32 temperature alarm above 30C\n\nRequested update: threshold 35C",
    )

    scenario = files["scenario"].read_text(encoding="utf-8")
    assert "value: 30" in scenario
    assert "value: 40" in scenario
