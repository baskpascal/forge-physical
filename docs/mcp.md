# Connect a coding agent

The production endpoint is Streamable HTTP at `https://YOUR_API_HOST/mcp`. The call to
`prototype_start` returns immediately; the Cloud Run Job continues the build.

## Codex

```toml
[mcp_servers.forge_physical]
url = "https://YOUR_API_HOST/mcp"
```

## Claude Code

```bash
claude mcp add --transport http forge-physical https://YOUR_API_HOST/mcp
```

## Gemini CLI

```json
{
  "mcpServers": {
    "forge-physical": {
      "httpUrl": "https://YOUR_API_HOST/mcp"
    }
  }
}
```

Then ask the coding agent:

> Build a small desk environmental monitor with a screen, rotary knob and temperature sensor. Use an ESP32 and USB power.

The agent should call `prototype_start`, return the Build Room URL, and use
`prototype_status` or `prototype_artifacts` only when structured follow-up data is needed.
