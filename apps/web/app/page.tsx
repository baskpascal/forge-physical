"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

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
      if (response.status === 429) {
        const retryAfter = response.headers.get("Retry-After");
        throw new Error(`Request limit reached${retryAfter ? `; try again in ${retryAfter}s` : ""}`);
      }
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
        <span>COUP</span>
        <span className="nav-note">HARDWARE EXECUTION LAYER</span>
      </nav>
      <section className="hero">
        <p className="eyebrow">INFRASTRUCTURE FOR CODING AGENTS</p>
        <h1>Infrastructure for agents<br />that build hardware.</h1>
        <p className="hero-copy">Connect COUP to Codex, Claude Code or Gemini CLI through MCP. Your agent can generate, compile, simulate and validate supported low-voltage prototypes without leaving the development workflow.</p>
        <div className="hero-actions"><a href="https://github.com/baskpascal/forge-physical/blob/main/docs/mcp.md">Connect MCP</a><Link href="/build/b4381f2ebfbd">View a live build</Link></div>
        <form className="build-form" onSubmit={submit}>
          <label htmlFor="prompt">Try COUP in the browser</label>
          <textarea id="prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={4} />
          <div className="form-footer">
            <span>ESP32-S3 · Verified component catalog</span>
            <button disabled={busy}>{busy ? "Starting build…" : "Run build"}<b>↗</b></button>
          </div>
          {error && <p className="form-error">{error}.</p>}
        </form>
      </section>
      <div className="landing-flow" aria-label="Product flow">
        <span>CODEX · CLAUDE CODE · GEMINI CLI</span><i>→</i><span>MCP</span><i>→</i><span>COUP</span><i>→</i><span>BUILD ROOM + EVIDENCE</span>
      </div>
    </main>
  );
}
