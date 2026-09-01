"use client";

import dynamic from "next/dynamic";
import gsap from "gsap";
import Link from "next/link";
import { useEffect } from "react";

const SharedHalftoneField = dynamic(() => import("@/components/shared-halftone-field"), { ssr: false });

export default function Home() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timeline = gsap.timeline({ defaults: { ease: "power2.out" } });
    timeline.set(".clean-header, .clean-message, .clean-footer", { opacity: 0 })
      .set(".shared-field", { opacity: 0 })
      .to(".clean-header", { opacity: 1, duration: .28 })
      .to(".shared-field", { opacity: 1, duration: .65 }, "+=.10")
      .to(".clean-message", { opacity: 1, duration: .36 }, "<+.18")
      .to(".clean-footer", { opacity: 1, duration: .28 }, "<+.12");
    return () => { timeline.kill(); };
  }, []);

  return <main className="reboot-landing clean-landing">
    <header className="reboot-nav clean-header">
      <Link href="/" className="reboot-logo wordmark" aria-describedby="coup-definition">COUP<span id="coup-definition" className="wordmark-definition"><b>COUP</b><em>/kʊ/</em><span>noun</span><strong>A rupture in the existing order.<br />A decisive shift in who gets to build.</strong><i>We believe machines should be as accessible to create as software.</i></span></Link>
      <nav className="reboot-links" aria-label="Primary"><a href="#manifesto">Manifesto</a><a href="#build">Builds</a><a href="https://github.com/baskpascal/forge-physical/blob/main/docs/mcp.md">Connect</a></nav>
      <a className="nav-cta" href="#get-coup">Get Coup</a>
    </header>
    <section className="reboot-hero clean-hero">
      <SharedHalftoneField />
      <div className="reboot-message clean-message"><h1>Vibe code<br />a drone.</h1><p>From prompt to flight.</p><a id="get-coup" className="hero-cta" href="https://github.com/baskpascal/forge-physical/blob/main/docs/mcp.md">Get Coup <b>↗</b></a><Link className="watch-build" href="/build/b4381f2ebfbd">Watch a build</Link></div>
    </section>
    <footer className="reboot-meta clean-footer"><span>COUP</span><span>Works with Codex · Claude Code · Gemini CLI</span><span>2026</span></footer>
  </main>;
}
