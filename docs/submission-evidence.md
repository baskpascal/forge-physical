# Submission Evidence Index

Every production claim below must remain tied to a reproducible check or immutable build artifact.

| Claim | Source / test | Production evidence | Limitation |
| --- | --- | --- | --- |
| Gemini plans the product | `hardware_build/agent.py`, agent tests | Build `agent_mode` and `plan.completed` event | A schema-invalid response is recorded as fallback, never hidden |
| Three additional Google models verify intent | `semantic_alignment.py`, semantic-alignment test | Per-model dimension, similarity and latency in `semantic-alignment.json` | Raw embedding vectors are never persisted |
| Async API → worker | `service.py`, service tests | Public `POST /api/builds`; Cloud Run Job execution name | Cold start may delay worker start |
| Firestore state/event stream | `storage.py`, integration check | Build document plus ordered events | Firestore is not a hardware measurement |
| ESP32 firmware compiles | `firmware.py`, firmware tests | PlatformIO output, `firmware.bin`, `firmware.elf` | Compile success does not prove physical assembly |
| Wokwi validates behavior | `simulation.py`, simulation tests | CLI lint, 25°C/35°C scenario, GPIO assertions, serial log | Requires a valid Wokwi CI token |
| Artifacts are durable | `artifacts.py`, API tests | `gs://supple-voyage-507119-v0-forge-artifacts/{build_id}/` | Access is mediated by the API |
| Enclosure is generated | `enclosure.py`, enclosure tests | Downloadable base/lid STL | Fit is digitally generated, not physically measured |
| Keyless deployment | Terraform + GitHub workflow | WIF-restricted deploy and Cloud Build run | Restricted to `baskpascal/forge-physical` |
| Secret handling | `settings.py`, `security.py` tests | Secret Manager reference on worker | Secret values must never be attached to evidence |
| Failure handling | orchestrator/service tests | Failed simulation ends `needs_review` | Cloud platform interruptions are visible separately |

## Judge quick path

1. Open the public Build Room: <https://forge-web-rldj6ghw7q-uc.a.run.app>.
2. Submit the ESP32 temperature-alarm prompt through the public API or MCP `prototype_start`.
3. Watch `queued → planning → building/testing → simulation → verification` events.
4. Confirm Gemini 3.5 Flash agent metadata, PlatformIO exit 0, Wokwi lint/scenario behavior, and the final result.
5. Download the firmware, Wokwi project, serial log, result JSON, and STL artifacts.

Production API: <https://forge-api-rldj6ghw7q-uc.a.run.app>

Hosted Build Room: <https://forge-web-rldj6ghw7q-uc.a.run.app>

Architecture diagram: [architecture.png](architecture.png)
