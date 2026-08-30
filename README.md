# AI agents can already build software. Now they can build physical products.

Forge Physical is agent-native infrastructure for building low-voltage electronic prototypes. A
coding agent calls one remote MCP tool, gets a Build Room URL immediately, and the backend takes over:

```text
Codex / Claude Code / Gemini CLI
                ↓  Streamable HTTP MCP
        Product intent + constraints
                ↓
   Google ADK + Gemini build workflow
                ↓
Hardware IR → electrical checks → firmware → PlatformIO → repair loop
                ↓                         ↓
        Wokwi scenario              parametric STL
                └──────────→ verification report
```

This is not a chatbot, EDA suite, CAD replacement, or simulated landing page. Every green state in the
Build Room comes from backend evidence. Missing credentials and physical tests remain visibly
`unavailable` or `not_verified`.

## The demo

Ask your coding agent:

> Build a small desk environmental monitor with a screen, rotary knob and temperature sensor. Use an ESP32 and USB power.

The verified vertical slice selects an ESP32-S3 DevKitC-1, SSD1306 OLED, DHT22, and KY-040, then:

1. creates a constrained `ProductSpec`;
2. generates the Hardware IR and runs nine deterministic electrical checks;
3. generates Arduino firmware and compiles it with PlatformIO;
4. gives compiler evidence to the ADK EngineeringAgent and retries a bounded repair loop;
5. generates and runs a Wokwi automation scenario when a token exists;
6. exports parametric base/lid STL files with display, knob, and USB openings;
7. emits a verification report that distinguishes digital evidence from physical verification.

The current local smoke test produces a real `firmware.bin`, real STL files, 16+ structured events,
and a completed Build Room. With no Wokwi token, simulation is honestly shown as unavailable.

## Architecture

| Surface | Implementation | Responsibility |
| --- | --- | --- |
| Build Room | Next.js 16, React 19, Three.js | Realtime product canvas, build stages, evidence |
| API + MCP | FastAPI, MCP Python SDK | Async `prototype_*` tools and artifact delivery |
| Agent workflow | Google ADK, Gemini 3.5 Flash | Product planning and evidence-grounded repair proposals |
| Worker | Cloud Run Job-compatible Python process | Validators, PlatformIO, Wokwi, enclosure, report |
| State | Firestore | Build source of truth and realtime event stream |
| Artifacts | Cloud Storage in Cloud; filesystem locally | Firmware, Wokwi config, STL, reports |

The API asks Cloud Run Jobs to execute a build using a `BUILD_ID` environment override. Local
development uses the same `BuildOrchestrator` in a background executor. The MCP request never waits
for the heavy workflow.

## Quickstart

Prerequisites: Node.js 22+, Python 3.11–3.13, and Git. Docker is optional. Backend secrets are not
loaded from `.env`; use ADC and the ephemeral Secret Manager helper described below.

```powershell
npm install

py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e 'services/build-worker[dev]'

# PlatformIO stays isolated from the ADK dependency graph.
py -3.13 -m venv .platformio-venv
.\.platformio-venv\Scripts\python.exe -m pip install platformio==6.1.19
$env:PLATFORMIO_CMD=(Resolve-Path '.\.platformio-venv\Scripts\platformio.exe').Path
```

Run the services in separate terminals:

```powershell
# Backend terminal
. .\.venv\Scripts\Activate.ps1
npm run backend:dev

# Web terminal
npm run dev
```

Open [http://localhost:3000](http://localhost:3000), or prove the backend vertical slice directly:

```powershell
$env:PLATFORMIO_CMD=(Resolve-Path '.\.platformio-venv\Scripts\platformio.exe').Path
npm run smoke
```

The first PlatformIO run downloads the ESP32 toolchain. Later builds reuse its cache.

For Google Cloud access locally, run `gcloud auth application-default login`. When Wokwi is needed,
`.\scripts\with-gcp-secrets.ps1 -Command npm -CommandArgs @('run','smoke')` fetches the token from
Secret Manager only for that child process and never writes it to disk.

## MCP tools

Only four tools are exposed:

- `prototype_start(prompt)` — queues a build and immediately returns `build_id`, `status`, and `build_url`.
- `prototype_update(build_id, change)` — creates a new immutable build version.
- `prototype_status(build_id)` — returns structured state, evidence, and human-readable events.
- `prototype_artifacts(build_id)` — lists available artifacts and the ZIP endpoint.

Connection examples for Codex, Claude Code, and Gemini CLI are in [docs/mcp.md](docs/mcp.md).

## Artifact contract

```text
hardware/
├── product.json
├── hardware.json
├── diagram.json (via simulation/diagram.json)
├── firmware/
│   ├── platformio.ini
│   ├── src/main.cpp
│   └── .pio/.../firmware.bin
├── simulation/
│   ├── diagram.json
│   ├── wokwi.toml
│   └── desk-monitor.scenario.yaml
├── enclosure/
│   ├── base.stl
│   └── lid.stl
└── verification.json
```

`hardware pull <buildId>` downloads the ZIP into the current repository. `hardware open <buildId>`
opens its Build Room.

## Google Cloud deployment

The included [cloudbuild.yaml](cloudbuild.yaml) builds and deploys:

- `forge-api` as a Cloud Run service;
- `forge-worker` as a Cloud Run Job;
- Firestore for build state/events and Cloud Storage for durable artifacts.

The Next.js frontend deploys separately to Vercel. Only public `NEXT_PUBLIC_*` values belong in
Vercel environment variables; they are expected to be visible in the browser bundle.

Production is provisioned reproducibly from [infra/](infra/README.md) with dedicated `forge-api` and
`forge-worker` service accounts and ADC. The Terraform configuration creates an empty Wokwi Secret
Manager secret but never stores a token in state; until a token version is deliberately added, Wokwi
truthfully reports `unavailable_due_to_missing_credentials`.

## Verification

```powershell
npm run lint
npm run build
npm test
npm run backend:test
.\.venv\Scripts\python.exe -m ruff check services/build-worker/src services/build-worker/tests
npm audit --audit-level=high
```

The test suite covers the catalog, Hardware IR, validators, build state machine, MCP surface,
firmware generation/repair helpers, and STL export. The smoke flow uses the actual PlatformIO tool.

## Intentional limits

Forge Physical accepts only supported low-voltage prototypes. It rejects mains/high voltage,
medical, safety-critical, weapons, and high-power requests. The core catalog is deliberately limited
to ESP32-S3, SSD1306, DHT22, KY-040, button, LED, and MPU6050. There is no arbitrary PCB routing,
generic CAD, billing, auth, marketplace, or fake simulation.

Physical assembly, EMI/EMC, and thermals are always `not_verified` until real-world evidence exists.
That honesty is part of the product.
