from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .firmware_modules import FirmwareFragment, compose_fragments
from .models import HardwareIR, ToolResult
from .security import redact_text
from .settings import Settings

PLATFORMIO_INI = """[env:esp32-s3-devkitc-1]
platform = espressif32@6.12.0
board = esp32-s3-devkitc-1
framework = arduino
monitor_speed = 115200
{lib_deps}
build_flags = -D ARDUINO_USB_CDC_ON_BOOT=1
"""

def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _indent(block: str, spaces: int = 2) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line else "" for line in block.splitlines())


def _render_platformio(fragments: list[FirmwareFragment]) -> str:
    libraries = _unique([library for fragment in fragments for library in fragment.libraries])
    if not libraries:
        return PLATFORMIO_INI.format(lib_deps="").replace("\n\n", "\n", 1)
    deps = "lib_deps =\n" + "\n".join(f"  {library}" for library in libraries)
    return PLATFORMIO_INI.format(lib_deps=deps)


def _render_source(fragments: list[FirmwareFragment]) -> str:
    includes = ["Arduino.h"]
    i2c_pins = next(
        (fragment.i2c_pins for fragment in fragments if fragment.i2c_pins is not None), None
    )
    if i2c_pins is not None:
        includes.append("Wire.h")
    includes.extend(include for fragment in fragments for include in fragment.includes)

    sections = ["\n".join(f"#include <{include}>" for include in _unique(includes))]
    sections.append("""struct MonitorTelemetry {
  float temperature_c = NAN;
  float humidity_percent = NAN;
  int encoder_delta = 0;
};

MonitorTelemetry telemetry;""")
    if i2c_pins is not None:
        sections.append(
            f"constexpr int I2C_SDA = {i2c_pins[0]};\nconstexpr int I2C_SCL = {i2c_pins[1]};"
        )
    declarations = [fragment.declarations for fragment in fragments if fragment.declarations]
    if declarations:
        sections.append("\n\n".join(declarations))
    helpers = [fragment.helpers for fragment in fragments if fragment.helpers]
    if helpers:
        sections.append("\n\n".join(helpers))

    setup_lines = ["Serial.begin(115200);", 'Serial.println("CHECK:BOOT:PASS");']
    if i2c_pins is not None:
        setup_lines.append("Wire.begin(I2C_SDA, I2C_SCL);")
    setup_lines.extend(fragment.setup for fragment in fragments if fragment.setup)
    sections.append("void setup() {\n" + _indent("\n".join(setup_lines)) + "\n}")

    loop_lines = [fragment.loop for fragment in fragments if fragment.loop]
    loop_lines.extend(fragment.post_loop for fragment in fragments if fragment.post_loop)
    loop_lines.append("delay(750);")
    sections.append("void loop() {\n" + _indent("\n".join(loop_lines)) + "\n}")
    return "\n\n".join(sections) + "\n"


def generate_firmware(hardware: HardwareIR, firmware_dir: Path) -> dict[str, Path]:
    fragments = compose_fragments(hardware)
    source_dir = firmware_dir / "src"
    source_dir.mkdir(parents=True, exist_ok=True)
    ini = firmware_dir / "platformio.ini"
    source = source_dir / "main.cpp"
    ini.write_text(_render_platformio(fragments), encoding="utf-8")
    code = _render_source(fragments)
    if os.getenv("INJECT_COMPILE_FAILURE_ONCE") == "true":
        code = code.replace("display.begin", "display.begin_broken", 1)
    source.write_text(code, encoding="utf-8")
    return {"platformio": ini, "source": source}


def compile_firmware(settings: Settings, firmware_dir: Path) -> ToolResult:
    executable = shutil.which(settings.platformio_cmd)
    if not executable:
        return ToolResult(
            status="unavailable",
            summary="PlatformIO is not installed in the worker tool container.",
            evidence={"command": settings.platformio_cmd, "install": "pipx install platformio"},
        )
    completed = subprocess.run(
        [executable, "run"], cwd=firmware_dir, capture_output=True, text=True, timeout=900, check=False
    )
    output = redact_text((completed.stdout + "\n" + completed.stderr)[-16000:], settings)
    firmware_bin = firmware_dir / ".pio" / "build" / "esp32-s3-devkitc-1" / "firmware.bin"
    return ToolResult(
        status="passed" if completed.returncode == 0 and firmware_bin.exists() else "failed",
        summary="PlatformIO compiled the ESP32-S3 firmware." if completed.returncode == 0 else "PlatformIO compilation failed.",
        evidence={"exit_code": completed.returncode, "output": output, "firmware_bin": str(firmware_bin) if firmware_bin.exists() else None},
    )


def deterministic_repair(source_path: Path, compiler_output: str) -> bool:
    """Conservative repair fallback for known demo faults; never declares success itself."""
    source = source_path.read_text(encoding="utf-8")
    repaired = source
    repairs = {
        "begin_broken": "begin",
        "Adafruit_SSD13066": "Adafruit_SSD1306",
        "DHT222": "DHT22",
    }
    for broken, valid in repairs.items():
        if broken in repaired and (broken in compiler_output or "not declared" in compiler_output):
            repaired = repaired.replace(broken, valid)
    if repaired == source:
        return False
    source_path.write_text(repaired, encoding="utf-8")
    return True
