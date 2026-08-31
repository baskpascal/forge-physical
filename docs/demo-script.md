# Four-minute Public Demo Script

Target: 3:35–3:55, one continuous take, no secrets or private console identifiers visible.

| Time | Screen | Narration / proof |
| --- | --- | --- |
| 0:00–0:25 | Build Room landing | Physical prototyping is slow because software, electronics and validation are disconnected. Forge turns one product request into evidence-backed build artifacts. |
| 0:25–0:50 | Coding agent / prompt | Submit the ESP32 temperature-alarm request through `prototype_start`; highlight the immediate build ID/URL. |
| 0:50–1:25 | Live Build Room | Show queued/planning events, Gemini 3.5 Flash agent metadata and supported ESP32/DHT22/LED Hardware IR. |
| 1:25–2:00 | Firmware evidence | Show real PlatformIO output, exit 0, `firmware.bin`, and the Cloud Run Job execution. |
| 2:00–2:45 | Wokwi evidence | Show lint pass; scenario drives 25°C then 35°C; GPIO 10 is off then on; serial includes `TEMP_NORMAL`, `TEMP_ALERT`, `COUP_TEST_PASS`. |
| 2:45–3:15 | Results/artifacts | Show Firestore-backed succeeded/completed state and download diagram, scenario, serial/result JSON, firmware and STL artifacts. |
| 3:15–3:40 | Architecture diagram | Trace Cloud Run API → Firestore → worker → Gemini/PlatformIO/Wokwi → Cloud Storage → Build Room. Mention WIF and Secret Manager. |
| 3:40–3:55 | Verification report | Close on “hardware validated virtually”; assembly, EMI/EMC and thermals are explicitly not physically verified. |

Recording checklist: public URL, readable zoom, desktop notifications disabled, token values hidden, Cloud Run/Vertex branding visible, total duration ≤4 minutes.
