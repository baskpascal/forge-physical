import { describe, expect, it } from "vitest";
import { deriveStageState } from "./build-stage";
import type { Build } from "@/types/build";

function completedBuild(): Build {
  return {
    id: "demo",
    prompt: "desk monitor",
    status: "completed",
    stage: "complete",
    progress: 100,
    version: 1,
    artifact_paths: {},
    agent_mode: "deterministic-fallback",
    events: [],
    firmware: { status: "passed", summary: "compiled", evidence: {} },
    simulation: { status: "unavailable", summary: "token missing", evidence: {} },
    enclosure: { status: "passed", summary: "generated", evidence: {} },
  };
}

describe("deriveStageState", () => {
  it("never renders an unavailable simulation as passed", () => {
    const build = completedBuild();
    expect(deriveStageState(build, "firmware")).toBe("passed");
    expect(deriveStageState(build, "simulation")).toBe("unavailable");
    expect(deriveStageState(build, "enclosure")).toBe("passed");
  });

  it("keeps not_run distinct from unavailable", () => {
    const build = completedBuild();
    build.simulation = { status: "not_run", summary: "not attempted", evidence: {} };
    expect(deriveStageState(build, "simulation")).toBe("not_run");
  });
});
