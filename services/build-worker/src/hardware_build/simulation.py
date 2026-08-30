from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from .models import HardwareIR, ToolResult
from .security import redact_text
from .settings import Settings


def generate_wokwi(hardware: HardwareIR, firmware_dir: Path, simulation_dir: Path) -> dict[str, Path]:
    simulation_dir.mkdir(parents=True, exist_ok=True)
    has_motion_sensor = any(component.component_id == "mpu6050" for component in hardware.components)
    parts = [
        {"type": "board-esp32-s3-devkitc-1", "id": "esp", "top": 0, "left": 0, "attrs": {}},
        {"type": "wokwi-ssd1306", "id": "display", "top": -120, "left": 220, "attrs": {"i2cAddress": "0x3c"}},
        {"type": "wokwi-dht22", "id": "sensor", "top": 50, "left": 240, "attrs": {"temperature": "23.5", "humidity": "45"}},
        {"type": "wokwi-ky-040", "id": "encoder", "top": 180, "left": 210, "attrs": {}},
    ]
    if has_motion_sensor:
        parts.append({"type": "wokwi-mpu6050", "id": "motion", "top": 180, "left": 360, "attrs": {}})
    connections = [
        ["esp:8", "display:SDA", "green", ["h20"]], ["esp:9", "display:SCL", "blue", ["h30"]],
        ["esp:3V3", "display:VCC", "red", ["h40"]], ["esp:GND.1", "display:GND", "black", ["h50"]],
        ["esp:4", "sensor:SDA", "green", ["h60"]], ["esp:3V3", "sensor:VCC", "red", ["h70"]],
        ["esp:GND.1", "sensor:GND", "black", ["h80"]], ["esp:5", "encoder:CLK", "orange", ["h90"]],
        ["esp:6", "encoder:DT", "yellow", ["h100"]], ["esp:7", "encoder:SW", "purple", ["h110"]],
        ["esp:3V3", "encoder:VCC", "red", ["h120"]], ["esp:GND.1", "encoder:GND", "black", ["h130"]],
    ]
    if has_motion_sensor:
        connections.extend([
            ["esp:8", "motion:SDA", "green", ["h140"]],
            ["esp:9", "motion:SCL", "blue", ["h150"]],
            ["esp:3V3", "motion:VCC", "red", ["h160"]],
            ["esp:GND.1", "motion:GND", "black", ["h170"]],
        ])
    diagram = simulation_dir / "diagram.json"
    diagram.write_text(json.dumps({"version": 1, "author": "Forge Physical", "editor": "wokwi", "parts": parts, "connections": connections}, indent=2), encoding="utf-8")
    firmware_bin = firmware_dir / ".pio" / "build" / "esp32-s3-devkitc-1" / "firmware.bin"
    firmware_elf = firmware_dir / ".pio" / "build" / "esp32-s3-devkitc-1" / "firmware.elf"
    wokwi_toml = simulation_dir / "wokwi.toml"
    wokwi_toml.write_text(
        "[wokwi]\nversion = 1\nfirmware = '../firmware/.pio/build/esp32-s3-devkitc-1/firmware.bin'\nelf = '../firmware/.pio/build/esp32-s3-devkitc-1/firmware.elf'\n",
        encoding="utf-8",
    )
    scenario = simulation_dir / "desk-monitor.scenario.yaml"
    motion_steps = """
  - wait-serial: 'CHECK:MOTION_INIT:PASS'
  - wait-serial: 'CHECK:MOTION_READ:PASS'""" if has_motion_sensor else ""
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
    return {"diagram": diagram, "config": wokwi_toml, "scenario": scenario, "firmware": firmware_bin, "elf": firmware_elf}


def run_wokwi(settings: Settings, simulation_dir: Path, firmware_passed: bool) -> ToolResult:
    if not firmware_passed:
        return ToolResult(status="not_run", summary="Simulation requires a compiled firmware binary.")
    if not settings.wokwi_cli_token:
        return ToolResult(
            status="unavailable",
            summary="Wokwi CI is configured but no WOKWI_CLI_TOKEN is available.",
            evidence={"required_env": "WOKWI_CLI_TOKEN"},
        )
    executable = shutil.which(settings.wokwi_cli_cmd)
    if not executable:
        return ToolResult(
            status="unavailable",
            summary="Wokwi token exists, but wokwi-cli is not installed in the worker.",
            evidence={"command": settings.wokwi_cli_cmd},
        )
    environment = {**os.environ, "WOKWI_CLI_TOKEN": settings.wokwi_cli_token}
    completed = subprocess.run(
        [executable, ".", "--scenario", "desk-monitor.scenario.yaml", "--timeout", "20000", "--timeout-exit-code", "1"],
        cwd=simulation_dir, env=environment, capture_output=True, text=True, timeout=120, check=False,
    )
    output = redact_text((completed.stdout + "\n" + completed.stderr)[-16000:], settings)
    scenario_text = (simulation_dir / "desk-monitor.scenario.yaml").read_text(encoding="utf-8")
    checks = ["boot", "OLED initialization", "sensor initialization", "temperature read"]
    if "CHECK:MOTION_READ:PASS" in scenario_text:
        checks.extend(["motion sensor initialization", "motion read"])
    return ToolResult(
        status="passed" if completed.returncode == 0 else "failed",
        summary="Wokwi completed the automated hardware scenario." if completed.returncode == 0 else "Wokwi simulation failed.",
        evidence={"exit_code": completed.returncode, "output": output, "checks": checks},
    )
