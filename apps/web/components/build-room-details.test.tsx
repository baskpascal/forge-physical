import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { BuildRoomDetails, nextTabIndex } from "./build-room-details";
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
});
