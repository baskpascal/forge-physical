# Product walkthrough

Use this walkthrough to introduce COUP to users, developers, and collaborators. It is designed to make the product workflow and its evidence model clear; it does not require access to private consoles or credentials.

| Step | Surface | What to show |
| --- | --- | --- |
| 1 | Build Room | Explain that physical prototyping connects software, electronics, and validation in one workflow. |
| 2 | Coding agent | Submit an ESP32 temperature-alarm request through `prototype_start` and show the immediate build ID and URL. |
| 3 | Live Build Room | Follow queued and planning events, agent metadata, and the constrained ESP32/DHT22/LED Hardware IR. |
| 4 | Firmware evidence | Inspect PlatformIO output, the compiler exit status, and the generated `firmware.bin`. |
| 5 | Simulation evidence | Show the Wokwi scenario changing 25°C to 35°C, the GPIO state transition, and required serial markers. |
| 6 | Results and artifacts | Download the diagram, scenario, serial/result JSON, firmware, and STL artifacts. |
| 7 | Architecture | Trace API → Firestore → worker → Gemini/PlatformIO/Wokwi → Cloud Storage → Build Room. |
| 8 | Verification report | Confirm that virtual evidence is distinct from physical assembly, EMI/EMC, and thermal validation. |

Before sharing a walkthrough, use a public build URL, verify readable zoom, and keep credentials and private console identifiers out of view.
