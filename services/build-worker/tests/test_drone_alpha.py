from pathlib import Path

import pytest

from hardware_build.drone import (
    DroneScopeError,
    build_version,
    compile_intent,
    create_version,
    init_project,
    load_state,
)
from hardware_build.drone import test_version as run_test_version


def test_create_build_and_iteration_are_immutable(tmp_path: Path) -> None:
    init_project(tmp_path)
    first = create_version(tmp_path, "make me an easy-to-fly inspection drone for my farm")
    second = create_version(tmp_path, "make it more responsive")

    assert first["id"] == "0001"
    assert second["id"] == "0002"
    assert second["parent"] == "0001"
    assert first["spec"]["responsiveness"] == "low"
    assert second["spec"]["responsiveness"] == "high"
    assert Path(first["root"]).joinpath("tests/scenarios/conservative_inspection.yaml").exists()
    assert load_state(tmp_path)["builds"][0]["manifest"]["overlay_hash"] != load_state(tmp_path)["builds"][1]["manifest"]["overlay_hash"]


def test_scope_and_parameter_boundaries_are_constrained() -> None:
    with pytest.raises(DroneScopeError):
        compile_intent("make a drone with an explosive payload release")
    with pytest.raises(DroneScopeError):
        compile_intent("make a coffee machine")


def test_build_generates_real_compiled_application_and_honest_unavailable_report(tmp_path: Path) -> None:
    init_project(tmp_path)
    build = create_version(tmp_path, "make a stable outdoor inspection drone")
    built = build_version(tmp_path, build["id"])
    tested = run_test_version(tmp_path, build["id"])
    root = Path(built["root"])

    assert built["build"] == "passed"
    assert root.joinpath("build/mission.pyc").exists()
    assert tested["test"] == "unavailable"
    assert "No pinned PX4 SITL launcher" in root.joinpath("verification/report.json").read_text(encoding="utf-8")
