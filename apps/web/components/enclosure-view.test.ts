import { Box3, BufferGeometry, Float32BufferAttribute, Vector3 } from "three";
import { describe, expect, it } from "vitest";

import { normalizeStlParts } from "../lib/stl-geometry";

describe("normalizeStlParts", () => {
  it("centers and uniformly scales loaded STL geometry", () => {
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new Float32BufferAttribute([
      10, 20, 30,
      20, 20, 30,
      10, 25, 30,
    ], 3));

    const [normalized] = normalizeStlParts([geometry]);
    const position = normalized.getAttribute("position") as Float32BufferAttribute;
    const bounds = new Box3().setFromBufferAttribute(position);
    const center = bounds.getCenter(new Vector3());
    const size = bounds.getSize(new Vector3());

    expect(center.length()).toBeCloseTo(0);
    expect(Math.max(size.x, size.y, size.z)).toBeCloseTo(4);
    expect(normalized).not.toBe(geometry);
    normalized.dispose();
    geometry.dispose();
  });
});
