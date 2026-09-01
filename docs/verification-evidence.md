# Verification Evidence Index

Every production claim below must remain tied to a reproducible check or immutable build artifact.

## Latest production evidence run

Build [`061bf9dfcf33`](https://forge-web-rldj6ghw7q-uc.a.run.app/build/061bf9dfcf33) was started through the public API on 2026-08-31 and reached terminal status `completed`. The run recorded 17 Firestore events and produced 14 downloadable Cloud Storage artifacts.

- Google ADK planned the product with `gemini-3.5-flash` on Vertex AI.
- `gemini-embedding-001`, `text-embedding-005`, and `text-multilingual-embedding-002` each returned runtime-verified semantic-alignment evidence.
- All nine deterministic electrical checks passed.
- PlatformIO compiled a real `firmware.bin` and retained compiler output.
- Wokwi CLI lint returned 0; the scenario asserted GPIO 10 low at 25°C and high at 35°C, matched `COUP_READY`, `TEMP_NORMAL`, `TEMP_ALERT`, and `COUP_TEST_PASS`, and returned 0 with no missing markers.
- Parametric base and lid STL files and the complete Wokwi evidence bundle were published.
- The COUP Build Room was checked on desktop and at 390 px without console errors, error overlays, or horizontal overflow.
- Separate build [`b4381f2ebfbd`](https://forge-web-rldj6ghw7q-uc.a.run.app/build/b4381f2ebfbd) preserves the controlled compiler failure, `EngineeringAgent` repair, and successful PlatformIO recompile proof.

| Claim | Source / test | Production evidence | Limitation |
| --- | --- | --- | --- |
| Gemini plans and repairs the product | `hardware_build/agent.py`, agent tests | Golden build `agent_mode` and `plan.completed`; repair build `firmware.compile.failed`, `agent.repair.started`, and successful recompile | A schema-invalid response is recorded as fallback, never hidden |
| Three additional Google models verify intent | `semantic_alignment.py`, semantic-alignment test | Per-model dimension, similarity and latency in `semantic-alignment.json` | Raw embedding vectors are never persisted |
| Async API → worker | `service.py`, service tests | Public `POST /api/builds`; Cloud Run Job execution name | Cold start may delay worker start |
| Firestore state/event stream | `storage.py`, integration check | Build document plus ordered events | Firestore is not a hardware measurement |
| ESP32 firmware compiles | `firmware.py`, firmware tests | PlatformIO output, `firmware.bin`, `firmware.elf` | Compile success does not prove physical assembly |
| Wokwi validates behavior | `simulation.py`, simulation tests | Build `061bf9dfcf33`: lint/scenario exit 0, 25°C/35°C GPIO assertions, four required serial markers | Evidence covers the supported temperature-alarm path |
| Artifacts are durable | `artifacts.py`, API tests | `gs://supple-voyage-507119-v0-forge-artifacts/{build_id}/` | Access is mediated by the API |
| Enclosure is generated | `enclosure.py`, enclosure tests | Downloadable base/lid STL | Fit is digitally generated, not physically measured |
| Keyless deployment | Terraform + GitHub workflow | WIF-restricted deploy and Cloud Build run | Restricted to `baskpascal/forge-physical` |
| Secret handling | `settings.py`, `security.py` tests | Secret Manager reference on worker | Secret values must never be attached to evidence |
| Failure handling | orchestrator/service tests | Failed/unavailable simulations remain distinct from `not_run` and `not_verified` | Cloud platform interruptions are visible separately |

## Reproduce a build

1. Open the public Build Room: <https://forge-web-rldj6ghw7q-uc.a.run.app>.
2. Submit the ESP32 temperature-alarm prompt through the public API or MCP `prototype_start`.
3. Watch `queued → planning → building/testing → simulation → verification` events.
4. Confirm Gemini 3.5 Flash agent metadata, PlatformIO exit 0, Wokwi lint/scenario behavior, and the final result.
5. Download the firmware, Wokwi project, serial log, result JSON, and STL artifacts.

Production API: <https://forge-api-rldj6ghw7q-uc.a.run.app>

Hosted Build Room: <https://forge-web-rldj6ghw7q-uc.a.run.app>

Architecture diagram: [architecture.png](architecture.png)
