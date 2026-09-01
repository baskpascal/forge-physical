# ADR 0002: COUPD local bridge is an admission boundary, not a remote flight-control path

- Status: Accepted
- Date: 2026-09-01

## Context

Drone Alpha proves software in PX4 simulation. A later physical-hardware bridge
must connect a developer's computer to a supported controller without making a
cloud build, a natural-language prompt, or simulation evidence equivalent to
permission to alter or fly a real vehicle.

## Decision

`coupd` will run locally and starts as a **read-only admission and backup
boundary**. The shared `hardware_build.local_bridge` contract requires all of:

1. an immutable COUP artifact with a supported, pinned PX4/SIH lock;
2. passing generated-app build and passing simulation verification;
3. hashes that prove the PX4 parameter overlay and scenario match the manifest;
4. a locally obtained PX4 device identity (`board_id`, serial number, optional
   hardware UID, and USB/serial transport); and
5. a non-empty, device-bound parameter export recorded before any future change.

The current contract explicitly exposes `physical_deployment: unavailable`.
It does not open serial ports, upload firmware, apply parameters, arm a drone,
or command flight. A future capability must add authenticated local consent,
operator preconditions, an auditable dry run, rollback from the backup, and a
separate physical verification state.

## Consequences

The Cloud API, CLI, SDK and MCP may ask for an admission decision, but none may
use this module as evidence that hardware was deployed or safe to fly. The
device identity comes from the local bridge, never from user text or a cloud
record. Tampered, floating, unbuilt, or simulation-unverified artifacts are
rejected deterministically.
