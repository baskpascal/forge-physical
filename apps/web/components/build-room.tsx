"use client";

import Link from "next/link";
import { ProductCanvas } from "@/components/product-canvas";
import { BuildRoomDetails } from "@/components/build-room-details";
import { useBuildStream } from "@/hooks/use-build-stream";
import { deriveStageState } from "@/lib/build-stage";
import type { BuildStage } from "@/types/build";

const stages: Array<{ key: BuildStage; label: string }> = [
  { key: "idea", label: "Idea" }, { key: "components", label: "Components" },
  { key: "electronics", label: "Electronics" }, { key: "firmware", label: "Firmware" },
  { key: "simulation", label: "Simulation" }, { key: "enclosure", label: "Enclosure" },
  { key: "verification", label: "Verification" },
];
function iconFor(state: string) {
  if (state === "passed") return "✓";
  if (state === "failed") return "!";
  if (state === "active") return "●";
  if (state === "unavailable") return "—";
  return "○";
}

export function BuildRoom({ buildId }: { buildId: string }) {
  const { build, error, transport } = useBuildStream(buildId);
  if (!build) return <main className="room-shell loading-room"><div className="room-topline"><Link href="/">FORGE</Link><span>{error ?? "CONNECTING TO BUILD"}</span></div><div className="loading-canvas" /></main>;
  const title = build.product_spec?.name ?? "Untitled physical product";
  const activity = build.events.at(-1)?.message ?? "Worker is accepting the build…";
  return (
    <main className="room-shell">
      <div className="room-topline"><Link href="/"><span className="brand-mark mini"><i /><i /><i /></span>FORGE PHYSICAL</Link><div><span className={`live-dot ${transport}`} />{transport === "firestore" ? "FIRESTORE LIVE" : "CLOUD API STREAM"}<b>BUILD {build.id.toUpperCase()}</b></div></div>
      <header className="build-header"><div><p className="eyebrow">PRODUCT / VERSION {build.version}</p><h1>{title}</h1></div><div className={`status-badge ${build.status}`}><i />{build.status.replaceAll("_", " ")}</div></header>
      <section className="workbench">
        <ProductCanvas build={build} />
        <aside className="build-rail">
          <div className="rail-heading"><p>BUILD</p><span>{build.progress}%</span></div>
          <div className="progress-track"><i style={{ width: `${build.progress}%` }} /></div>
          <ol className="stage-list">{stages.map((stage) => { const state = deriveStageState(build, stage.key); return <li className={state} key={stage.key}><span>{iconFor(state)}</span><p>{stage.label}</p>{state === "active" && <small>{build.status === "repairing" ? "REPAIRING" : "IN PROGRESS"}</small>}{state === "unavailable" && <small>UNAVAILABLE</small>}</li>; })}</ol>
          <div className="rail-agent"><div className="agent-title"><span>AGENT</span><b>{build.agent_mode}</b></div><p>{activity}</p><div className="agent-pulse"><i /><i /><i /></div></div>
        </aside>
      </section>
      <BuildRoomDetails build={build} />
      <footer className="room-footer"><span>{build.product_spec?.description ?? build.prompt}</span><span>Physical assembly is never implied by digital verification.</span></footer>
    </main>
  );
}
