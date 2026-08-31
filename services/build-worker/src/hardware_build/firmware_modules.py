from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .models import ComponentInstance, HardwareIR


@dataclass(frozen=True)
class FirmwareFragment:
    includes: tuple[str, ...] = ()
    libraries: tuple[str, ...] = ()
    declarations: str = ""
    helpers: str = ""
    setup: str = ""
    loop: str = ""
    post_loop: str = ""
    i2c_pins: tuple[int, int] | None = None


@dataclass(frozen=True)
class FirmwareModule:
    component_id: str
    order: int
    render: Callable[[HardwareIR, ComponentInstance], FirmwareFragment]


def _identifier(value: str) -> str:
    identifier = re.sub(r"[^a-zA-Z0-9_]", "_", value)
    if not identifier or identifier[0].isdigit():
        identifier = f"component_{identifier}"
    return identifier.lower()


def _pin_number(hardware: HardwareIR, component: ComponentInstance, pin: str) -> int:
    board_ref = hardware.board.ref
    candidates: set[str] = set()
    for connection in hardware.connections:
        endpoints = (connection.from_, connection.to)
        if (
            endpoints[0].ref == component.ref
            and endpoints[0].pin == pin
            and endpoints[1].ref == board_ref
        ):
            candidates.add(endpoints[1].pin)
        if (
            endpoints[1].ref == component.ref
            and endpoints[1].pin == pin
            and endpoints[0].ref == board_ref
        ):
            candidates.add(endpoints[0].pin)

    if not candidates:
        raise ValueError(
            f"Missing signal connection for {component.ref}.{pin} to board {board_ref}"
        )
    if len(candidates) != 1:
        raise ValueError(
            f"Ambiguous signal connection for {component.ref}.{pin}: {sorted(candidates)}"
        )
    board_pin = next(iter(candidates))
    match = re.fullmatch(r"GPIO(\d+)", board_pin, flags=re.IGNORECASE)
    if not match:
        raise ValueError(
            f"Firmware requires a GPIO board pin for {component.ref}.{pin}; got {board_pin}"
        )
    return int(match.group(1))


def _i2c_pins(hardware: HardwareIR, component: ComponentInstance) -> tuple[int, int]:
    return (
        _pin_number(hardware, component, "SDA"),
        _pin_number(hardware, component, "SCL"),
    )


def _ssd1306(hardware: HardwareIR, component: ComponentInstance) -> FirmwareFragment:
    name = _identifier(component.ref)
    prefix = name.upper()
    i2c_pins = _i2c_pins(hardware, component)
    return FirmwareFragment(
        includes=("Adafruit_GFX.h", "Adafruit_SSD1306.h"),
        libraries=(
            "adafruit/Adafruit GFX Library@1.11.11",
            "adafruit/Adafruit SSD1306@2.5.13",
        ),
        declarations=f"""constexpr int {prefix}_SCREEN_WIDTH = 128;
constexpr int {prefix}_SCREEN_HEIGHT = 64;
constexpr int {prefix}_OLED_RESET = -1;
Adafruit_SSD1306 {name}({prefix}_SCREEN_WIDTH, {prefix}_SCREEN_HEIGHT, &Wire, {prefix}_OLED_RESET);""",
        helpers=f"""void render_{name}(const MonitorTelemetry& telemetry) {{
  {name}.clearDisplay();
  {name}.setTextColor(SSD1306_WHITE);
  {name}.setTextSize(1);
  {name}.setCursor(0, 0);
  {name}.println("FORGE / PHYSICAL");
  {name}.drawLine(0, 12, 127, 12, SSD1306_WHITE);
  {name}.setCursor(0, 20);
  {name}.print("Temp: ");
  if (isnan(telemetry.temperature_c)) {name}.println("--");
  else {{ {name}.print(telemetry.temperature_c, 1); {name}.println(" C"); }}
  {name}.print("Humidity: ");
  if (isnan(telemetry.humidity_percent)) {name}.println("--");
  else {{ {name}.print(telemetry.humidity_percent, 1); {name}.println(" %"); }}
  {name}.print("Knob: ");
  {name}.println(telemetry.encoder_delta);
  {name}.display();
}}""",
        setup=f"""if (!{name}.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {{
    Serial.println("CHECK:OLED_INIT:FAIL");
    return;
  }}
  Serial.println("CHECK:OLED_INIT:PASS");
  render_{name}(telemetry);""",
        post_loop=f"render_{name}(telemetry);",
        i2c_pins=i2c_pins,
    )


def _dht22(hardware: HardwareIR, component: ComponentInstance) -> FirmwareFragment:
    name = _identifier(component.ref)
    prefix = name.upper()
    pin = _pin_number(hardware, component, "SDA")
    alarm_led = next((item for item in hardware.components if item.component_id == "led"), None)
    alarm_declaration = ""
    alarm_setup = ""
    alarm_loop = ""
    if alarm_led:
        alarm_pin = _pin_number(hardware, alarm_led, "A")
        alarm_declaration = f"""\nconstexpr int COUP_ALARM_LED_PIN = {alarm_pin};
constexpr float COUP_ALARM_THRESHOLD_C = 30.0f;"""
        alarm_setup = '\n  pinMode(COUP_ALARM_LED_PIN, OUTPUT);\n  digitalWrite(COUP_ALARM_LED_PIN, LOW);\n  Serial.println("COUP_READY");'
        alarm_loop = """
  if (!isnan(telemetry.temperature_c)) {
    if (telemetry.temperature_c > COUP_ALARM_THRESHOLD_C) {
      digitalWrite(COUP_ALARM_LED_PIN, HIGH);
      Serial.println("TEMP_ALERT");
      Serial.println("COUP_TEST_PASS");
    } else {
      digitalWrite(COUP_ALARM_LED_PIN, LOW);
      Serial.println("TEMP_NORMAL");
    }
  }"""
    return FirmwareFragment(
        includes=("DHT.h",),
        libraries=(
            "adafruit/Adafruit Unified Sensor@1.1.15",
            "adafruit/DHT sensor library@1.4.6",
        ),
        declarations=f"""constexpr int {prefix}_DHT_PIN = {pin};
DHT {name}({prefix}_DHT_PIN, DHT22);{alarm_declaration}""",
        setup=f"""{name}.begin();
  Serial.println("CHECK:SENSOR_INIT:PASS");{alarm_setup}""",
        loop=f"""telemetry.humidity_percent = {name}.readHumidity();
  telemetry.temperature_c = {name}.readTemperature();
  if (!isnan(telemetry.temperature_c) && !isnan(telemetry.humidity_percent)) {{
    Serial.println("CHECK:TEMPERATURE_READ:PASS");
  }}{alarm_loop}""",
    )


def _led(_hardware: HardwareIR, _component: ComponentInstance) -> FirmwareFragment:
    """The DHT22 alarm module owns the LED behavior when both are selected."""
    return FirmwareFragment()


def _ky040(hardware: HardwareIR, component: ComponentInstance) -> FirmwareFragment:
    name = _identifier(component.ref)
    prefix = name.upper()
    clk = _pin_number(hardware, component, "CLK")
    dt = _pin_number(hardware, component, "DT")
    switch = _pin_number(hardware, component, "SW")
    return FirmwareFragment(
        declarations=f"""constexpr int {prefix}_ENCODER_CLK = {clk};
constexpr int {prefix}_ENCODER_DT = {dt};
constexpr int {prefix}_ENCODER_SW = {switch};
int {name}_last_clk = HIGH;""",
        setup=f"""pinMode({prefix}_ENCODER_CLK, INPUT_PULLUP);
  pinMode({prefix}_ENCODER_DT, INPUT_PULLUP);
  pinMode({prefix}_ENCODER_SW, INPUT_PULLUP);
  Serial.println("CHECK:ENCODER_INIT:PASS");""",
        loop=f"""int {name}_clk = digitalRead({prefix}_ENCODER_CLK);
  if ({name}_clk != {name}_last_clk && {name}_clk == LOW) {{
    telemetry.encoder_delta += digitalRead({prefix}_ENCODER_DT) == {name}_clk ? -1 : 1;
    Serial.println("CHECK:ENCODER:PASS");
  }}
  {name}_last_clk = {name}_clk;""",
    )


def _mpu6050(hardware: HardwareIR, component: ComponentInstance) -> FirmwareFragment:
    name = _identifier(component.ref)
    i2c_pins = _i2c_pins(hardware, component)
    return FirmwareFragment(
        includes=("Adafruit_Sensor.h", "Adafruit_MPU6050.h"),
        libraries=(
            "adafruit/Adafruit Unified Sensor@1.1.15",
            "adafruit/Adafruit MPU6050@2.2.6",
        ),
        declarations=f"Adafruit_MPU6050 {name};",
        setup=f"""if (!{name}.begin(0x68, &Wire)) {{
    Serial.println("CHECK:MOTION_INIT:FAIL");
    return;
  }}
  Serial.println("CHECK:MOTION_INIT:PASS");""",
        loop=f"""sensors_event_t {name}_acceleration, {name}_gyro, {name}_temperature;
  {name}.getEvent(&{name}_acceleration, &{name}_gyro, &{name}_temperature);
  Serial.println("CHECK:MOTION_READ:PASS");""",
        i2c_pins=i2c_pins,
    )


MODULES: dict[str, FirmwareModule] = {
    module.component_id: module
    for module in (
        FirmwareModule("ssd1306-oled", 10, _ssd1306),
        FirmwareModule("dht22", 20, _dht22),
        FirmwareModule("led", 25, _led),
        FirmwareModule("ky-040", 30, _ky040),
        FirmwareModule("mpu6050", 40, _mpu6050),
    )
}


def compose_fragments(hardware: HardwareIR) -> list[FirmwareFragment]:
    if hardware.board.component_id != "esp32-s3-devkit":
        raise ValueError(f"Unsupported firmware board: {hardware.board.component_id}")

    refs = [component.ref for component in hardware.components]
    if len(refs) != len(set(refs)):
        raise ValueError("Hardware IR component refs must be unique")

    unsupported = sorted(
        {component.component_id for component in hardware.components} - MODULES.keys()
    )
    if unsupported:
        raise ValueError(f"Unsupported firmware component(s): {', '.join(unsupported)}")

    components = sorted(
        hardware.components,
        key=lambda component: (MODULES[component.component_id].order, component.ref),
    )
    fragments = [
        MODULES[component.component_id].render(hardware, component) for component in components
    ]

    i2c_buses = {fragment.i2c_pins for fragment in fragments if fragment.i2c_pins is not None}
    if len(i2c_buses) > 1:
        raise ValueError(f"All I2C modules must share one bus; found {sorted(i2c_buses)}")
    return fragments
