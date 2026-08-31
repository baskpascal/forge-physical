from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from .incremental import temperature_threshold_c
from .models import HardwareIR, ToolResult
from .security import redact_text
from .settings import Settings


def generate_wokwi(
    hardware: HardwareIR,
    firmware_dir: Path,
    simulation_dir: Path,
    prompt: str | None = None,
) -> dict[str, Path]:
    simulation_dir.mkdir(parents=True, exist_ok=True)
    has_temperature_alarm = {component.component_id for component in hardware.components} >= {
        "dht22",
        "led",
    }
    if has_temperature_alarm:
        return _generate_temperature_alarm_wokwi(
            firmware_dir,
            simulation_dir,
            temperature_threshold_c(prompt or ""),
        )
    has_motion_sensor = any(
        component.component_id == "mpu6050" for component in hardware.components
    )
    parts = [
        {"type": "board-esp32-s3-devkitc-1", "id": "esp", "top": 0, "left": 0, "attrs": {}},
        {
            "type": "wokwi-ssd1306",
            "id": "display",
            "top": -120,
            "left": 220,
            "attrs": {"i2cAddress": "0x3c"},
        },
        {
            "type": "wokwi-dht22",
            "id": "sensor",
            "top": 50,
            "left": 240,
            "attrs": {"temperature": "23.5", "humidity": "45"},
        },
        {"type": "wokwi-ky-040", "id": "encoder", "top": 180, "left": 210, "attrs": {}},
    ]
    if has_motion_sensor:
        parts.append(
            {"type": "wokwi-mpu6050", "id": "motion", "top": 180, "left": 360, "attrs": {}}
        )
    connections = [
        ["esp:8", "display:SDA", "green", ["h20"]],
        ["esp:9", "display:SCL", "blue", ["h30"]],
        ["esp:3V3", "display:VCC", "red", ["h40"]],
        ["esp:GND.1", "display:GND", "black", ["h50"]],
        ["esp:4", "sensor:SDA", "green", ["h60"]],
        ["esp:3V3", "sensor:VCC", "red", ["h70"]],
        ["esp:GND.1", "sensor:GND", "black", ["h80"]],
        ["esp:5", "encoder:CLK", "orange", ["h90"]],
        ["esp:6", "encoder:DT", "yellow", ["h100"]],
        ["esp:7", "encoder:SW", "purple", ["h110"]],
        ["esp:3V3", "encoder:VCC", "red", ["h120"]],
        ["esp:GND.1", "encoder:GND", "black", ["h130"]],
    ]
    if has_motion_sensor:
        connections.extend(
            [
                ["esp:8", "motion:SDA", "green", ["h140"]],
                ["esp:9", "motion:SCL", "blue", ["h150"]],
                ["esp:3V3", "motion:VCC", "red", ["h160"]],
                ["esp:GND.1", "motion:GND", "black", ["h170"]],
            ]
        )
    diagram = simulation_dir / "diagram.json"
    diagram.write_text(
        json.dumps(
            {
                "version": 1,
                "author": "Forge Physical",
                "editor": "wokwi",
                "parts": parts,
                "connections": connections,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    firmware_bin = firmware_dir / ".pio" / "build" / "esp32-s3-devkitc-1" / "firmware.bin"
    firmware_elf = firmware_dir / ".pio" / "build" / "esp32-s3-devkitc-1" / "firmware.elf"
    wokwi_toml = simulation_dir / "wokwi.toml"
    wokwi_toml.write_text(
        "[wokwi]\nversion = 1\nfirmware = '../firmware/.pio/build/esp32-s3-devkitc-1/firmware.bin'\nelf = '../firmware/.pio/build/esp32-s3-devkitc-1/firmware.elf'\n",
        encoding="utf-8",
    )
    scenario = simulation_dir / "desk-monitor.scenario.yaml"
    motion_steps = (
        """
  - wait-serial: 'CHECK:MOTION_INIT:PASS'
  - wait-serial: 'CHECK:MOTION_READ:PASS'"""
        if has_motion_sensor
        else ""
    )
    scenario.write_text(
        f"""name: 'Desk environmental monitor'
version: 1
author: 'Forge Physical'
steps:
  - wait-serial: 'CHECK:BOOT:PASS'
  - wait-serial: 'CHECK:OLED_INIT:PASS'
  - wait-serial: 'CHECK:SENSOR_INIT:PASS'
  - set-control:
      part-id: sensor
      control: temperature
      value: 27
  - delay: 1500ms
  - wait-serial: 'CHECK:TEMPERATURE_READ:PASS'
{motion_steps}
""",
        encoding="utf-8",
    )
    return {
        "diagram": diagram,
        "config": wokwi_toml,
        "scenario": scenario,
        "firmware": firmware_bin,
        "elf": firmware_elf,
    }


def _generate_temperature_alarm_wokwi(
    firmware_dir: Path, simulation_dir: Path, threshold_c: float
) -> dict[str, Path]:
    """Materialize the one production Wokwi golden path with an observable LED output."""
    diagram = simulation_dir / "diagram.json"
    diagram.write_text(
        json.dumps(
            {
                "version": 1,
                "author": "Forge Physical",
                "editor": "wokwi",
                "parts": [
                    # The firmware is built with ARDUINO_USB_CDC_ON_BOOT=1, so Wokwi
                    # must expose the S3 USB serial/JTAG transport for scenario
                    # wait-serial assertions to receive the firmware markers.
                    {
                        "type": "board-esp32-s3-devkitc-1",
                        "id": "esp",
                        "top": 0,
                        "left": 0,
                        "attrs": {"serialInterface": "USB_SERIAL_JTAG"},
                    },
                    {
                        "type": "wokwi-dht22",
                        "id": "sensor",
                        "top": 20,
                        "left": 240,
                        "attrs": {"temperature": "25", "humidity": "45"},
                    },
                    {
                        "type": "wokwi-resistor",
                        "id": "led_resistor",
                        "top": 170,
                        "left": 220,
                        "attrs": {"value": "220"},
                    },
                    {
                        "type": "wokwi-led",
                        "id": "warning_led",
                        "top": 170,
                        "left": 340,
                        "attrs": {"color": "red"},
                    },
                ],
                "connections": [
                    ["esp:4", "sensor:SDA", "green", ["h20"]],
                    ["esp:3V3.1", "sensor:VCC", "red", ["h30"]],
                    ["esp:GND.1", "sensor:GND", "black", ["h40"]],
                    ["esp:10", "led_resistor:1", "orange", ["h50"]],
                    ["led_resistor:2", "warning_led:A", "orange", ["h60"]],
                    ["esp:GND.1", "warning_led:C", "black", ["h70"]],
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    firmware_bin = firmware_dir / ".pio" / "build" / "esp32-s3-devkitc-1" / "firmware.bin"
    firmware_elf = firmware_dir / ".pio" / "build" / "esp32-s3-devkitc-1" / "firmware.elf"
    wokwi_toml = simulation_dir / "wokwi.toml"
    wokwi_toml.write_text(
        "[wokwi]\nversion = 1\nfirmware = '../firmware/.pio/build/esp32-s3-devkitc-1/firmware.bin'\nelf = '../firmware/.pio/build/esp32-s3-devkitc-1/firmware.elf'\n",
        encoding="utf-8",
    )
    scenario = simulation_dir / "temperature-alarm.scenario.yaml"
    normal_temperature = round(threshold_c - 5.0, 1)
    alert_temperature = round(threshold_c + 5.0, 1)
    scenario.write_text(
        f"""name: 'ESP32 temperature alarm'
version: 1
author: 'Forge Physical'
steps:
  - wait-serial: 'COUP_READY'
  - set-control:
      part-id: sensor
      control: temperature
      value: {normal_temperature:g}
  - delay: 2500ms
  - wait-serial: 'TEMP_NORMAL'
  - expect-pin:
      part-id: esp
      pin: 10
      value: 0
  - set-control:
      part-id: sensor
      control: temperature
      value: {alert_temperature:g}
  - delay: 2500ms
  - wait-serial: 'TEMP_ALERT'
  - expect-pin:
      part-id: esp
      pin: 10
      value: 1
  - wait-serial: 'COUP_TEST_PASS'
""",
        encoding="utf-8",
    )
    return {
        "diagram": diagram,
        "config": wokwi_toml,
        "scenario": scenario,
        "firmware": firmware_bin,
        "elf": firmware_elf,
    }


def wokwi_token_is_valid(token: str | None) -> bool:
    """Validate the documented Wokwi CI token envelope without exposing it."""
    normalized = token.strip() if token else ""
    return normalized.startswith("wok_") and len(normalized) == 44


def _scenario_evidence(simulation_dir: Path) -> tuple[Path | None, str, list[str]]:
    scenario_paths = sorted(simulation_dir.glob("*.scenario.yaml"))
    if len(scenario_paths) != 1:
        return None, "", []
    scenario = scenario_paths[0]
    scenario_text = scenario.read_text(encoding="utf-8")
    checks = ["boot", "OLED initialization", "sensor initialization", "temperature read"]
    if "CHECK:MOTION_READ:PASS" in scenario_text:
        checks.extend(["motion sensor initialization", "motion read"])
    if "TEMP_NORMAL" in scenario_text:
        checks = [
            "temperature_normal",
            "temperature_alert",
            "LED off below configured threshold",
            "LED on above configured threshold",
        ]
    return scenario, scenario_text, checks


def run_wokwi(settings: Settings, simulation_dir: Path, firmware_passed: bool) -> ToolResult:
    if not firmware_passed:
        return ToolResult(
            status="not_run", summary="Simulation requires a compiled firmware binary."
        )
    scenario, scenario_text, checks = _scenario_evidence(simulation_dir)
    if scenario is None:
        return ToolResult(
            status="failed", summary="Wokwi project must contain exactly one automation scenario."
        )
    if not settings.wokwi_cli_token:
        return ToolResult(
            status="unavailable",
            summary="Wokwi CI is configured but no WOKWI_CLI_TOKEN is available.",
            evidence={"required_env": "WOKWI_CLI_TOKEN", "checks": checks},
        )
    if not wokwi_token_is_valid(settings.wokwi_cli_token):
        return ToolResult(
            status="unavailable",
            summary="WOKWI_CLI_TOKEN is present but does not match the documented Wokwi CI token format.",
            evidence={"required_format": "wok_ prefix, 44 characters", "checks": checks},
        )
    executable = shutil.which(settings.wokwi_cli_cmd)
    if not executable:
        return ToolResult(
            status="unavailable",
            summary="Wokwi token exists, but wokwi-cli is not installed in the worker.",
            evidence={"command": settings.wokwi_cli_cmd, "checks": checks},
        )
    environment = {**os.environ, "WOKWI_CLI_TOKEN": settings.wokwi_cli_token.strip()}
    lint = subprocess.run(
        [executable, "lint"],
        cwd=simulation_dir,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    lint_output = redact_text((lint.stdout + "\n" + lint.stderr)[-16000:], settings)
    serial_log = simulation_dir / "serial.log"
    command = [executable, ".", "--scenario", scenario.name, "--serial-log-file", serial_log.name]
    # The scenario itself waits for COUP_TEST_PASS after both GPIO assertions.
    # Do not use --expect-text here: it exits as soon as the marker appears and
    # can bypass the scenario's terminal completion reporting.
    command.extend(["--timeout", "20000", "--timeout-exit-code", "1"])
    completed = subprocess.run(
        command,
        cwd=simulation_dir,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = redact_text((completed.stdout + "\n" + completed.stderr)[-16000:], settings)
    serial_output = redact_text(
        serial_log.read_text(encoding="utf-8") if serial_log.exists() else completed.stdout,
        settings,
    )
    expected_serial = [
        line.split("'", 2)[1]
        for line in scenario_text.splitlines()
        if "wait-serial:" in line and "'" in line
    ]
    missing_markers = [marker for marker in expected_serial if marker not in serial_output]
    passed = lint.returncode == 0 and completed.returncode == 0 and not missing_markers
    evidence = {
        "lint_exit_code": lint.returncode,
        "lint_output": lint_output,
        "command": [Path(item).name if item == executable else item for item in command],
        "exit_code": completed.returncode,
        "output": output,
        "serial_log": "serial.log" if serial_log.exists() else None,
        "serial_output": serial_output[-16000:],
        "expected_serial": expected_serial,
        "missing_serial": missing_markers,
        "checks": checks,
        "validation_passed": passed,
    }
    (simulation_dir / "simulation-result.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8"
    )
    return ToolResult(
        status="passed" if passed else "failed",
        summary="Wokwi lint, sensor scenario, pin assertions, and serial validation passed."
        if passed
        else "Wokwi lint, simulation, or behavioral validation failed.",
        evidence=evidence,
    )
