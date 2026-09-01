# ADR 0001: PX4, MAVSDK, and SIH for COUP Drone Alpha

## Status

Accepted — 2026-09-01.

## Context

COUP Drone Alpha must turn constrained civilian drone intent into a reproducible software project and real simulation evidence. It must not generate a flight controller from scratch or accept arbitrary flight-controller parameters from a language model.

## Decision

COUP supports one profile: **COUP Quad Alpha**, a PX4 `sihsim_quadx` quadrotor.

- **Autopilot:** PX4 `v1.17.0`, consumed as a pinned upstream runtime rather than copied into generated projects.
- **Control and test API:** MAVSDK-Python `3.17.2`; MAVLink remains an internal transport protocol.
- **Required simulation gate:** PX4 SIH/SITL headless, started by the runner in Linux/WSL or CI.
- **Optional later simulation:** Gazebo Harmonic for camera, world, and sensor tests only.
- **First physical target:** Pixhawk Standard FMUv6X-class controller. Physical deployment is unavailable in Alpha.
- **Agent boundary:** CLI and core compiler own domain logic. MCP and a future HTTP API are thin adapters.

The compiler accepts only named DroneSpec presets with bounded PX4 parameter overlays. A successful simulator run is `verified_simulated`; physical flight remains `not_verified`.

## Consequences

Generated projects pin PX4, MAVSDK, schema, compiler, and scenario versions in `coup.lock`. They contain an overlay, generated MAVSDK companion application, scenario runner, provenance hashes, and verification report — not a copied PX4 source tree.

ArduPilot was rejected for Alpha despite strong SITL maturity because its GPLv3 licensing is a worse fit for a product that may distribute custom firmware overlays. Direct MAVLink/pymavlink is retained as an internal escape hatch, not the user-facing API. ROS 2 and ModalAI/VOXL are deferred because they add integration surface without improving the first headless verification loop. The executable deferred-profile contract and promotion criteria are in [Drone Alpha platform contracts](../drone-platforms.md).

## Evidence

- [PX4 simulation overview](https://docs.px4.io/main/en/simulation/)
- [PX4 prebuilt SITL packages](https://docs.px4.io/main/en/simulation/px4_sitl_prebuilt_packages)
- [PX4 MAVSDK integration testing](https://docs.px4.io/main/en/test_and_ci/integration_testing_mavsdk)
- [MAVSDK-Python releases](https://github.com/mavlink/MAVSDK-Python/releases)
- [ArduPilot GPLv3 licensing](https://ardupilot.org/dev/docs/license-gplv3.html)
