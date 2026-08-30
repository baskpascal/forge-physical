import { Box3, BufferGeometry, Vector3 } from "three";

export function normalizeStlParts(parts: BufferGeometry[]): BufferGeometry[] {
  const geometries = parts.map((part) => part.clone());
  const bounds = new Box3();
  for (const geometry of geometries) {
    geometry.computeBoundingBox();
    if (geometry.boundingBox) bounds.union(geometry.boundingBox);
  }
  if (bounds.isEmpty()) return geometries;
  const center = bounds.getCenter(new Vector3());
  const size = bounds.getSize(new Vector3());
  const largestDimension = Math.max(size.x, size.y, size.z);
  const scale = largestDimension > 0 ? 4 / largestDimension : 1;
  for (const geometry of geometries) {
    geometry.translate(-center.x, -center.y, -center.z);
    geometry.scale(scale, scale, scale);
    geometry.computeVertexNormals();
    geometry.computeBoundingSphere();
  }
  return geometries;
}
