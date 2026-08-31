import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { BuildRoomDetails, RepairProof, nextTabIndex } from "./build-room-details";
import type { Build } from "@/types/build";

function queuedBuild(): Build {
  return {
    id: "queued-build",
    prompt: "Build a desk environmental monitor",
    status: "queued",
    stage: "idea",
    progress: 0,
    version: 1,
    artifact_paths: {},
    agent_mode: "pending",
    events: [],
  };
}

describe("BuildRoomDetails", () => {
  it("supports wrapping arrow navigation and Home/End tab selection", () => {
    expect(nextTabIndex(0, "ArrowLeft")).toBe(4);
    expect(nextTabIndex(4, "ArrowRight")).toBe(0);
    expect(nextTabIndex(2, "Home")).toBe(0);
    expect(nextTabIndex(2, "End")).toBe(4);
    expect(nextTabIndex(2, "Enter")).toBe(2);
  });

  it("renders accessible tabs and an honest queued state", () => {
    const html = renderToStaticMarkup(<BuildRoomDetails build={queuedBuild()} />);
    expect(html).toContain('role="tablist"');
    expect(html).toContain('aria-selected="true"');
    expect(html).toContain('role="tabpanel"');
    expect(html).toContain("queued");
    expect(html).not.toContain("not physically verified</em><span");
  });

  it("makes the bounded EngineeringAgent repair sequence explicit", () => {
    const build = queuedBuild();
    build.events = [
      { id: "1", type: "firmware.compile.failed", stage: "firmware", status: "failed", message: "Compiler rejected firmware.", metadata: {}, created_at: "2026-08-31T12:00:00Z" },
      { id: "2", type: "agent.repair.started", stage: "firmware", status: "running", message: "Repairing.", metadata: { agent: "EngineeringAgent" }, created_at: "2026-08-31T12:00:01Z" },
      { id: "3", type: "firmware.compile.started", stage: "firmware", status: "running", message: "Recompiling.", metadata: {}, created_at: "2026-08-31T12:00:02Z" },
      { id: "4", type: "firmware.compile.passed", stage: "firmware", status: "passed", message: "Passed.", metadata: { attempts: 1 }, created_at: "2026-08-31T12:00:03Z" },
    ];

    const html = renderToStaticMarkup(<RepairProof events={build.events} />);
    expect(html).toContain("BOUNDED REPAIR PROOF");
    expect(html).toContain("COMPILE FAILED");
    expect(html).toContain("EngineeringAgent");
    expect(html).toContain("RECOMPILE");
    expect(html).toContain("PASS");
  });
});
