"""Generate a lightweight OBJ fallback for the Pet G companion.

This does not require Blender. The authoritative Blender source generator is
`make_pet_g_blender.py`; this fallback exists so the repository contains an
immediately inspectable mesh even on machines without Blender installed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OBJ_PATH = ROOT / "pet_g.obj"
MTL_PATH = ROOT / "pet_g.mtl"
MANIFEST_PATH = ROOT / "pet_g_manifest.json"


class Mesh:
    def __init__(self) -> None:
        self.vertices: list[tuple[float, float, float]] = []
        self.faces: list[tuple[str, tuple[int, ...]]] = []

    def add_vertex(self, v: tuple[float, float, float]) -> int:
        self.vertices.append(v)
        return len(self.vertices)

    def add_face(self, material: str, indices: tuple[int, ...]) -> None:
        self.faces.append((material, indices))


def transform(v: tuple[float, float, float], loc, scale) -> tuple[float, float, float]:
    return (loc[0] + v[0] * scale[0], loc[1] + v[1] * scale[1], loc[2] + v[2] * scale[2])


def add_uv_sphere(mesh: Mesh, name: str, material: str, loc, scale, rings=18, segments=32) -> None:
    start_faces = len(mesh.faces)
    grid: list[list[int]] = []
    for r in range(rings + 1):
        theta = math.pi * r / rings
        row: list[int] = []
        for s in range(segments):
            phi = 2 * math.pi * s / segments
            base = (math.sin(theta) * math.cos(phi), math.sin(theta) * math.sin(phi), math.cos(theta))
            row.append(mesh.add_vertex(transform(base, loc, scale)))
        grid.append(row)
    for r in range(rings):
        for s in range(segments):
            a = grid[r][s]
            b = grid[r][(s + 1) % segments]
            c = grid[r + 1][(s + 1) % segments]
            d = grid[r + 1][s]
            mesh.add_face(material, (a, b, c, d))
    mesh.faces[start_faces:start_faces] = [(f"o {name}", tuple())]


def add_cube(mesh: Mesh, name: str, material: str, loc, scale) -> None:
    x, y, z = scale
    points = [
        (-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
        (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z),
    ]
    ids = [mesh.add_vertex((loc[0] + px, loc[1] + py, loc[2] + pz)) for px, py, pz in points]
    for face in [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]:
        mesh.add_face(material, tuple(ids[i] for i in face))
    mesh.faces.insert(len(mesh.faces) - 6, (f"o {name}", tuple()))


def add_cylinder(mesh: Mesh, name: str, material: str, loc, radius, depth, segments=28, axis="z") -> None:
    ids_bottom: list[int] = []
    ids_top: list[int] = []
    for i in range(segments):
        a = 2 * math.pi * i / segments
        p = (math.cos(a) * radius, math.sin(a) * radius)
        if axis == "z":
            bottom = (loc[0] + p[0], loc[1] + p[1], loc[2] - depth / 2)
            top = (loc[0] + p[0], loc[1] + p[1], loc[2] + depth / 2)
        else:
            bottom = (loc[0] - depth / 2, loc[1] + p[0], loc[2] + p[1])
            top = (loc[0] + depth / 2, loc[1] + p[0], loc[2] + p[1])
        ids_bottom.append(mesh.add_vertex(bottom))
        ids_top.append(mesh.add_vertex(top))
    mesh.faces.append((f"o {name}", tuple()))
    mesh.add_face(material, tuple(reversed(ids_bottom)))
    mesh.add_face(material, tuple(ids_top))
    for i in range(segments):
        mesh.add_face(material, (ids_bottom[i], ids_bottom[(i + 1) % segments], ids_top[(i + 1) % segments], ids_top[i]))


def build() -> None:
    mesh = Mesh()
    add_uv_sphere(mesh, "body_soft_capsule", "body_graphite", (0, 0, 1.45), (0.72, 0.52, 0.92))
    add_uv_sphere(mesh, "head_round_display", "body_graphite", (0, 0, 2.45), (0.58, 0.5, 0.48))
    add_uv_sphere(mesh, "left_eye", "eye_glow", (-0.22, -0.45, 2.52), (0.08, 0.035, 0.08), 10, 16)
    add_uv_sphere(mesh, "right_eye", "eye_glow", (0.22, -0.45, 2.52), (0.08, 0.035, 0.08), 10, 16)
    add_cube(mesh, "chest_g_vertical", "amber_mark", (-0.18, -0.55, 1.55), (0.055, 0.03, 0.28))
    add_cube(mesh, "chest_g_top", "amber_mark", (0.02, -0.55, 1.80), (0.23, 0.03, 0.055))
    add_cube(mesh, "chest_g_bottom", "amber_mark", (0.02, -0.55, 1.30), (0.23, 0.03, 0.055))
    add_cube(mesh, "chest_g_mid", "amber_mark", (0.08, -0.55, 1.53), (0.17, 0.03, 0.052))
    add_cube(mesh, "chest_g_tip", "amber_mark", (0.27, -0.55, 1.41), (0.052, 0.03, 0.13))
    add_cylinder(mesh, "left_antenna", "metal_trim", (-0.28, 0.02, 2.95), 0.028, 0.42)
    add_cylinder(mesh, "right_antenna", "metal_trim", (0.28, 0.02, 2.95), 0.028, 0.42)
    add_uv_sphere(mesh, "left_antenna_light", "eye_glow", (-0.28, 0.02, 3.19), (0.075, 0.075, 0.075), 8, 14)
    add_uv_sphere(mesh, "right_antenna_light", "eye_glow", (0.28, 0.02, 3.19), (0.075, 0.075, 0.075), 8, 14)
    add_cylinder(mesh, "left_arm", "body_graphite", (-0.68, -0.02, 1.58), 0.07, 0.62, axis="x")
    add_cylinder(mesh, "right_arm", "body_graphite", (0.68, -0.02, 1.58), 0.07, 0.62, axis="x")
    add_uv_sphere(mesh, "left_hand", "metal_trim", (-1.0, -0.02, 1.58), (0.11, 0.11, 0.11), 10, 16)
    add_uv_sphere(mesh, "right_hand", "metal_trim", (1.0, -0.02, 1.58), (0.11, 0.11, 0.11), 10, 16)
    add_uv_sphere(mesh, "left_foot", "metal_trim", (-0.32, -0.04, 0.54), (0.22, 0.18, 0.11), 10, 18)
    add_uv_sphere(mesh, "right_foot", "metal_trim", (0.32, -0.04, 0.54), (0.22, 0.18, 0.11), 10, 18)

    MTL_PATH.write_text(
        "\n".join(
            [
                "newmtl body_graphite", "Kd 0.055 0.063 0.075", "Ks 0.5 0.5 0.5", "Ns 120",
                "newmtl metal_trim", "Kd 0.36 0.40 0.44", "Ks 0.8 0.8 0.8", "Ns 180",
                "newmtl eye_glow", "Kd 0.24 0.86 1.0", "Ke 0.12 0.55 0.8",
                "newmtl amber_mark", "Kd 1.0 0.62 0.12", "Ke 0.65 0.28 0.02",
            ]
        ),
        encoding="utf-8",
    )
    with OBJ_PATH.open("w", encoding="utf-8") as f:
        f.write("mtllib pet_g.mtl\n")
        f.write("# Pet G procedural companion fallback mesh\n")
        current = None
        for vertex in mesh.vertices:
            f.write(f"v {vertex[0]:.5f} {vertex[1]:.5f} {vertex[2]:.5f}\n")
        for material, indices in mesh.faces:
            if material.startswith("o "):
                f.write(f"{material}\n")
                continue
            if material != current:
                f.write(f"usemtl {material}\n")
                current = material
            f.write("f " + " ".join(str(i) for i in indices) + "\n")

    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "name": "Pet G",
                "source": "procedural",
                "authoring": {
                    "fallback_obj": "pet_g.obj",
                    "blender_generator": "make_pet_g_blender.py",
                    "intended_blender_outputs": ["pet_g.blend", "pet_g.glb", "pet_g_preview.png"],
                },
                "style": "small friendly graphite robot companion with glowing cyan eyes and amber G chest mark",
                "scale_meters": {"height": 3.25, "width": 2.1, "depth": 1.1},
                "runtime_notes": "Use pet_g.glb from Blender when available; pet_g.obj is a non-animated fallback mesh.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    build()
