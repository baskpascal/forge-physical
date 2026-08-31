from pathlib import Path

import pytest

from hardware_build.firmware import deterministic_repair, generate_firmware
from hardware_build.models import ComponentInstance, Connection, Endpoint, HardwareIR
from hardware_build.planning import deterministic_hardware_ir, deterministic_product_spec


def _connection(component_ref: str, component_pin: str, board_pin: str) -> Connection:
    return Connection(
        **{
            "from": Endpoint(ref="board", pin=board_pin),
            "to": Endpoint(ref=component_ref, pin=component_pin),
            "interface": "i2c" if component_pin in {"SDA", "SCL"} else "gpio",
            "reason": "test connection",
        }
    )


def _hardware(component_ids: list[str]) -> HardwareIR:
    pin_maps = {
        "ssd1306-oled": {"SDA": "GPIO11", "SCL": "GPIO12"},
        "dht22": {"SDA": "GPIO15"},
        "ky-040": {"CLK": "GPIO4", "DT": "GPIO5", "SW": "GPIO6"},
        "mpu6050": {"SDA": "GPIO11", "SCL": "GPIO12"},
        "led": {"A": "GPIO10"},
    }
    refs = {
        "ssd1306-oled": "display",
        "dht22": "sensor",
        "ky-040": "encoder",
        "mpu6050": "imu",
        "led": "warning_led",
    }
    components = [
        ComponentInstance(ref=refs[component_id], component_id=component_id, label=component_id)
        for component_id in component_ids
    ]
    connections = [
        _connection(refs[component_id], component_pin, board_pin)
        for component_id in component_ids
        for component_pin, board_pin in pin_maps[component_id].items()
    ]
    return HardwareIR(
        board=ComponentInstance(
            ref="board", component_id="esp32-s3-devkit", label="ESP32-S3"
        ),
        components=components,
        connections=connections,
        power=[],
    )


def test_firmware_generation_and_known_repair(tmp_path: Path):
    hardware = deterministic_hardware_ir(deterministic_product_spec("Build an OLED desk temperature monitor with a knob"))
    files = generate_firmware(hardware, tmp_path)
    assert "CHECK:BOOT:PASS" in files["source"].read_text(encoding="utf-8")
    source = files["source"].read_text(encoding="utf-8").replace("display.begin", "display.begin_broken", 1)
    files["source"].write_text(source, encoding="utf-8")
    assert deterministic_repair(files["source"], "no member named begin_broken")
    assert "begin_broken" not in files["source"].read_text(encoding="utf-8")


def test_temperature_alarm_firmware_emits_observable_wokwi_markers(tmp_path: Path):
    hardware = deterministic_hardware_ir(
        deterministic_product_spec("Create an ESP32 temperature alarm with an LED above 30C")
    )
    source = generate_firmware(hardware, tmp_path)["source"].read_text(encoding="utf-8")

    assert "COUP_ALARM_LED_PIN = 10" in source
    assert "COUP_READY" in source
    assert "TEMP_NORMAL" in source
    assert "TEMP_ALERT" in source
    assert "COUP_TEST_PASS" in source


def test_compile_failure_injection_applies_to_the_temperature_alarm(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("INJECT_COMPILE_FAILURE_ONCE", "true")
    hardware = deterministic_hardware_ir(
        deterministic_product_spec("Create an ESP32 temperature alarm with an LED above 30C")
    )

    source = generate_firmware(hardware, tmp_path)["source"].read_text(encoding="utf-8")

    assert "Serial.begin_broken(115200);" in source


@pytest.mark.parametrize(
    ("component_ids", "expected_markers"),
    [
        (["dht22"], ["DHT sensor library", "SENSOR_INIT"]),
        (["ky-040"], ["ENCODER_CLK = 4", "ENCODER_INIT"]),
        (["ssd1306-oled", "mpu6050"], ["OLED_INIT", "MOTION_INIT"]),
        (["dht22", "ky-040", "mpu6050"], ["DHT.h", "ENCODER_INIT", "MOTION_READ"]),
    ],
)
def test_composes_supported_component_combinations(
    tmp_path: Path, component_ids: list[str], expected_markers: list[str]
):
    files = generate_firmware(_hardware(component_ids), tmp_path)
    generated = files["platformio"].read_text(encoding="utf-8") + files["source"].read_text(
        encoding="utf-8"
    )

    for marker in expected_markers:
        assert marker in generated


def test_derives_pins_deduplicates_dependencies_and_is_deterministic(tmp_path: Path):
    hardware = _hardware(["mpu6050", "dht22", "ssd1306-oled"])
    first = generate_firmware(hardware, tmp_path / "first")
    reordered = hardware.model_copy(
        update={
            "components": list(reversed(hardware.components)),
            "connections": list(reversed(hardware.connections)),
        }
    )
    second = generate_firmware(reordered, tmp_path / "second")

    first_source = first["source"].read_text(encoding="utf-8")
    first_ini = first["platformio"].read_text(encoding="utf-8")
    assert first_source == second["source"].read_text(encoding="utf-8")
    assert first_ini == second["platformio"].read_text(encoding="utf-8")
    assert "constexpr int I2C_SDA = 11;" in first_source
    assert "constexpr int SENSOR_DHT_PIN = 15;" in first_source
    assert first_source.count("#include <Adafruit_Sensor.h>") == 1
    assert first_ini.count("Adafruit Unified Sensor") == 1


def test_base_monitor_flows_sensor_and_encoder_telemetry_to_oled(tmp_path: Path):
    files = generate_firmware(
        _hardware(["ssd1306-oled", "dht22", "ky-040"]),
        tmp_path,
    )
    source = files["source"].read_text(encoding="utf-8")

    assert "telemetry.temperature_c = sensor.readTemperature();" in source
    assert "telemetry.humidity_percent = sensor.readHumidity();" in source
    assert "telemetry.encoder_delta +=" in source
    assert 'display.print("Temp: ");' in source
    assert 'display.print("Humidity: ");' in source
    assert 'display.print("Knob: ");' in source
    assert "display.println(telemetry.encoder_delta);" in source
    loop_start = source.index("void loop()")
    assert source.index("telemetry.temperature_c = sensor.readTemperature();", loop_start) < source.index(
        "render_display(telemetry);", loop_start
    )


def test_oled_without_sensor_or_encoder_renders_safe_empty_telemetry(tmp_path: Path):
    files = generate_firmware(_hardware(["ssd1306-oled"]), tmp_path)
    source = files["source"].read_text(encoding="utf-8")

    assert "float temperature_c = NAN;" in source
    assert "float humidity_percent = NAN;" in source
    assert "int encoder_delta = 0;" in source
    assert "render_display(telemetry);" in source


def test_fails_explicitly_for_incomplete_or_incompatible_hardware_ir(tmp_path: Path):
    missing_pin = _hardware(["dht22"]).model_copy(update={"connections": []})
    with pytest.raises(ValueError, match=r"Missing signal connection for sensor\.SDA"):
        generate_firmware(missing_pin, tmp_path / "missing")

    different_i2c_buses = _hardware(["ssd1306-oled", "mpu6050"])
    different_i2c_buses.connections[-2:] = [
        _connection("imu", "SDA", "GPIO13"),
        _connection("imu", "SCL", "GPIO14"),
    ]
    with pytest.raises(ValueError, match="All I2C modules must share one bus"):
        generate_firmware(different_i2c_buses, tmp_path / "bus")
