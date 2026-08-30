import { describe, expect, it } from "vitest";

import { artifactUrl } from "./artifact-url";

describe("artifactUrl", () => {
  it("maps persisted build paths to the individual artifact endpoint", () => {
    expect(artifactUrl("abc123", "abc123/hardware/enclosure/base.stl")).toBe(
      "http://127.0.0.1:8080/api/builds/abc123/artifacts/hardware/enclosure/base.stl",
    );
  });

  it("accepts already build-relative paths and encodes segments", () => {
    expect(artifactUrl("abc123", "hardware/enclosure/my lid.stl")).toContain(
      "/hardware/enclosure/my%20lid.stl",
    );
  });

  it("rejects missing, internal, and traversal paths", () => {
    expect(artifactUrl("abc123")).toBeNull();
    expect(artifactUrl("abc123", "data/build.json")).toBeNull();
    expect(artifactUrl("abc123", "hardware/../data/build.json")).toBeNull();
  });
});
