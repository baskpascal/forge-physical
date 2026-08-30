from hardware_build.catalog import CATALOG
from hardware_build.planning import (
    deterministic_hardware_ir,
    deterministic_product_spec,
    scope_violation,
)
from hardware_build.validators import validate_hardware


def test_catalog_is_restricted_and_complete():
    assert set(CATALOG) == {"esp32-s3-devkit", "ssd1306-oled", "dht22", "ky-040", "push-button", "led", "mpu6050"}
    assert all(component.wokwi_part_id for component in CATALOG.values())


def test_demo_hardware_ir_passes_deterministic_validation():
    spec = deterministic_product_spec("Build a desk monitor with OLED, rotary knob, temperature sensor and USB power")
    hardware = deterministic_hardware_ir(spec)
    result = validate_hardware(hardware)
    assert result.passed, result.model_dump()
    assert len(hardware.components) == 3


def test_gpio_conflict_is_rejected():
    hardware = deterministic_hardware_ir(deterministic_product_spec("Build a desk monitor with screen and knob"))
    hardware.connections[2].from_.pin = "GPIO8"
    result = validate_hardware(hardware)
    assert not result.passed
    assert any(issue.code == "gpio_conflict" for issue in result.issues)


def test_unsafe_scope_is_rejected():
    assert scope_violation("Build a 230V mains outlet controller") == "mains electricity"
    assert deterministic_product_spec("Build a medical diagnostic device").supported is False
