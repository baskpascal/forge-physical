import { describe, expect, it } from "vitest";
import { macroStageState, terminalSummary } from "./build-room";
import type { Build } from "@/types/build";

function build(status: Build["status"]): Build {
  return { id: "test", prompt: "test", status, stage: status === "completed" ? "complete" : "simulation", progress: 100, version: 1, artifact_paths: {}, agent_mode: "test", events: [], created_at: "2026-08-31T12:00:00Z", updated_at: "2026-08-31T12:02:18Z", firmware: { status: "passed", summary: "compiled", evidence: {} }, simulation: { status: status === "completed" ? "passed" : "failed", summary: "simulated", evidence: {} } };
}

describe("Build Room presentation", () => {
  it("shows a completed duration instead of terminal 100 percent", () => {
    expect(terminalSummary(build("completed"))).toBe("Completed in 2m 18s");
  });
  it("shows the actual failed macro phase", () => {
    const failed = build("failed");
    expect(terminalSummary(failed)).toContain("Stopped at Simulation");
    expect(macroStageState(failed, ["simulation"])).toBe("failed");
  });
  it("treats capacity as a queued product state with position", () => {
    const queued = build("queued");
    queued.stage = "idea";
    queued.progress = 0;
    queued.queue_position = 2;
    expect(terminalSummary(queued)).toBe("Waiting for hardware execution slot · Position 2");
  });
});
