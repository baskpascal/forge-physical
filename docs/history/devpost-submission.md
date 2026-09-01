# Historical record: Devpost Submission Copy

> Preserved for provenance of the competition submission. The current product documentation is in the repository root and `docs/`.

## Project

**COUP** — Infrastructure for agents that build hardware.

## Category

Taskmaster (agent autonomously coordinates a multi-step engineering workflow and returns evidence).

## What it does

COUP is the hardware execution layer for coding agents. It accepts a supported low-voltage prototype request through a Streamable HTTP MCP/FastAPI endpoint and returns a Build Room link immediately. A Cloud Run Job then uses Google ADK with Gemini 3.5 Flash to plan the design, validates a structured Hardware IR, generates and compiles ESP32 firmware with PlatformIO, runs a deterministic Wokwi hardware scenario, creates enclosure STL files, and stores state and artifacts in Firestore and Cloud Storage.

## How we built it

- Google ADK + Gemini 3.5 Flash on Vertex AI (`us` inference location)
- Three additional Vertex AI models for prompt-to-spec alignment: `gemini-embedding-001`, `text-embedding-005`, and `text-multilingual-embedding-002`
- Cloud Run API and Cloud Run Job (`us-central1`)
- Firestore event/state store
- Cloud Storage artifact store
- Artifact Registry + Cloud Build
- Secret Manager for Wokwi CI credentials
- GitHub Actions OIDC → Workload Identity Federation → `forge-build` (no JSON key)
- PlatformIO and Wokwi CLI for real firmware and behavioral verification
- Next.js Build Room for live evidence

### Additional Google model evidence

The three additional models perform a real prompt-to-product-spec semantic-alignment check; they
are not decorative model calls. Immutable evidence is stored in build `061bf9dfcf33` and its
`semantic-alignment.json` artifact. Raw vectors are not persisted.

| Model ID | Function | Runtime evidence |
| --- | --- | --- |
| `gemini-embedding-001` | Embed prompt and generated spec for alignment | `runtime_verified`, 128 dimensions, similarity 0.9801, 369 ms |
| `text-embedding-005` | Independent English semantic-alignment measurement | `runtime_verified`, 128 dimensions, similarity 0.8895, 294 ms |
| `text-multilingual-embedding-002` | Independent multilingual alignment measurement | `runtime_verified`, 128 dimensions, similarity 0.9353, 313 ms |

## What makes it agentic

The request starts an asynchronous workflow rather than a chat response. The ProductPlanner uses Gemini and the verified component catalog; deterministic validators gate unsafe or invalid designs; the EngineeringAgent receives real compiler evidence for bounded repairs; and every stage persists an event that the user can inspect while the job runs.

## Challenges and learnings

The hardest part was making evidence honest. A CLI exit code is not enough to claim hardware behavior, so the Wokwi golden path changes a DHT22 from 25°C to 35°C, asserts the alarm GPIO low then high, and requires serial markers. Schema variations from model output are normalized without replacing Gemini with fixtures. Platform limits and external credential failures remain visible instead of becoming green status.

## Hosted project

- API: <https://forge-api-rldj6ghw7q-uc.a.run.app>
- Build Room: <https://forge-web-rldj6ghw7q-uc.a.run.app>
- Build article: <https://forge-web-rldj6ghw7q-uc.a.run.app/build-story>
- Repository: <https://github.com/baskpascal/forge-physical> (public)
- Architecture diagram: <https://github.com/baskpascal/forge-physical/blob/main/docs/architecture.png>

## Testing instructions

Submit: “Create an ESP32 temperature alarm. Use a temperature sensor. Turn the warning LED on when temperature is above 30°C. The design must be testable automatically in Wokwi.” Poll the returned build ID until a terminal state, then inspect agent mode, events, simulation evidence, and artifact links. No judge credential is required for the hosted Build Room or public repository. If capacity is temporarily full, the API returns `429` with a `Retry-After` delay and creates no build.

For clean-machine reproduction, follow the Docker and verification commands in the public
[README](https://github.com/baskpascal/forge-physical#verification). No Google Cloud or Wokwi
credential is required to inspect the hosted evidence and download public artifacts.

For the complete golden production run, open [build `061bf9dfcf33`](https://forge-web-rldj6ghw7q-uc.a.run.app/build/061bf9dfcf33). It completed with Google ADK/Gemini planning, nine deterministic electrical checks, a real PlatformIO `firmware.bin`, Wokwi lint plus 25°C/35°C GPIO and serial assertions, Firestore events, 14 Cloud Storage artifacts, and generated base/lid STL files. Build [`b4381f2ebfbd`](https://forge-web-rldj6ghw7q-uc.a.run.app/build/b4381f2ebfbd) separately preserves the intentional compile-failure → EngineeringAgent repair → successful recompile evidence.

## Known limitations

- The supported catalog is intentionally limited to low-voltage ESP32-S3 prototypes.
- Physical assembly, EMI/EMC and thermals remain `not_verified`; digital evidence never implies a fabricated physical test.
- Wokwi evidence applies to the supported temperature-alarm path; it does not imply arbitrary hardware support.
- The public endpoint is protected by concurrency and per-client admission limits; a busy judge receives an explicit retry response rather than a silently dropped build.

## Eligibility facts to fill before submission

- Project start date: **August 30, 2026** (first repository commit: `e732a86`)
- Submitter type: **confirm individual or team**
- Public demo video URL: **pending recording/upload**
- Build article URL: <https://forge-web-rldj6ghw7q-uc.a.run.app/build-story>
- Social URL with `#AllThingsAgenticHackathon`: **pending publication**
