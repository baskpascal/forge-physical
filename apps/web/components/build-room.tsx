"use client";

import Link from "next/link";
import { ProductCanvas } from "@/components/product-canvas";
import { useBuildStream } from "@/hooks/use-build-stream";
import { deriveStageState } from "@/lib/build-stage";
import type { BuildStage, Event, Verification } from "@/types/build";

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

function EventFeed({ events }: { events: Event[] }) {
  const visible = events.slice(-5).reverse();
  return <div className="agent-feed">{visible.map((event, index) => <div className={`agent-line ${event.status}`} key={event.id}><span>{index === 0 ? "›" : ""}</span><p>{event.message}</p><time>{new Date(event.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time></div>)}</div>;
}

function VerificationPanel({ report }: { report?: Verification }) {
  if (!report) return <div className="empty-detail">Verification evidence will appear after deterministic checks run.</div>;
  const verified = [
    ["Electronics", report.electrical_compatibility], ["Firmware", report.firmware_compilation],
    ["Simulation", report.simulation], ["Enclosure", report.enclosure_generation],
  ];
  const unverified = [["Physical assembly", report.physical_assembly], ["EMI / EMC", report.emi_emc], ["Thermals", report.thermals]];
  return <div className="verification-grid"><div><p className="detail-label">DIGITAL EVIDENCE</p>{verified.map(([label, status]) => <div className="verification-row" key={label}><span className={status}>{status === "passed" ? "✓" : status === "failed" ? "!" : "—"}</span><b>{label}</b><em>{status.replaceAll("_", " ")}</em></div>)}</div><div className="not-verified"><p className="detail-label">NOT PHYSICALLY VERIFIED</p>{unverified.map(([label]) => <div className="verification-row" key={label}><span>—</span><b>{label}</b><em>not verified</em></div>)}</div></div>;
}

export function BuildRoom({ buildId }: { buildId: string }) {
  const { build, error, transport } = useBuildStream(buildId);
  if (!build) return <main className="room-shell loading-room"><div className="room-topline"><Link href="/">FORGE</Link><span>{error ?? "CONNECTING TO BUILD"}</span></div><div className="loading-canvas" /></main>;
  const title = build.product_spec?.name ?? "Untitled physical product";
  const activity = build.events.at(-1)?.message ?? "Worker is accepting the build…";
  return (
    <main className="room-shell">
      <div className="room-topline"><Link href="/"><span className="brand-mark mini"><i /><i /><i /></span>FORGE PHYSICAL</Link><div><span className={`live-dot ${transport}`} />{transport === "firestore" ? "FIRESTORE LIVE" : "LOCAL EVENT STREAM"}<b>BUILD {build.id.toUpperCase()}</b></div></div>
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
      <section className="lower-deck">
        <div className="deck-tabs"><button className="active">Engineering</button><button>Electronics</button><button>Software</button><button>Tests</button><button>3D</button><span>{Object.keys(build.artifact_paths).length} ARTIFACTS</span></div>
        <div className="deck-content"><VerificationPanel report={build.verification} /><div className="timeline-panel"><p className="detail-label">AGENT ACTIONS</p><EventFeed events={build.events} /></div></div>
      </section>
      <footer className="room-footer"><span>{build.product_spec?.description ?? build.prompt}</span><span>Physical assembly is never implied by digital verification.</span></footer>
    </main>
  );
}
