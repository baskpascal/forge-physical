import Link from "next/link";

export const metadata = {
  title: "How COUP works",
  description: "An evidence-first execution layer for supported hardware prototypes.",
};

export default function BuildStory() {
  return (
    <main className="story-shell">
      <nav className="story-nav"><Link href="/">← COUP</Link><span>BUILD STORY</span></nav>
      <article className="story-article">
        <p className="eyebrow">PRODUCT OVERVIEW</p>
        <h1>From coding agents to verified physical prototypes</h1>
        <p className="story-deck">How we connected Gemini, Cloud Run, real ESP32 compilation and evidence-first virtual hardware testing.</p>

        <h2>The gap after code generation</h2>
        <p>Software agents can edit code, run tests and deploy services because their work has machine-readable feedback. Physical-product development breaks that loop: component selection, wiring, firmware, simulation and mechanical artifacts live in separate tools, and a plausible answer can be mistaken for a verified one.</p>

        <h2>One asynchronous build, one evidence trail</h2>
        <p>COUP accepts a low-voltage product request through a public FastAPI and Streamable HTTP MCP surface. The API creates an immutable Firestore build and immediately starts a Cloud Run Job. Google ADK and Gemini 3.5 Flash produce a constrained product specification; deterministic validators gate the supported catalog, voltage, pins, buses and required connections.</p>
        <p>The worker generates Arduino firmware and asks PlatformIO for an actual ESP32 binary. It materializes a Wokwi project and deterministic temperature-alarm scenario, then stores artifacts in Cloud Storage. The Build Room follows the same Firestore-backed event trail.</p>

        <h2>Verification must mean behavior</h2>
        <p>A simulator exit code is not enough. The golden scenario changes a DHT22 from 25°C to 35°C, asserts the ESP32 alarm GPIO low then high, and waits for <code>COUP_READY</code>, <code>TEMP_NORMAL</code>, <code>TEMP_ALERT</code> and <code>COUP_TEST_PASS</code>. Any lint, compile, simulation, pin or serial failure becomes <code>needs_review</code>.</p>

        <h2>Four Google models, distinct responsibilities</h2>
        <p>Gemini 3.5 Flash remains the ProductPlanner. Three additional Vertex AI models—<code>gemini-embedding-001</code>, <code>text-embedding-005</code> and <code>text-multilingual-embedding-002</code>—compare the request with the generated specification to expose semantic drift. COUP persists similarity, dimension and latency evidence, never the raw vectors.</p>

        <h2>Production-minded by construction</h2>
        <p>Cloud Run uses dedicated API, worker and web identities. Secret Manager injects Wokwi credentials only into the worker. GitHub Actions authenticates through OIDC and Workload Identity Federation, with no service-account JSON key. Terraform remains the source of truth.</p>

        <h2>What COUP does not claim</h2>
        <p>Virtual validation does not replace physical testing. Assembly, EMI/EMC and thermals remain explicitly <code>not_verified</code>. That distinction is part of the product: every green state must correspond to inspectable evidence.</p>

        <p className="story-cta"><Link href="/">Start a hardware build →</Link></p>
      </article>
    </main>
  );
}
