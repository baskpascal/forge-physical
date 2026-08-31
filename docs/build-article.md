# From coding agents to verified physical prototypes

> This article was created for the purpose of entering the All Things Agentic Hackathon.

Software agents can edit code, run tests and deploy services because their work has machine-readable feedback. Physical-product development usually breaks that loop: component selection, wiring, firmware, simulation and mechanical artifacts live in separate tools, and a plausible answer can be mistaken for a verified one.

Forge Physical closes one narrow but real loop. A user asks for a low-voltage prototype. A Cloud Run API creates an immutable build record and starts a Cloud Run Job. Google ADK and Gemini 3.5 Flash translate the request into a constrained product specification. Deterministic code—not the model—checks the supported catalog, voltage, pins, buses and required connections. The worker generates Arduino firmware and asks PlatformIO for an actual ESP32 binary.

The most important design choice is evidence-first status. Forge does not mark Wokwi green because a token exists or a process exits zero. For the temperature-alarm golden path, Wokwi CI lints the generated diagram, changes the DHT22 from 25°C to 35°C, verifies the ESP32 alarm pin is low then high, and waits for unambiguous serial markers. The build result includes the serial log and machine-readable validation metadata. A failure becomes `needs_review`, not a fabricated success.

Firestore is the source of truth for the build and its event stream. Cloud Storage holds firmware, Wokwi files, results and enclosure STL artifacts. Secret Manager injects the Wokwi credential only into the worker, while GitHub Actions uses OIDC and Workload Identity Federation rather than a service-account key.

The result is not a claim that virtual validation replaces physical testing. Assembly, EMI/EMC and thermals remain explicitly `not_verified`. The useful leap is that an agent can now own a complete, inspectable digital prototype loop—request, plan, generate, compile, simulate, validate and publish—on production cloud infrastructure.

Forge also uses three additional Google embedding models—`gemini-embedding-001`,
`text-embedding-005`, and `text-multilingual-embedding-002`—to compare the original request with
the generated product specification. The build stores similarity, dimension and latency evidence,
but never persists the raw vectors.

Hosted Build Room: <https://forge-web-rldj6ghw7q-uc.a.run.app>. Add the public repository and demo
video links immediately before publishing.
