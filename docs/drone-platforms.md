# Drone Alpha platform contracts

Only **COUP Quad Alpha** is supported today: PX4 `sihsim_quadx`, with a pinned SIH runtime and MAVSDK scenario runner. A build is not verified until that runtime is available and the scenario has real evidence. Digital verification never proves physical flight.

The following profiles are deliberately represented as product contracts rather than half-implemented integration paths. Adapters may list them, but must expose their `deferred` lifecycle and `unavailable` verification state. They must not offer `build`, `test`, or `deploy` as if the underlying platform were available.

| Profile | Role | Alpha state | What it is not |
| --- | --- | --- | --- |
| `gazebo-harmonic` | Future PX4 camera, sensor, and world regression testing | Deferred; verification unavailable | The Alpha flight gate, a source of physical-flight evidence, or a bundled runtime/world |
| `modalai-voxl` | Future companion-compute target for perception and mission apps | Deferred; verification and deployment unavailable | A deployment target, device bridge, VOXL SDK integration, or a substitute for autopilot verification |

## Promotion gates

Gazebo Harmonic may be promoted only after COUP pins the PX4/Gazebo compatibility matrix and container digest, ships a deterministic headless scenario, records sensor evidence in `verification.json`, and proves that the scenario adds coverage beyond SIH.

ModalAI VOXL may be promoted only after COUP selects a specific device and OS/SDK release, establishes signed local-bridge/device identity, validates a hardware-in-the-loop acceptance suite, and keeps companion-app evidence separate from PX4 flight-controller evidence.

The programmatic source of truth is `hardware_build.drone_platforms`. Future CLI/API/MCP adapters should use it instead of inventing status strings or capability claims.
