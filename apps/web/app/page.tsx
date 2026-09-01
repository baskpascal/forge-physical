"use client";

import dynamic from "next/dynamic";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const DroneStippleHero = dynamic(() => import("@/components/drone-stipple-hero"), { ssr: false });

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
    <main className="coup-landing">
      <nav className="coup-nav">
        <Link href="/" className="coup-wordmark" aria-label="COUP home"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>COUP</Link>
        <span className="nav-note">HARDWARE EXECUTION LAYER / 01</span>
        <a className="nav-connect" href="https://github.com/baskpascal/forge-physical/blob/main/docs/mcp.md">CONNECT MCP <b>↗</b></a>
      </nav>
      <section className="coup-hero">
        <div className="hero-copy-block">
          <p className="eyebrow">COUP / AGENTIC HARDWARE</p>
          <h1>Make physical<br /><em>things.</em></h1>
          <p>COUP is the execution layer for agents building hardware — from intention to a tested physical system.</p>
          <div className="hero-actions"><a href="#build">Begin a build <b>↘</b></a><Link href="/build/b4381f2ebfbd">View live evidence</Link></div>
        </div>
        <DroneStippleHero />
      </section>
      <section id="build" className="coup-build">
        <div><p className="eyebrow">START WITH AN INTENTION</p><h2>Describe the system.<br />Your agent does the rest.</h2></div>
        <form className="build-form" onSubmit={submit}>
          <label htmlFor="prompt">Build brief</label><textarea id="prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={3} />
          <div className="form-footer"><span>SUPPORTED: ESP32-S3 · WOKWI VALIDATION</span><button disabled={busy}>{busy ? "Starting build…" : "Run build"}<b>↗</b></button></div>
          {error && <p className="form-error">{error}.</p>}
        </form>
      </section>
      <footer className="coup-footer"><span>CODEX · CLAUDE CODE · GEMINI CLI</span><span>GENERATE / COMPILE / SIMULATE / VALIDATE</span><span>© COUP 2026</span></footer>
    </main>
  );
}
