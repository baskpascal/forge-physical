# Historical record: COUP — All Things Agentic demo checklist

> Preserved as the submitted-demo record. The `hackathon-submission-2026` Git tag identifies the corresponding repository baseline. This checklist is not current product documentation.

## Under-four-minute story

1. In Codex/Claude/Gemini, ask for the ESP32 temperature alarm.
2. Show the agent calling `prototype_start` and immediately receiving a Build Room URL.
3. Open the URL while the Cloud Run Job is still working.
4. Point out Firestore events and the canvas evolving from idea to electronics to enclosure.
5. Show Hardware IR and deterministic electrical checks—not an LLM-authored PASS.
6. Show the actual `pio run` event and resulting `firmware.bin`.
7. For the repair beat, set `INJECT_COMPILE_FAILURE_ONCE=true`: compile fails, EngineeringAgent gets
   compiler evidence, a constrained patch is applied, and PlatformIO recompiles.
8. Show Wokwi changing the DHT22 from 25°C to 35°C, asserting GPIO 10 low/high, and matching
   `COUP_READY`, `TEMP_NORMAL`, `TEMP_ALERT`, and `COUP_TEST_PASS`. If the CI token is invalid,
   show the visible unavailable/failed state instead of claiming success.
9. Rotate the generated enclosure in the Product Canvas and download both STL files.
10. End on the report: digital prototype verified; assembly, EMI/EMC, and thermals not verified.

## Judge-proof evidence

- [ ] Gemini model name and non-sensitive Vertex AI configuration visible in Cloud Run environment.
- [ ] Cloud Run revisions show dedicated service accounts; no service-account key file is mounted.
- [ ] Wokwi is a Secret Manager reference, not a literal environment value.
- [ ] ADK `ProductPlanner` tool calls visible in logs/events.
- [ ] ADK `EngineeringAgent` receives real compiler output during repair.
- [ ] Cloud Run service returns from MCP before the worker completes.
- [ ] Cloud Run Job execution shown in Google Cloud Console.
- [ ] Firestore `/builds/{id}` and `/events/{eventId}` documents shown.
- [ ] PlatformIO output and generated firmware binary shown.
- [ ] Wokwi CLI output shown only when token-backed simulation ran.
- [ ] Cloud Storage artifact prefix shown.
- [ ] Verification report displays `not_verified` physical categories.

## Preflight

```bash
pytest services/build-worker/tests
npm run lint && npm run build && npm test
python -m hardware_build.smoke
```

- [ ] `GOOGLE_CLOUD_PROJECT`, region, Vertex AI, and Gemini model set.
- [ ] API service account can execute the Cloud Run Job.
- [ ] Worker can read/write Firestore and the artifact bucket.
- [ ] Vercel contains only public `NEXT_PUBLIC_*` configuration.
- [ ] GitHub Actions authenticated through OIDC/WIF; no Google JSON key exists in GitHub Secrets.
- [ ] Firestore rules deployed.
- [ ] A Wokwi **CI** token (`wok_` prefix, 44 characters) is stored in Secret Manager and a real scenario has passed.
- [ ] Demo build opened once to warm PlatformIO/tool image caches.
- [ ] Browser tested at desktop and narrow widths.

## Honest fallback language

- No Wokwi token: “Simulation adapter and scenario are generated; execution is unavailable until a
  token is configured.”
- No Google credentials locally: “The verified deterministic demo planner ran; ADK/Gemini mode is
  shown as unavailable in the event stream.”
- Compiler unavailable/failing: build ends in `needs_review`, never `completed` because of firmware.
- No physical prototype: “Not physically verified” remains visible in the final report.

## Integration evidence labels

- `implemented`: adapter/code exists; this is not proof of external access.
- `configured`: required non-secret config and secret reference exist; still not runtime proof.
- `runtime_verified`: a real external call or token-backed scenario succeeded in this environment.
- `unavailable_due_to_missing_credentials`: no usable ADC or Wokwi token was available.

Run `python -m hardware_build.integration_check` before the demo and retain its JSON output. Do not
turn `implemented` or `configured` into a pass in slides, logs, or the Build Room.
