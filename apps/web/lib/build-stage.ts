import type { Build, BuildStage } from "@/types/build";

const ranks: Record<BuildStage, number> = {
  idea: 0,
  components: 1,
  electronics: 2,
  firmware: 3,
  simulation: 4,
  enclosure: 5,
  verification: 6,
  complete: 7,
};

export type StageState = "passed" | "active" | "pending" | "failed" | "unavailable";

export function deriveStageState(build: Build, stage: BuildStage): StageState {
  const current = ranks[build.stage];
  const target = ranks[stage];
  const toolStatus = stage === "firmware"
    ? build.firmware?.status
    : stage === "simulation"
      ? build.simulation?.status
      : stage === "enclosure"
        ? build.enclosure?.status
        : undefined;
  if (toolStatus === "unavailable" || toolStatus === "not_run") return "unavailable";
  if (toolStatus === "failed") return "failed";
  if (build.status === "failed" && current === target) return "failed";
  if (current > target || build.stage === "complete") return "passed";
  if (current === target) return "active";
  return "pending";
}
