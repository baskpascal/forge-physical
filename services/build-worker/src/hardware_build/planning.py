from __future__ import annotations

import re

from .models import ComponentInstance, Connection, Endpoint, HardwareIR, ProductSpec

UNSUPPORTED_PATTERNS = {
    "mains electricity": r"\b(mains|110v|120v|220v|230v|240v|ac outlet)\b",
    "medical device": r"\b(medical|pacemaker|insulin|diagnos)\b",
    "weapon": r"\b(weapon|gun|explosive|detonator)\b",
    "safety-critical system": r"\b(brake controller|life support|airbag)\b",
    "high-power system": r"\b(high[- ]power|kilowatt|motor drive)\b",
}
MOTION_UPDATE_TERMS = (
    "motion",
    "movement",
    "orientation",
    "imu",
    "accelerometer",
    "gyroscope",
    "mpu6050",
)
_MOTION_UPDATE_TARGETS = (
    r"motion sensing",
    r"movement sensing",
    r"orientation sensing",
    r"(?:an? )?imu(?: sensor)?",
    r"(?:an? )?mpu[ -]?6050(?: imu| motion sensor| sensor)?",
    r"(?:an? )?accelerometer(?: and (?:a )?gyroscope)?",
    r"(?:a )?gyroscope(?: and (?:an? )?accelerometer)?",
)
_MOTION_UPDATE_PATTERN = re.compile(
    rf"(?:please )?(?:add|include|enable|integrate) "
    rf"(?:{'|'.join(_MOTION_UPDATE_TARGETS)})"
    rf"(?: support| capability)?[.!]?",
    flags=re.IGNORECASE,
)


def scope_violation(prompt: str) -> str | None:
    lowered = prompt.lower()
    for reason, pattern in UNSUPPORTED_PATTERNS.items():
        if re.search(pattern, lowered):
            return reason
    return None


def supported_update_change(change: str) -> bool:
    """Return whether an update belongs to the one verified iterative-design slice."""
    normalized = " ".join(change.strip().split())
    return scope_violation(normalized) is None and _MOTION_UPDATE_PATTERN.fullmatch(normalized) is not None


def product_has_motion_sensing(spec: ProductSpec | None, prompt: str) -> bool:
    """Detect the already-applied feature from persisted state or a positive product request."""
    if spec and "motion sensing" in spec.features:
        return True
    lowered = " ".join(prompt.lower().split())
    if re.search(r"\b(?:without|remove|disable|exclude|no)\b[^.\n]{0,40}\b(?:motion|imu|mpu[ -]?6050|accelerometer|gyroscope)\b", lowered):
        return False
    return any(term in lowered for term in MOTION_UPDATE_TERMS)


def deterministic_product_spec(prompt: str) -> ProductSpec:
    violation = scope_violation(prompt)
    if violation:
        return ProductSpec(
            intent=prompt, description="Request is outside the supported low-voltage prototype scope.",
            features=[], constraints=["Low-voltage electronic prototypes only"], supported=False,
            unsupported_reason=violation,
        )
    lowered = prompt.lower()
    features = ["temperature and humidity sensing"]
    if any(word in lowered for word in ("screen", "display", "oled")):
        features.append("OLED status display")
    if any(word in lowered for word in ("rotary", "knob", "encoder")):
        features.append("rotary input")
    if any(word in lowered for word in MOTION_UPDATE_TERMS):
        features.append("motion sensing")
    power = "battery" if "battery" in lowered else "usb"
    return ProductSpec(
        intent=prompt,
        description="A compact desk device that measures the environment and presents live readings.",
        features=features,
        power=power,
        constraints=["ESP32-S3 DevKit", "3.3V logic", "low-voltage prototyping", "supported catalog only"],
    )


def deterministic_hardware_ir(spec: ProductSpec) -> HardwareIR:
    component_ids = ["ssd1306-oled", "dht22", "ky-040"]
    components = [
        ComponentInstance(ref="display", component_id=component_ids[0], label="OLED display"),
        ComponentInstance(ref="sensor", component_id=component_ids[1], label="Temperature sensor"),
        ComponentInstance(ref="encoder", component_id=component_ids[2], label="Rotary knob"),
    ]
    has_motion_sensing = "motion sensing" in spec.features
    if has_motion_sensing:
        components.append(ComponentInstance(ref="motion", component_id="mpu6050", label="Motion sensor"))
    def link(source_ref: str, source_pin: str, target_ref: str, target_pin: str, interface: str, reason: str) -> Connection:
        return Connection(**{"from": Endpoint(ref=source_ref, pin=source_pin), "to": Endpoint(ref=target_ref, pin=target_pin), "interface": interface, "reason": reason})
    connections = [
        link("board", "GPIO8", "display", "SDA", "i2c", "OLED I2C data"),
        link("board", "GPIO9", "display", "SCL", "i2c", "OLED I2C clock"),
        link("board", "GPIO4", "sensor", "SDA", "gpio", "DHT22 data"),
        link("board", "GPIO5", "encoder", "CLK", "gpio", "Encoder clock"),
        link("board", "GPIO6", "encoder", "DT", "gpio", "Encoder direction"),
        link("board", "GPIO7", "encoder", "SW", "gpio", "Encoder switch"),
    ]
    if has_motion_sensing:
        connections.extend([
            link("board", "GPIO8", "motion", "SDA", "i2c", "Shared I2C data for motion sensor"),
            link("board", "GPIO9", "motion", "SCL", "i2c", "Shared I2C clock for motion sensor"),
        ])
    power = []
    powered_refs = ["display", "sensor", "encoder"]
    if has_motion_sensing:
        powered_refs.append("motion")
    for ref in powered_refs:
        power.append(link("board", "3V3", ref, "VCC", "power", f"3.3V supply for {ref}"))
        power.append(link("board", "GND", ref, "GND", "power", f"Common ground for {ref}"))
    return HardwareIR(
        board=ComponentInstance(ref="board", component_id="esp32-s3-devkit", label="ESP32-S3 DevKitC-1"),
        components=components, connections=connections, power=power,
        constraints=spec.constraints,
    )
