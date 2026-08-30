from hardware_build.mcp_server import mcp


def test_mcp_registers_only_the_four_agent_native_tools():
    names = set(mcp._tool_manager._tools)
    assert names == {
        "prototype_start",
        "prototype_update",
        "prototype_status",
        "prototype_artifacts",
    }
