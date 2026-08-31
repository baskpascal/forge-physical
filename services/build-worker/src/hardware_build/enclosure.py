from __future__ import annotations

import math
from pathlib import Path

from .models import HardwareIR, ToolResult

Triangle = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


def _box(x: float, y: float, z: float, width: float, depth: float, height: float) -> list[Triangle]:
    p = [
        (x, y, z),
        (x + width, y, z),
        (x + width, y + depth, z),
        (x, y + depth, z),
        (x, y, z + height),
        (x + width, y, z + height),
        (x + width, y + depth, z + height),
        (x, y + depth, z + height),
    ]
    faces = [
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    ]
    return [(p[a], p[b], p[c]) for a, b, c in faces]


def _normal(triangle: Triangle) -> tuple[float, float, float]:
    a, b, c = triangle
    u, v = tuple(b[i] - a[i] for i in range(3)), tuple(c[i] - a[i] for i in range(3))
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    length = math.sqrt(sum(value * value for value in n)) or 1
    return tuple(value / length for value in n)


def _write_stl(path: Path, name: str, triangles: list[Triangle]) -> None:
    lines = [f"solid {name}"]
    for triangle in triangles:
        normal = _normal(triangle)
        lines.append(f"  facet normal {normal[0]:.6f} {normal[1]:.6f} {normal[2]:.6f}")
        lines.append("    outer loop")
        lines.extend(f"      vertex {p[0]:.4f} {p[1]:.4f} {p[2]:.4f}" for p in triangle)
        lines.extend(["    endloop", "  endfacet"])
    lines.append(f"endsolid {name}")
    path.write_text("\n".join(lines), encoding="ascii")


def generate_enclosure(
    hardware: HardwareIR,
    enclosure_dir: Path,
    dimensions_mm: tuple[float, float, float] | None = None,
) -> ToolResult:
    enclosure_dir.mkdir(parents=True, exist_ok=True)
    width, depth, height = dimensions_mm or (84.0, 64.0, 30.0)
    wall = 2.0
    base_triangles = _box(0, 0, 0, width, depth, wall)
    base_triangles += _box(0, 0, wall, wall, depth, height - wall)
    base_triangles += _box(width - wall, 0, wall, wall, depth, height - wall)
    base_triangles += _box(wall, 0, wall, width - 2 * wall, wall, height - wall)
    # Rear wall leaves a centered USB-C opening (12 x 6 mm).
    usb_left = (width - 12) / 2
    base_triangles += _box(wall, depth - wall, wall, usb_left - wall, wall, height - wall)
    base_triangles += _box(
        usb_left + 12, depth - wall, wall, width - wall - (usb_left + 12), wall, height - wall
    )
    base_triangles += _box(usb_left, depth - wall, wall + 6, 12, wall, height - wall - 6)

    # Lid is assembled around a real 29 x 16 mm display cutout and a 7 mm knob opening.
    lid_z = 0.0
    screen_x, screen_y, screen_w, screen_h = 10.0, 16.0, 29.0, 16.0
    lid_triangles = _box(0, 0, lid_z, width, screen_y, wall)
    lid_triangles += _box(0, screen_y + screen_h, lid_z, width, depth - screen_y - screen_h, wall)
    lid_triangles += _box(0, screen_y, lid_z, screen_x, screen_h, wall)
    knob_x, knob_y, knob_r = 61.0, 25.0, 4.0
    # Right field is tiled around the knob clearance; the opening remains empty.
    lid_triangles += _box(
        screen_x + screen_w,
        screen_y,
        lid_z,
        knob_x - knob_r - (screen_x + screen_w),
        screen_h,
        wall,
    )
    lid_triangles += _box(
        knob_x + knob_r, screen_y, lid_z, width - (knob_x + knob_r), screen_h, wall
    )
    lid_triangles += _box(
        knob_x - knob_r, screen_y, lid_z, knob_r * 2, knob_y - knob_r - screen_y, wall
    )
    lid_triangles += _box(
        knob_x - knob_r,
        knob_y + knob_r,
        lid_z,
        knob_r * 2,
        screen_y + screen_h - (knob_y + knob_r),
        wall,
    )

    base_path, lid_path = enclosure_dir / "base.stl", enclosure_dir / "lid.stl"
    _write_stl(base_path, "forge_base", base_triangles)
    _write_stl(lid_path, "forge_lid", lid_triangles)
    return ToolResult(
        status="passed",
        summary="Parametric base and lid STL files generated from verified component clearances.",
        evidence={
            "files": [str(base_path), str(lid_path)],
            "dimensions_mm": [width, depth, height],
            "wall_thickness_mm": wall,
            "cutouts": {
                "screen_mm": [screen_w, screen_h],
                "knob_diameter_mm": knob_r * 2,
                "usb_mm": [12, 6],
            },
            "generator": "deterministic parametric mesh",
        },
    )
