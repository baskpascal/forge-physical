"use client";

import Link from "next/link";
import { ProductCanvas } from "@/components/product-canvas";
import { BuildRoomDetails, VerificationPanel, displayVerification, safePlanningCopy } from "@/components/build-room-details";
import { useBuildStream } from "@/hooks/use-build-stream";
import { deriveStageState } from "@/lib/build-stage";
import type { Build, BuildStage } from "@/types/build";

const terminal = new Set(["completed", "needs_review", "failed", "unsupported_scope"]);
const macroStages: Array<{ label: string; stages: BuildStage[] }> = [
  { label: "PLANNING", stages: ["idea", "components"] },
  { label: "ELECTRONICS", stages: ["electronics"] },
  { label: "FIRMWARE", stages: ["firmware"] },
  { label: "SIMULATION", stages: ["simulation"] },
  { label: "ENCLOSURE", stages: ["enclosure"] },
  { label: "VERIFICATION", stages: ["verification"] },
  { label: "COMPLETED", stages: ["complete"] },
];

export function macroStageState(build: Build, stages: BuildStage[]) {
  const states = stages.map((stage) => deriveStageState(build, stage));
  if (states.includes("failed")) return "failed"; if (states.includes("unavailable")) return "unavailable"; if (states.includes("not_run")) return "not_run";
  if (states.includes("active")) return "active"; if (states.every((state) => state === "passed")) return "passed";
  return "pending";
}
function duration(build: Build) {
  const start = build.created_at ?? build.events[0]?.created_at; const end = build.updated_at ?? build.events.at(-1)?.created_at;
  if (!start || !end) return null; const seconds = Math.max(0, Math.round((Date.parse(end) - Date.parse(start)) / 1000));
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s`;
}
export function terminalSummary(build: Build) {
  if (build.status === "queued") return build.queue_position && build.queue_position > 0
    ? `Waiting for hardware execution slot · Position ${build.queue_position}`
    : "Queued · starting hardware worker";
  const elapsed = duration(build); if (!terminal.has(build.status)) return `${build.progress}% · ${build.stage.replaceAll("_", " ")}`;
  if (build.status === "completed") return elapsed ? `Completed in ${elapsed}` : "Completed";
  const stop = build.simulation?.status === "failed" || build.simulation?.status === "unavailable" ? "Simulation" : build.stage === "complete" ? "Verification" : build.stage;
  return `Stopped at ${String(stop).replaceAll("_", " ")} ${elapsed ? `· ${elapsed}` : ""}`.trim();
}
function icon(state: string) { return state === "passed" ? "✓" : state === "failed" ? "✕" : ["unavailable", "not_run"].includes(state) ? "—" : state === "active" ? "●" : "○"; }

export function BuildRoom({ buildId }: { buildId: string }) {
  const { build, error, transport } = useBuildStream(buildId);
  if (!build) return <main className="room-shell loading-room"><div className="room-topline"><Link href="/">COUP</Link><span>{error ?? "CONNECTING TO BUILD"}</span></div><div className="loading-canvas" /></main>;
  const title = build.product_spec?.name ?? "Untitled physical product";
  return <main className="room-shell">
    <div className="room-topline"><Link href="/">COUP <span>/ Build Room</span></Link><div><span className={`live-dot ${transport}`} />{transport === "firestore" ? "FIRESTORE LIVE" : "CLOUD API STREAM"}<b>{build.id}</b></div></div>
    <header className="build-header"><div><p className="eyebrow">SUPPORTED LOW-VOLTAGE PROTOTYPE</p><h1>{title}</h1><p className="build-result-line">{terminalSummary(build)}</p></div><div className={`status-badge ${build.status}`}><i />{build.status.replaceAll("_", " ")}</div></header>
    {build.status === "queued" && <p className="queue-notice" role="status">{build.queue_position && build.queue_position > 0 ? `Queued · Waiting for hardware execution slot · Position: ${build.queue_position}` : "Queued · Starting hardware worker"}</p>}
    <section className="build-overview">
      <ProductCanvas build={build} />
      <aside className="receipt-card"><VerificationPanel report={displayVerification(build)} /></aside>
    </section>
    <ol className="macro-flow" aria-label="Build phases"><li className={build.status === "queued" ? "active" : "passed"}><span>{build.status === "queued" ? "●" : "✓"}</span><b>QUEUED</b><small>{build.status === "queued" ? "active" : "passed"}</small></li>{macroStages.map((macro) => { const state = macroStageState(build, macro.stages); return <li className={state} key={macro.label}><span>{icon(state)}</span><b>{macro.label}</b><small>{state.replaceAll("_", " ")}</small></li>; })}</ol>
    <p className="overview-copy">{safePlanningCopy(build.product_spec?.description ?? build.prompt)}</p>
    <BuildRoomDetails build={build} />
    <footer className="room-footer"><span>COUP — Infrastructure for agents that build hardware.</span><span>Physical assembly is never implied by digital verification.</span></footer>
  </main>;
}
