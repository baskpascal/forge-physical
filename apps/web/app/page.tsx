"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

const defaultPrompt =
  "Create an ESP32 temperature alarm. Use a temperature sensor. Turn the warning LED on when temperature is above 30°C. The design must be testable automatically in Wokwi.";

export default function Home() {
  const router = useRouter();
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const base = process.env.NEXT_PUBLIC_BUILD_API_URL ?? "http://127.0.0.1:8080";
      const response = await fetch(`${base}/api/builds`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      if (!response.ok) throw new Error(`Build service returned ${response.status}`);
      const build = (await response.json()) as { build_id: string };
      router.push(`/build/${build.build_id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not start the build");
      setBusy(false);
    }
  }

  return (
    <main className="landing">
      <nav className="landing-nav">
        <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
        <span>FORGE PHYSICAL</span>
        <span className="nav-note">AGENT-NATIVE HARDWARE</span>
      </nav>
      <section className="hero">
        <p className="eyebrow">PHYSICAL BUILD INFRASTRUCTURE</p>
        <h1>Software agents can now<br />build beyond software.</h1>
        <p className="hero-copy">From product intent to compiled firmware, simulated electronics, parametric enclosure and an evidence-backed prototype.</p>
        <form className="build-form" onSubmit={submit}>
          <label htmlFor="prompt">Describe a low-voltage prototype</label>
          <textarea id="prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={4} />
          <div className="form-footer">
            <span>ESP32-S3 · Verified component catalog</span>
            <button disabled={busy}>{busy ? "Starting build…" : "Start hardware build"}<b>↗</b></button>
          </div>
          {error && <p className="form-error">{error}. The build service may be temporarily unavailable.</p>}
        </form>
      </section>
      <div className="landing-flow" aria-label="Product flow">
        <span>CODEX / CLAUDE / GEMINI</span><i>→</i><span>MCP</span><i>→</i><span>HARDWARE BUILD</span><i>→</i><span>VERIFIED PROTOTYPE</span>
      </div>
    </main>
  );
}
