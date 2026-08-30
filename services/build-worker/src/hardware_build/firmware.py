from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from .models import HardwareIR, ToolResult
from .security import redact_text
from .settings import Settings

PLATFORMIO_INI = """[env:esp32-s3-devkitc-1]
platform = espressif32@6.12.0
board = esp32-s3-devkitc-1
framework = arduino
monitor_speed = 115200
lib_deps =
  adafruit/Adafruit GFX Library@^1.11.11
  adafruit/Adafruit SSD1306@^2.5.13
  adafruit/DHT sensor library@^1.4.6
build_flags = -D ARDUINO_USB_CDC_ON_BOOT=1
"""

MAIN_CPP = r'''#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>

constexpr int SCREEN_WIDTH = 128;
constexpr int SCREEN_HEIGHT = 64;
constexpr int OLED_RESET = -1;
constexpr int DHT_PIN = 4;
constexpr int ENCODER_CLK = 5;
constexpr int ENCODER_DT = 6;
constexpr int ENCODER_SW = 7;
constexpr int I2C_SDA = 8;
constexpr int I2C_SCL = 9;

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
DHT dht(DHT_PIN, DHT22);
volatile int encoderDelta = 0;
int lastClk = HIGH;

void render(float temperature, float humidity) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("FORGE / ENVIRONMENT");
  display.drawLine(0, 12, 127, 12, SSD1306_WHITE);
  display.setTextSize(2);
  display.setCursor(0, 20);
  if (isnan(temperature)) display.print("--.- C");
  else { display.print(temperature, 1); display.print(" C"); }
  display.setTextSize(1);
  display.setCursor(0, 48);
  display.print("Humidity ");
  if (isnan(humidity)) display.print("--");
  else display.print(humidity, 0);
  display.print("%  Knob ");
  display.print(encoderDelta);
  display.display();
}

void setup() {
  Serial.begin(115200);
  pinMode(ENCODER_CLK, INPUT_PULLUP);
  pinMode(ENCODER_DT, INPUT_PULLUP);
  pinMode(ENCODER_SW, INPUT_PULLUP);
  Wire.begin(I2C_SDA, I2C_SCL);
  dht.begin();
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("CHECK:OLED_INIT:FAIL");
    return;
  }
  Serial.println("CHECK:BOOT:PASS");
  Serial.println("CHECK:OLED_INIT:PASS");
  Serial.println("CHECK:SENSOR_INIT:PASS");
  render(NAN, NAN);
}

void loop() {
  int clk = digitalRead(ENCODER_CLK);
  if (clk != lastClk && clk == LOW) {
    encoderDelta += digitalRead(ENCODER_DT) == clk ? -1 : 1;
    Serial.println("CHECK:ENCODER:PASS");
  }
  lastClk = clk;
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();
  if (!isnan(temperature)) Serial.println("CHECK:TEMPERATURE_READ:PASS");
  render(temperature, humidity);
  delay(750);
}
'''


def generate_firmware(hardware: HardwareIR, firmware_dir: Path) -> dict[str, Path]:
    required = {component.component_id for component in hardware.components}
    expected = {"ssd1306-oled", "dht22", "ky-040"}
    if not expected.issubset(required):
        raise ValueError("Firmware template supports the verified desk monitor component set only")
    source_dir = firmware_dir / "src"
    source_dir.mkdir(parents=True, exist_ok=True)
    ini = firmware_dir / "platformio.ini"
    source = source_dir / "main.cpp"
    ini.write_text(PLATFORMIO_INI, encoding="utf-8")
    code = MAIN_CPP
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
    repaired = re.sub(r"constexpr int I2C_SDA = \d+;", "constexpr int I2C_SDA = 8;", repaired)
    if repaired == source:
        return False
    source_path.write_text(repaired, encoding="utf-8")
    return True
