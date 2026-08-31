"use client";

import dynamic from "next/dynamic";
import { artifactUrl } from "@/lib/artifact-url";
import type { Build, ComponentInstance, Connection } from "@/types/build";

const EnclosureView = dynamic(() => import("./enclosure-view").then((module) => module.EnclosureView), { ssr: false });

function HardwareNode({ component, kind }: { component: ComponentInstance; kind: "board" | "component" }) {
  return <article className={`hardware-node ${kind}`} data-component-id={component.component_id}>
    <span>{kind === "board" ? "CONTROLLER" : component.component_id.toUpperCase()}</span><b>{component.label}</b><code>{component.ref}</code>
  </article>;
}

function pathLabel(connection: Connection) { return `${connection.from.ref}.${connection.from.pin} → ${connection.to.ref}.${connection.to.pin}`; }

export function ProductCanvas({ build, enclosure = false }: { build: Build; enclosure?: boolean }) {
  const hardware = build.hardware;
  if (enclosure) {
    const baseUrl = artifactUrl(build.id, build.artifact_paths.enclosure_base);
    const lidUrl = artifactUrl(build.id, build.artifact_paths.enclosure_lid);
    return <div className="product-canvas three-canvas"><EnclosureView baseUrl={baseUrl} lidUrl={lidUrl} /><div className="canvas-caption"><span>GENERATED ENCLOSURE</span><b>ACTUAL BASE + LID STL</b></div></div>;
  }
  if (!hardware) return <div className="product-canvas hardware-empty" role="status">Hardware IR will appear after component planning.</div>;
  const paths = [...hardware.connections, ...hardware.power];
  const resistorPath = paths.find((connection) => /resistor/i.test(connection.reason));
  return <div className="product-canvas hardware-ir-view">
    <p className="canvas-kicker">ACTUAL HARDWARE · HARDWARE IR</p>
    <div className="hardware-graph" role="img" aria-label={`Hardware IR: ${[hardware.board, ...hardware.components].map((part) => part.label).join(", ")}`}>
      <HardwareNode component={hardware.board} kind="board" />
      <div className="hardware-branches">{hardware.components.map((component) => <div className="hardware-branch" key={component.ref}><i aria-hidden="true" /><HardwareNode component={component} kind="component" />{component.ref === resistorPath?.to.ref && <span className="inline-accessory">+ current-limiting resistor</span>}</div>)}</div>
    </div>
    <div className="hardware-paths" aria-label="Hardware connections">{paths.map((connection, index) => <span key={`${pathLabel(connection)}-${index}`}><code>{pathLabel(connection)}</code><em>{connection.interface}</em></span>)}</div>
    <div className="canvas-caption"><span>NO INFERRED COMPONENTS</span><b>{hardware.components.length + 1} components · {hardware.connections.length} signals · {hardware.power.length} power paths</b></div>
  </div>;
}
