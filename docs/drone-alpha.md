# COUP Drone Alpha

Drone Alpha supports one constrained profile: **COUP Quad Alpha**, a PX4 `sihsim_quadx` inspection quadrotor. It compiles plain-language intent into a bounded DroneSpec, a PX4 parameter overlay, a generated MAVSDK companion module, a scenario contract, and hashes that tie every artifact to an immutable build.

## Local flow

```powershell
coup init .\scout
coup --project .\scout create "make me an easy-to-fly inspection drone for my farm"
coup --project .\scout build
coup --project .\scout test --launcher '<pinned PX4 v1.17.0 SIH launcher>'
coup --project .\scout change "make it more responsive"
```

`coup test` intentionally returns `UNAVAILABLE` when it has no explicitly pinned PX4 SIH runtime. It never substitutes a floating Docker `latest` tag and never treats simulation as physical-flight evidence.

The launcher must expose MAVSDK UDP on port `14540`; it can be supplied with `--launcher` or `COUP_PX4_SITL_COMMAND`. Install the real test dependency with:

```powershell
.\.venv\Scripts\python.exe -m pip install -e 'services/build-worker[drone]'
```

When COUP itself runs outside Docker (for example on Windows), execute MAVSDK in the simulator network namespace. The checked-in smoke runner is suitable for a local evidence run:

```powershell
coup --project .\scout test --launcher 'docker run --rm --name coup-px4-run coup-px4-sih:v1.17.0' --scenario-command 'docker run --rm --network container:coup-px4-run -v D:\Projects\Coup\docker\px4-sih:/work python:3.13-slim bash -lc "pip install --quiet mavsdk==3.17.2 && python /work/smoke.py"'
```

See [ADR 0001](adr/0001-drone-alpha-px4-mavsdk-sih.md) for the architectural decision and [platform contracts](drone-platforms.md) for Gazebo/VOXL's explicit deferred status.
