"use client";

import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { ProductCanvas } from "@/components/product-canvas";
import { artifactUrl } from "@/lib/artifact-url";
import type { Build, Event, ToolResult, Verification } from "@/types/build";

export const detailTabs = ["overview", "hardware", "firmware", "simulation", "artifacts"] as const;
export type DetailTab = (typeof detailTabs)[number];
const tabLabels: Record<DetailTab, string> = { overview: "Overview", hardware: "Hardware", firmware: "Firmware", simulation: "Simulation", artifacts: "Artifacts" };

export function nextTabIndex(current: number, key: string, count = detailTabs.length) {
  if (key === "Home") return 0; if (key === "End") return count - 1;
  if (key === "ArrowRight") return (current + 1) % count; if (key === "ArrowLeft") return (current - 1 + count) % count;
  return current;
}

export function safePlanningCopy(value: string) {
  return value
    .replace(/(?:fully\s+)?compatible with Wokwi simulation(?: for automated testing)?/gi, "structured for automated validation in Wokwi")
    .replace(/fully testable in Wokwi simulation/gi, "structured for automated validation in Wokwi");
}

function Status({ value }: { value: string }) { const normalized = value || "unavailable"; return <span className={`evidence-status ${normalized}`}>{normalized.replaceAll("_", " ")}</span>; }
function Empty({ children }: { children: ReactNode }) { return <div className="empty-detail" role="status">{children}</div>; }
function ToolEvidence({ result, noun }: { result?: ToolResult; noun: string }) {
  if (!result) return <Empty>{noun} has not run.</Empty>;
  const entries = Object.entries(result.evidence).filter(([, value]) => value !== null && value !== "" && typeof value !== "object");
  return <div className="tool-evidence"><div className="panel-summary"><Status value={result.status} /><p>{result.summary}</p></div>{entries.length > 0 && <dl className="detail-list">{entries.map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{String(value).slice(0, 500)}</dd></div>)}</dl>}</div>;
}

function verificationIcon(status: string) { return status === "passed" ? "✓" : status === "failed" ? "✕" : "—"; }
export function VerificationPanel({ report }: { report?: Verification }) {
  if (!report) return <Empty>Verification evidence will appear after deterministic checks run.</Empty>;
  const digital = [["Electrical", report.electrical_compatibility], ["Firmware", report.firmware_compilation], ["Simulation", report.simulation], ["Enclosure", report.enclosure_generation]];
  const physical = [["Physical assembly", report.physical_assembly], ["EMI / EMC", report.emi_emc], ["Thermals", report.thermals]];
  const group = (title: string, rows: string[][]) => <section><p className="detail-label">{title}</p>{rows.map(([label, status]) => <div className="verification-row" key={label}><span className={status}>{verificationIcon(status)}</span><b>{label}</b><em>{status.replaceAll("_", " ")}</em></div>)}</section>;
  return <div className="verification-grid">{group("DIGITAL VERIFICATION", digital)}{group("PHYSICAL VERIFICATION", physical)}</div>;
}

export function displayVerification(build: Build): Verification {
  return build.verification ?? {
    electrical_compatibility: build.electrical_validation ? (build.electrical_validation.passed ? "passed" : "failed") : "not_run",
    firmware_compilation: build.firmware?.status ?? "not_run",
    simulation: build.simulation?.status ?? "not_run",
    enclosure_generation: build.enclosure?.status ?? "not_run",
    physical_assembly: "not_verified",
    emi_emc: "not_verified",
    thermals: "not_verified",
  };
}

export function RepairProof({ events }: { events: Event[] }) {
  const failed = events.findIndex((event) => event.type === "firmware.compile.failed");
  const repair = events.findIndex((event, index) => index > failed && event.type === "agent.repair.started");
  const passed = events.findIndex((event, index) => index > repair && event.type === "firmware.compile.passed");
  if (failed < 0 || repair < 0) return null;
  return <section className="repair-proof"><p className="detail-label">ENGINEERING AGENT</p><p>Compiler failure detected</p><p>1 constrained repair applied</p><b>Recompile → {passed >= 0 ? "Passed" : "Pending"}</b></section>;
}

function HardwarePanel({ build }: { build: Build }) {
  if (!build.hardware) return <Empty>Hardware IR has not been generated.</Empty>;
  const paths = [...build.hardware.connections, ...build.hardware.power];
  return <div className="hardware-detail"><ProductCanvas build={build} /><section className="evidence-panel"><p className="detail-label">PINS, SIGNALS & POWER</p><div className="connection-list">{paths.map((connection, index) => <div key={`${connection.from.ref}-${connection.to.ref}-${index}`}><code>{connection.from.ref}.{connection.from.pin}</code><span>→</span><code>{connection.to.ref}.{connection.to.pin}</code><em>{connection.interface}</em><p>{connection.reason}</p></div>)}</div><p className="detail-label">DETERMINISTIC ELECTRICAL VALIDATION</p>{build.electrical_validation ? Object.entries(build.electrical_validation.checks).map(([check, passed]) => <p className="check-line" key={check}><Status value={passed ? "passed" : "failed"} /> {check.replaceAll("_", " ")}</p>) : <Empty>Not run.</Empty>}</section></div>;
}

function FirmwarePanel({ build }: { build: Build }) {
  return <div className="evidence-panel"><ToolEvidence result={build.firmware} noun="Firmware compilation" /><RepairProof events={build.events} /><p className="detail-label">FILES</p><ul className="artifact-list">{[["main.cpp", build.artifact_paths.firmware_source], ["platformio.ini", build.artifact_paths.platformio], ["firmware.bin", build.artifact_paths.firmware_bin]].map(([label, path]) => { const url = artifactUrl(build.id, path); return url && <li key={label}><a href={url}>{label}</a></li>; })}</ul></div>;
}

function SimulationPanel({ build }: { build: Build }) {
  const evidence = build.simulation?.evidence ?? {};
  const output = String(evidence.output ?? ""); const serial = String(evidence.serial_output ?? "");
  const passed = build.simulation?.status === "passed";
  return <div className="evidence-panel"><p className="detail-label">VIRTUAL BENCH TEST</p><div className="bench-grid"><span>25°C</span><b>LED OFF</b><Status value={passed && output.includes("esp:10 == 0") ? "passed" : build.simulation?.status ?? "not_run"} /><span>35°C</span><b>LED ON</b><Status value={passed && output.includes("esp:10 == 1") ? "passed" : build.simulation?.status ?? "not_run"} /></div><ToolEvidence result={build.simulation} noun="Wokwi simulation" />{passed && <div className="bench-summary"><span>Serial markers <b>{["COUP_READY", "TEMP_NORMAL", "TEMP_ALERT", "COUP_TEST_PASS"].filter((marker) => serial.includes(marker)).length}/4</b></span><span>GPIO assertions <b>{["esp:10 == 0", "esp:10 == 1"].filter((marker) => output.includes(marker)).length}/2</b></span><span>Lint <b>{evidence.lint_exit_code === 0 ? "PASS" : "FAILED"}</b></span></div>}</div>;
}

function ArtifactsPanel({ build }: { build: Build }) {
  const files = Object.entries(build.artifact_paths).map(([name, path]) => [name, artifactUrl(build.id, path)] as const).filter((item): item is readonly [string, string] => Boolean(item[1]));
  return <div className="artifacts-detail">{build.artifact_paths.enclosure_base && build.artifact_paths.enclosure_lid && <ProductCanvas build={build} enclosure />}<section className="evidence-panel"><p className="detail-label">BUILD ARTIFACTS</p><ul className="artifact-list">{files.map(([name, url]) => <li key={name}><a href={url}>{name.replaceAll("_", " ")}</a></li>)}</ul></section></div>;
}

function OverviewPanel({ build }: { build: Build }) { const spec = build.product_spec; return <div className="overview-detail"><section className="evidence-panel"><div className="panel-summary"><Status value={build.status} /><p>{safePlanningCopy(spec?.description ?? build.prompt)}</p></div>{spec && <><p className="detail-label">FEATURES</p><ul>{spec.features.map((feature) => <li key={feature}>{safePlanningCopy(feature)}</li>)}</ul><p className="detail-label">CONSTRAINTS</p><ul>{spec.constraints.map((constraint) => <li key={constraint}>{safePlanningCopy(constraint)}</li>)}</ul></>}</section><div><VerificationPanel report={displayVerification(build)} /><RepairProof events={build.events} /></div></div>; }
function ActivePanel({ tab, build }: { tab: DetailTab; build: Build }) { if (tab === "overview") return <OverviewPanel build={build} />; if (tab === "hardware") return <HardwarePanel build={build} />; if (tab === "firmware") return <FirmwarePanel build={build} />; if (tab === "simulation") return <SimulationPanel build={build} />; return <ArtifactsPanel build={build} />; }

export function BuildRoomDetails({ build }: { build: Build }) {
  const [activeTab, setActiveTab] = useState<DetailTab>("overview"); const buttons = useRef<Array<HTMLButtonElement | null>>([]);
  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) { const next = nextTabIndex(index, event.key); if (next === index && !["Home", "End"].includes(event.key)) return; event.preventDefault(); setActiveTab(detailTabs[next]); buttons.current[next]?.focus(); }
  return <section className="lower-deck"><div className="deck-tabs" role="tablist" aria-label="Build evidence">{detailTabs.map((tab, index) => <button key={tab} ref={(element) => { buttons.current[index] = element; }} id={`tab-${tab}`} role="tab" aria-selected={activeTab === tab} aria-controls={`panel-${tab}`} tabIndex={activeTab === tab ? 0 : -1} className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)} onKeyDown={(event) => onKeyDown(event, index)}>{tabLabels[tab]}</button>)}<span>{Object.keys(build.artifact_paths).length} ARTIFACTS</span></div><div id={`panel-${activeTab}`} role="tabpanel" aria-labelledby={`tab-${activeTab}`} tabIndex={0}><ActivePanel tab={activeTab} build={build} /></div><details className="activity-drawer"><summary>Activity / Logs <span>{build.events.length} events</span></summary><div className="agent-feed">{build.events.slice().reverse().map((event) => <div className={`agent-line ${event.status}`} key={event.id}><span>›</span><p>{event.message}</p><time>{new Date(event.created_at).toLocaleTimeString()}</time></div>)}</div></details></section>;
}
