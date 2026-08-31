# Devpost Submission Copy

## Project

**Coup / Forge Physical** — AI agents can already build software. Now they can build physical products.

## Category

Taskmaster (agent autonomously coordinates a multi-step engineering workflow and returns evidence).

## What it does

Forge accepts a physical-product request through a Streamable HTTP MCP/FastAPI endpoint and returns a Build Room link immediately. A Cloud Run Job then uses Google ADK with Gemini 3.5 Flash to plan a supported low-voltage design, validates a structured Hardware IR, generates and compiles ESP32 firmware with PlatformIO, runs a deterministic Wokwi hardware scenario, creates enclosure STL files, and stores state and artifacts in Firestore and Cloud Storage.

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

## What makes it agentic

The request starts an asynchronous workflow rather than a chat response. The ProductPlanner uses Gemini and the verified component catalog; deterministic validators gate unsafe or invalid designs; the EngineeringAgent receives real compiler evidence for bounded repairs; and every stage persists an event that the user can inspect while the job runs.

## Challenges and learnings

The hardest part was making evidence honest. A CLI exit code is not enough to claim hardware behavior, so the Wokwi golden path changes a DHT22 from 25°C to 35°C, asserts the alarm GPIO low then high, and requires serial markers. Schema variations from model output are normalized without replacing Gemini with fixtures. Platform limits and external credential failures remain visible instead of becoming green status.

## Hosted project

- API: <https://forge-api-rldj6ghw7q-uc.a.run.app>
- Build Room: <https://forge-web-rldj6ghw7q-uc.a.run.app>
- Build article: <https://forge-web-rldj6ghw7q-uc.a.run.app/build-story>
- Repository: <https://github.com/baskpascal/forge-physical> (public)

## Testing instructions

Submit: “Create an ESP32 temperature alarm. Use a temperature sensor. Turn the warning LED on when temperature is above 30°C. The design must be testable automatically in Wokwi.” Poll the returned build ID until a terminal state, then inspect agent mode, events, simulation evidence, and artifact links. No judge credential is required for the hosted Build Room or public repository. If capacity is temporarily full, the API returns `429` with a `Retry-After` delay and creates no build.

For an immediately inspectable production run, open [build `b4381f2ebfbd`](https://forge-web-rldj6ghw7q-uc.a.run.app/build/b4381f2ebfbd). It demonstrates Google ADK planning, the intentional compiler failure, `EngineeringAgent`'s evidence-grounded repair, successful PlatformIO recompilation, Firestore events, Cloud Storage artifacts, and generated STL files. Wokwi correctly remains `unavailable` because the deployed Secret Manager value is not a valid CI token; this is not represented as a successful hardware simulation.

## Eligibility facts to fill before submission

- Project start date: **August 30, 2026** (first repository commit: `e732a86`)
- Submitter type: **confirm individual or team**
- Public demo video URL: **pending recording/upload**
- Build article URL: <https://forge-web-rldj6ghw7q-uc.a.run.app/build-story>
- Social URL with `#AllThingsAgenticHackathon`: **pending publication**
