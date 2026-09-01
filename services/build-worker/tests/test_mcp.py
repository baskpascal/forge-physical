from hardware_build.mcp_server import mcp


def test_mcp_registers_legacy_prototype_and_thin_drone_alpha_tools():
    names = set(mcp._tool_manager._tools)
    assert names == {
        "prototype_start",
        "prototype_update",
        "prototype_status",
        "prototype_artifacts",
        "drone_create",
        "drone_change",
        "drone_build",
        "drone_test",
        "drone_status",
        "drone_artifacts",
    }
