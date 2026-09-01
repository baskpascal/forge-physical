"""Application service for server-owned COUP Drone Alpha projects.

The CLI, HTTP API, and MCP adapter all use this module.  It deliberately does
not reimplement intent compilation, versioning, or SITL execution; those stay
in :mod:`hardware_build.drone`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .drone import (
    DroneScopeError,
    build_version,
    create_version,
    init_project,
    load_state,
    test_version,
)
from .settings import Settings, get_settings

_PROJECT_NAME = re.compile(r"[a-z][a-z0-9-]{0,62}")


def _root(project: str, settings: Settings | None = None) -> Path:
    if not _PROJECT_NAME.fullmatch(project):
        raise DroneScopeError("Project must be a lowercase slug (letters, digits, and hyphens).")
    root = (settings or get_settings()).drone_project_root.resolve()
    candidate = (root / project).resolve()
    if not candidate.is_relative_to(root):  # Defensive in case the validation changes.
        raise DroneScopeError("Invalid drone project path.")
    return candidate


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return provenance without leaking server filesystem paths."""
    return {
        key: value
        for key, value in record.items()
        if key in {"id", "parent", "intent", "spec", "manifest", "build", "test"}
    }


def create_drone(project: str, intent: str, settings: Settings | None = None) -> dict[str, Any]:
    root = _root(project, settings)
    if not root.exists():
        init_project(root)
    return {"project": project, "build": _public_record(create_version(root, intent))}


def change_drone(project: str, build_id: str, change: str, settings: Settings | None = None) -> dict[str, Any]:
    root = _root(project, settings)
    state = load_state(root)
    if not any(item["id"] == build_id for item in state["builds"]):
        raise DroneScopeError("Build not found.")
    # The core always derives the next immutable revision from the latest build.
    if state["builds"][-1]["id"] != build_id:
        raise DroneScopeError("Changes can only be made from the latest build version.")
    return {"project": project, "build": _public_record(create_version(root, change))}


def build_drone(project: str, build_id: str, settings: Settings | None = None) -> dict[str, Any]:
    return {"project": project, "build": _public_record(build_version(_root(project, settings), build_id))}


def test_drone(project: str, build_id: str, settings: Settings | None = None) -> dict[str, Any]:
    # The launcher is server configuration only.  An API client must not be able
    # to cause arbitrary shell execution through a test request.
    return {"project": project, "build": _public_record(test_version(_root(project, settings), build_id))}


def drone_status(project: str, build_id: str, settings: Settings | None = None) -> dict[str, Any]:
    state = load_state(_root(project, settings))
    record = next((item for item in state["builds"] if item["id"] == build_id), None)
    if record is None:
        raise DroneScopeError("Build not found.")
    return {"project": project, "build": _public_record(record)}


def drone_artifacts(project: str, build_id: str, settings: Settings | None = None) -> dict[str, Any]:
    record = drone_status(project, build_id, settings)["build"]
    # Names are stable build-artifact paths relative to coup-drone; downloads can
    # later be served through the existing artifact-storage abstraction.
    paths = [
        "coup.lock",
        "drone/spec.yaml",
        "drone/manifest.json",
        "autopilot/overlay/coup_quad_alpha.params",
        "app/mission.py",
        "tests/scenarios/conservative_inspection.yaml",
        "build/result.json",
        "verification/report.json",
    ]
    return {"project": project, "build_id": record["id"], "artifacts": paths, "manifest": record["manifest"]}
