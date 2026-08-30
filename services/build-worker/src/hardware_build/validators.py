from __future__ import annotations

from collections import Counter, defaultdict

from .catalog import get_component
from .models import HardwareIR, ValidationIssue, ValidationResult


def validate_hardware(hardware: HardwareIR) -> ValidationResult:
    checks = {
        "supported_components": True,
        "voltage_compatible": True,
        "pins_exist": True,
        "pin_capabilities": True,
        "no_duplicate_connections": True,
        "no_gpio_conflicts": True,
        "no_i2c_address_conflicts": True,
        "required_connections": True,
        "power_requirements": True,
    }
    issues: list[ValidationIssue] = []
    instances = {hardware.board.ref: hardware.board, **{item.ref: item for item in hardware.components}}
    definitions = {}
    for ref, instance in instances.items():
        try:
            definitions[ref] = get_component(instance.component_id)
        except ValueError as exc:
            checks["supported_components"] = False
            issues.append(ValidationIssue(code="unsupported_component", message=str(exc), path=ref))

    all_connections = hardware.connections + hardware.power
    seen: Counter[tuple[str, str, str, str]] = Counter()
    board_gpio_usage: defaultdict[str, list[str]] = defaultdict(list)
    connected_targets: set[tuple[str, str]] = set()

    for index, connection in enumerate(all_connections):
        path = f"connections[{index}]"
        source = connection.from_
        target = connection.to
        key = (source.ref, source.pin, target.ref, target.pin)
        seen[key] += 1
        connected_targets.add((target.ref, target.pin))
        for endpoint_name, endpoint in (("from", source), ("to", target)):
            definition = definitions.get(endpoint.ref)
            if not definition or endpoint.pin not in definition.pins:
                checks["pins_exist"] = False
                issues.append(ValidationIssue(code="unknown_pin", message=f"{endpoint.ref}.{endpoint.pin} does not exist", path=f"{path}.{endpoint_name}"))
        source_def = definitions.get(source.ref)
        target_def = definitions.get(target.ref)
        if source_def and target_def and connection.interface == "power":
            if source.pin == "3V3" and target_def.voltage > 3.3:
                checks["voltage_compatible"] = False
                issues.append(ValidationIssue(code="voltage_mismatch", message=f"{target.ref} requires {target_def.voltage}V", path=path))
        if source.ref == hardware.board.ref and source.pin.startswith("GPIO"):
            board_gpio_usage[source.pin].append(f"{target.ref}.{target.pin}")
            capability = source_def.pins.get(source.pin, "") if source_def else ""
            required = "i2c_sda" if target.pin == "SDA" and connection.interface == "i2c" else "i2c_scl" if target.pin == "SCL" and connection.interface == "i2c" else "gpio"
            if required not in capability:
                checks["pin_capabilities"] = False
                issues.append(ValidationIssue(code="pin_capability", message=f"{source.pin} cannot provide {required}", path=path))

    duplicates = [key for key, count in seen.items() if count > 1]
    if duplicates:
        checks["no_duplicate_connections"] = False
        issues.extend(ValidationIssue(code="duplicate_connection", message="Duplicate connection", path="connections") for _ in duplicates)

    conflicts = {pin: targets for pin, targets in board_gpio_usage.items() if len(targets) > 1}
    if conflicts:
        checks["no_gpio_conflicts"] = False
        for pin, targets in conflicts.items():
            issues.append(ValidationIssue(code="gpio_conflict", message=f"{pin} is assigned to {', '.join(targets)}", path=f"board.{pin}"))

    addresses: defaultdict[str, list[str]] = defaultdict(list)
    for ref, definition in definitions.items():
        if definition.i2c_address:
            addresses[definition.i2c_address].append(ref)
    for address, refs in addresses.items():
        if len(refs) > 1:
            checks["no_i2c_address_conflicts"] = False
            issues.append(ValidationIssue(code="i2c_address_conflict", message=f"{address} used by {', '.join(refs)}", path="components"))

    for ref, definition in definitions.items():
        if ref == hardware.board.ref:
            continue
        required = {pin for pin, function in definition.pins.items() if function in {"power_3v3", "ground"}}
        missing = [pin for pin in required if (ref, pin) not in connected_targets]
        if missing:
            checks["required_connections"] = False
            checks["power_requirements"] = False
            issues.append(ValidationIssue(code="missing_required_connection", message=f"{ref} is missing {', '.join(missing)}", path=ref))

    return ValidationResult(passed=all(checks.values()), checks=checks, issues=issues)
