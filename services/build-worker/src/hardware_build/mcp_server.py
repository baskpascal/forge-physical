from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

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
