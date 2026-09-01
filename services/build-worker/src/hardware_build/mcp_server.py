from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .drone_service import (
    build_drone,
    change_drone,
    create_drone,
    drone_artifacts,
    drone_status,
    test_drone,
)
from .service import artifacts_payload, create_build, status_payload, update_build

mcp = FastMCP(
    "Forge Physical",
    instructions="Start and inspect real low-voltage hardware prototype builds. Builds continue asynchronously in the Build Room.",
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
)


@mcp.tool(name="prototype_start", structured_output=True)
def prototype_start(prompt: str) -> dict[str, Any]:
    """Start a supported low-voltage hardware prototype and return immediately with its Build Room URL."""
    return create_build(prompt).model_dump(mode="json")


@mcp.tool(name="prototype_update", structured_output=True)
def prototype_update(build_id: str, change: str) -> dict[str, Any]:
    """Create a new build version that applies a requested product change."""
    return update_build(build_id, change).model_dump(mode="json")


@mcp.tool(name="prototype_status", structured_output=True)
def prototype_status(build_id: str) -> dict[str, Any]:
    """Return structured build stage, verification evidence and human-readable events."""
    return status_payload(build_id)


@mcp.tool(name="prototype_artifacts", structured_output=True)
def prototype_artifacts(build_id: str) -> dict[str, Any]:
    """List currently available product, hardware, firmware, simulation, enclosure and verification artifacts."""
    return artifacts_payload(build_id)


@mcp.tool(name="drone_create", structured_output=True)
def drone_create(project: str, intent: str) -> dict[str, Any]:
    """Create a constrained COUP Quad Alpha project from benign civilian drone intent."""
    return create_drone(project, intent)


@mcp.tool(name="drone_change", structured_output=True)
def drone_change(project: str, build_id: str, change: str) -> dict[str, Any]:
    """Create the next immutable Drone Alpha build from the latest version."""
    return change_drone(project, build_id, change)


@mcp.tool(name="drone_build", structured_output=True)
def drone_build(project: str, build_id: str) -> dict[str, Any]:
    """Build the generated Drone Alpha application artifact."""
    return build_drone(project, build_id)


@mcp.tool(name="drone_test", structured_output=True)
def drone_test(project: str, build_id: str) -> dict[str, Any]:
    """Run the configured pinned PX4 SIH validation; never claims physical flight."""
    return test_drone(project, build_id)


@mcp.tool(name="drone_status", structured_output=True)
def drone_status_tool(project: str, build_id: str) -> dict[str, Any]:
    """Return DroneSpec, immutable-version, build, and validation state."""
    return drone_status(project, build_id)


@mcp.tool(name="drone_artifacts", structured_output=True)
def drone_artifacts_tool(project: str, build_id: str) -> dict[str, Any]:
    """List provenance-bearing Drone Alpha artifacts for one immutable build."""
    return drone_artifacts(project, build_id)
