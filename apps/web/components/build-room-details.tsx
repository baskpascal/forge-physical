"use client";

import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { ProductCanvas } from "@/components/product-canvas";
import { artifactUrl } from "@/lib/artifact-url";
import type { Build, Event, ToolResult, Verification } from "@/types/build";

export const detailTabs = ["engineering", "electronics", "software", "tests", "3d"] as const;
export type DetailTab = (typeof detailTabs)[number];

const tabLabels: Record<DetailTab, string> = {
  engineering: "Engineering",
  electronics: "Electronics",
  software: "Software",
  tests: "Tests",
  "3d": "3D",
};

export function nextTabIndex(current: number, key: string, count = detailTabs.length) {
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  if (key === "ArrowRight") return (current + 1) % count;
  if (key === "ArrowLeft") return (current - 1 + count) % count;
  return current;
}

function Status({ value }: { value: string }) {
  const normalized = value || "unavailable";
  return <span className={`evidence-status ${normalized}`}>{normalized.replaceAll("_", " ")}</span>;
}

function Empty({ children }: { children: ReactNode }) {
  return <div className="empty-detail" role="status">{children}</div>;
}

function DefinitionList({ rows }: { rows: Array<[string, ReactNode]> }) {
  return <dl className="detail-list">{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>;
}

function boundedEvidence(value: unknown) {
  const text = String(value);
  return text.length > 500 ? `${text.slice(0, 500)}…` : text;
}

function ToolEvidence({ result, noun }: { result?: ToolResult; noun: string }) {
  if (!result) return <Empty>{noun} evidence is unavailable while this stage is queued or has not run.</Empty>;
  const entries = Object.entries(result.evidence).filter(([, value]) => value !== null && value !== "" && typeof value !== "object");
  return <div className="tool-evidence"><div className="panel-summary"><Status value={result.status} /><p>{result.summary}</p></div>{entries.length > 0 && <DefinitionList rows={entries.map(([key, value]) => [key.replaceAll("_", " "), boundedEvidence(value)])} />}</div>;
}

function EventFeed({ events }: { events: Event[] }) {
  const visible = events.slice(-5).reverse();
  if (visible.length === 0) return <Empty>No agent actions have been reported yet.</Empty>;
  return <div className="agent-feed">{visible.map((event, index) => <div className={`agent-line ${event.status}`} key={event.id}><span>{index === 0 ? "›" : ""}</span><p>{event.message}</p><time>{new Date(event.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time></div>)}</div>;
}

export function VerificationPanel({ report }: { report?: Verification }) {
  if (!report) return <Empty>Verification evidence will appear after deterministic checks run.</Empty>;
  const verified = [
    ["Electronics", report.electrical_compatibility], ["Firmware", report.firmware_compilation],
    ["Simulation", report.simulation], ["Enclosure", report.enclosure_generation],
  ];
  const unverified = [["Physical assembly", report.physical_assembly], ["EMI / EMC", report.emi_emc], ["Thermals", report.thermals]];
  return <div className="verification-grid"><div><p className="detail-label">DIGITAL EVIDENCE</p>{verified.map(([label, status]) => <div className="verification-row" key={label}><span className={status}>{status === "passed" ? "✓" : status === "failed" ? "!" : "—"}</span><b>{label}</b><em>{status.replaceAll("_", " ")}</em></div>)}</div><div className="not-verified"><p className="detail-label">NOT PHYSICALLY VERIFIED</p>{unverified.map(([label, status]) => <div className="verification-row" key={label}><span>—</span><b>{label}</b><em>{status.replaceAll("_", " ")}</em></div>)}</div></div>;
}

function EngineeringPanel({ build }: { build: Build }) {
  const spec = build.product_spec;
  return <div className="evidence-panel"><div className="panel-summary"><Status value={build.status} /><p>{spec?.description ?? build.prompt}</p></div><DefinitionList rows={[["Current stage", build.stage], ["Agent mode", build.agent_mode], ["Progress", `${build.progress}%`], ["Parent build", build.parent_build_id ?? "Original build"]]} />{spec && <div className="detail-columns"><section><p className="detail-label">FEATURES</p><ul>{spec.features.map((feature) => <li key={feature}>{feature}</li>)}</ul></section><section><p className="detail-label">CONSTRAINTS</p>{spec.constraints.length ? <ul>{spec.constraints.map((constraint) => <li key={constraint}>{constraint}</li>)}</ul> : <p className="muted-copy">No product constraints were recorded.</p>}</section></div>}</div>;
}

function ElectronicsPanel({ build }: { build: Build }) {
  const hardware = build.hardware;
  if (!hardware) return <Empty>Electronics data is unavailable while component planning has not completed.</Empty>;
  const validation = build.electrical_validation;
  return <div className="evidence-panel"><div className="panel-summary"><Status value={validation ? (validation.passed ? "passed" : "failed") : "not_run"} /><p>{hardware.components.length + 1} components · {hardware.connections.length} signal paths · {hardware.power.length} power paths</p></div><div className="detail-columns"><section><p className="detail-label">COMPONENTS</p><ul><li>{hardware.board.ref} · {hardware.board.label}</li>{hardware.components.map((component) => <li key={component.ref}>{component.ref} · {component.label}</li>)}</ul></section><section><p className="detail-label">VALIDATOR CHECKS</p>{validation ? <ul>{Object.entries(validation.checks).map(([check, passed]) => <li key={check}><Status value={passed ? "passed" : "failed"} /> {check.replaceAll("_", " ")}</li>)}</ul> : <p className="muted-copy">Electrical validation has not run.</p>}</section></div><p className="detail-label">CONNECTIONS</p><div className="connection-list">{[...hardware.connections, ...hardware.power].map((connection, index) => <div key={`${connection.from.ref}-${connection.from.pin}-${connection.to.ref}-${connection.to.pin}-${index}`}><code>{connection.from.ref}.{connection.from.pin}</code><span>→</span><code>{connection.to.ref}.{connection.to.pin}</code><em>{connection.interface}</em><p>{connection.reason}</p></div>)}</div>{validation?.issues.length ? <section className="validation-issues"><p className="detail-label">VALIDATION ISSUES</p>{validation.issues.map((issue) => <p key={`${issue.code}-${issue.path}`}><Status value={issue.severity === "error" ? "failed" : "unavailable"} /> <b>{issue.code}</b> {issue.message}</p>)}</section> : null}</div>;
}

function SoftwarePanel({ build }: { build: Build }) {
  const source = build.artifact_paths.firmware_source;
  const platformio = build.artifact_paths.platformio;
  const sourceUrl = artifactUrl(build.id, source);
  const platformioUrl = artifactUrl(build.id, platformio);
  return <div className="evidence-panel"><ToolEvidence result={build.firmware} noun="Firmware" /><p className="detail-label">GENERATED FILES</p>{sourceUrl || platformioUrl ? <ul className="artifact-list">{sourceUrl && <li><a href={sourceUrl}>main.cpp</a></li>}{platformioUrl && <li><a href={platformioUrl}>platformio.ini</a></li>}</ul> : <p className="muted-copy">Firmware artifacts are not available yet.</p>}</div>;
}

function TestsPanel({ build }: { build: Build }) {
  return <div><VerificationPanel report={build.verification} />{build.verification?.scenario_checks?.length ? <div className="scenario-checks"><p className="detail-label">DETERMINISTIC SCENARIO CHECKS</p><ul>{build.verification.scenario_checks.map((check) => <li key={check}>{check}</li>)}</ul></div> : null}<div className="simulation-evidence"><p className="detail-label">SIMULATION</p><ToolEvidence result={build.simulation} noun="Simulation" /></div></div>;
}

function ThreeDPanel({ build }: { build: Build }) {
  const base = build.artifact_paths.enclosure_base;
  const lid = build.artifact_paths.enclosure_lid;
  const baseUrl = artifactUrl(build.id, base);
  const lidUrl = artifactUrl(build.id, lid);
  if (!baseUrl || !lidUrl) return <Empty>Generated enclosure artifacts are unavailable while the 3D stage is queued, failed, or has not run.</Empty>;
  return <div className="three-detail"><ProductCanvas build={build} /><div><p className="detail-label">GENERATED STL ARTIFACTS</p><p>The canvas and downloads use the enclosure bytes produced by this build.</p><a href={baseUrl}>Download base.stl</a><a href={lidUrl}>Download lid.stl</a></div></div>;
}

function ActivePanel({ tab, build }: { tab: DetailTab; build: Build }) {
  if (tab === "engineering") return <EngineeringPanel build={build} />;
  if (tab === "electronics") return <ElectronicsPanel build={build} />;
  if (tab === "software") return <SoftwarePanel build={build} />;
  if (tab === "tests") return <TestsPanel build={build} />;
  return <ThreeDPanel build={build} />;
}

export function BuildRoomDetails({ build }: { build: Build }) {
  const [activeTab, setActiveTab] = useState<DetailTab>("engineering");
  const buttons = useRef<Array<HTMLButtonElement | null>>([]);

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const next = nextTabIndex(index, event.key);
    if (next === index && !["Home", "End"].includes(event.key)) return;
    event.preventDefault();
    setActiveTab(detailTabs[next]);
    buttons.current[next]?.focus();
  }

  return <section className="lower-deck"><div className="deck-tabs" role="tablist" aria-label="Build evidence">{detailTabs.map((tab, index) => <button key={tab} ref={(element) => { buttons.current[index] = element; }} id={`tab-${tab}`} role="tab" aria-selected={activeTab === tab} aria-controls={`panel-${tab}`} tabIndex={activeTab === tab ? 0 : -1} className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)} onKeyDown={(event) => onKeyDown(event, index)}>{tabLabels[tab]}</button>)}<span>{Object.keys(build.artifact_paths).length} ARTIFACTS</span></div><div className="deck-content"><div id={`panel-${activeTab}`} role="tabpanel" aria-labelledby={`tab-${activeTab}`} tabIndex={0}><ActivePanel tab={activeTab} build={build} /></div><aside className="timeline-panel"><p className="detail-label">AGENT ACTIONS</p><EventFeed events={build.events} /></aside></div></section>;
}
