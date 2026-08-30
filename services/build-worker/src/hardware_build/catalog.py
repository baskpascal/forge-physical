from __future__ import annotations

from .models import ComponentDefinition

CATALOG: dict[str, ComponentDefinition] = {
    "esp32-s3-devkit": ComponentDefinition(
        id="esp32-s3-devkit",
        name="ESP32-S3 DevKitC-1",
        type="board",
        voltage=3.3,
        interfaces=["gpio", "i2c", "spi", "uart", "usb", "power"],
        pins={
            "3V3": "power_3v3", "5V": "power_5v", "GND": "ground",
            "GPIO4": "gpio,adc", "GPIO5": "gpio,adc", "GPIO6": "gpio,pwm",
            "GPIO7": "gpio,pwm", "GPIO8": "gpio,i2c_sda", "GPIO9": "gpio,i2c_scl",
            "GPIO10": "gpio,pwm", "GPIO11": "gpio", "GPIO12": "gpio",
            "GPIO13": "gpio", "GPIO14": "gpio", "GPIO15": "gpio",
        },
        dimensions_mm=(51.0, 25.4, 8.0),
        firmware_libraries=["framework-arduinoespressif32"],
        wokwi_part_id="board-esp32-s3-devkitc-1",
        constraints=["3.3V GPIO only", "USB power limited to low-voltage prototypes"],
    ),
    "ssd1306-oled": ComponentDefinition(
        id="ssd1306-oled", name="SSD1306 OLED 128x64", type="display", voltage=3.3,
        interfaces=["i2c"], pins={"VCC": "power_3v3", "GND": "ground", "SDA": "i2c_sda", "SCL": "i2c_scl"},
        i2c_address="0x3C", dimensions_mm=(27.3, 27.8, 4.3),
        firmware_libraries=["adafruit/Adafruit SSD1306", "adafruit/Adafruit GFX Library"],
        wokwi_part_id="wokwi-ssd1306", constraints=["Default address 0x3C"],
    ),
    "dht22": ComponentDefinition(
        id="dht22", name="DHT22 Temperature & Humidity", type="sensor", voltage=3.3,
        interfaces=["gpio"], pins={"VCC": "power_3v3", "SDA": "gpio", "GND": "ground"},
        dimensions_mm=(15.1, 25.0, 7.7), firmware_libraries=["adafruit/DHT sensor library"],
        wokwi_part_id="wokwi-dht22", constraints=["Requires pull-up on data line"],
    ),
    "ky-040": ComponentDefinition(
        id="ky-040", name="KY-040 Rotary Encoder", type="input", voltage=3.3,
        interfaces=["gpio"], pins={"VCC": "power_3v3", "GND": "ground", "CLK": "gpio", "DT": "gpio", "SW": "gpio"},
        dimensions_mm=(26.0, 19.0, 29.0), firmware_libraries=[],
        wokwi_part_id="wokwi-ky-040", constraints=["Use internal pull-ups"],
    ),
    "push-button": ComponentDefinition(
        id="push-button", name="Momentary Push Button", type="input", voltage=3.3,
        interfaces=["gpio"], pins={"1.l": "gpio", "2.l": "ground"}, dimensions_mm=(12.0, 12.0, 7.0),
        firmware_libraries=[], wokwi_part_id="wokwi-pushbutton", constraints=["Use internal pull-up"],
    ),
    "led": ComponentDefinition(
        id="led", name="Indicator LED", type="output", voltage=3.3,
        interfaces=["gpio"], pins={"A": "gpio", "C": "ground"}, dimensions_mm=(5.0, 5.0, 8.6),
        firmware_libraries=[], wokwi_part_id="wokwi-led", constraints=["Requires current-limiting resistor"],
    ),
    "mpu6050": ComponentDefinition(
        id="mpu6050", name="MPU6050 IMU", type="sensor", voltage=3.3,
        interfaces=["i2c"], pins={"VCC": "power_3v3", "GND": "ground", "SDA": "i2c_sda", "SCL": "i2c_scl"},
        i2c_address="0x68", dimensions_mm=(21.2, 16.4, 3.3), firmware_libraries=["adafruit/Adafruit MPU6050"],
        wokwi_part_id="wokwi-mpu6050", constraints=["Default address 0x68"],
    ),
}


def get_component(component_id: str) -> ComponentDefinition:
    try:
        return CATALOG[component_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported component: {component_id}") from exc


def public_catalog() -> list[dict]:
    return [component.model_dump(mode="json") for component in CATALOG.values()]
