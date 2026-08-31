# COUP hardware iteration performance

Hardware timing evidence is emitted in the Firestore event stream as `build.metrics`. The
measurements below are production observations, not projections. Phase durations overlap
where work is intentionally parallel, so they must not be summed to derive `total_ms`.

## Production benchmark

Build `16a308a1026d` was submitted to the public production API on 2026-08-31 with an
ESP32-S3 temperature/humidity monitor prompt. The API accepted it as queued in 893 ms and
returned queue position 4. It subsequently produced real Gemini/ADK planning evidence,
three per-model Vertex embedding results, electrical validation, PlatformIO firmware,
real Wokwi CLI simulation, base/lid STL files, Firestore events, and 15 named Cloud Storage
artifacts.

| Phase | Pre-instrumentation reference | Instrumented production build |
|---|---:|---:|
| Request acknowledgment | unavailable | **893 ms** |
| Queue wait | ~142 s (event-derived) | **460,183 ms** |
| Worker startup | unavailable | **178,604 ms** |
| Planning | ~8 s (event-derived) | **11,366 ms** |
| Semantic verification | only model latencies recorded | **591 ms** |
| Electrical validation | unavailable | **217 ms** |
| Firmware generation | unavailable | **110 ms** |
| PlatformIO | ~15 s (event-derived) | **14,034 ms** |
| Repair | no repair event | **0 ms** |
| Wokwi | ~12 s (event-derived) | **10,330 ms** |
| Enclosure | coarse event timestamp only | **10 ms**, parallel branch |
| Artifact upload | ~2 s (event-derived) | **1,595 ms** |
| Total intent-to-complete | ~181 s (event-derived) | **499,657 ms** |

The reference is completed production build `1996231aeded`, the latest comparable build
whose events predate `build.metrics`; second-level event timestamps make those values
approximate. It is not presented as a controlled before/after workload. The instrumented
sample encountered a real backlog of three earlier queued builds and therefore has worse
queue/total time despite a similar ~39.5 s execution pipeline. The production UX still
improved materially: intent was acknowledged in under one second and the Build Room could
show a real queued position instead of returning capacity HTTP 429.

The three embedding calls preserved individual evidence while running with bounded
concurrency:

| Model | Status | Latency | Similarity | Dimensions |
|---|---|---:|---:|---:|
| `gemini-embedding-001` | `runtime_verified` | 202 ms | 0.9779 | 128 |
| `text-embedding-005` | `runtime_verified` | 350 ms | 0.9040 | 128 |
| `text-multilingual-embedding-002` | `runtime_verified` | 204 ms | 0.9411 | 128 |

Wokwi CLI 0.26.1 connected to the real Simulation API and verified `COUP_READY`, normal
temperature, alert temperature, GPIO10 low/high, and `COUP_TEST_PASS`. PlatformIO compiled
the ESP32-S3 firmware without repair. Reuse was not claimed for this clean build.

## Operational finding

The first benchmark request exposed a missing Firestore composite index in the FIFO query.
Build intent had already been persisted, but admission returned HTTP 500 before the fix.
The queue now uses Firestore's automatic equality index and sorts the bounded queued result
in memory, preserving deterministic FIFO without an asynchronous index migration. The
successful request above validates the production repair.

Collect multiple identical prompts under controlled queue depth to establish hardware p50
and p95. One real sample is evidence, but it is not a percentile distribution.
