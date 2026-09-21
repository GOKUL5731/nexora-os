"""Create the authored Pet G Blender asset.

Run with Blender:
  blender --background --python make_pet_g_blender.py

Outputs:
  pet_g.blend
  pet_g.glb
  pet_g_preview.png
"""

from __future__ import annotations

from pathlib import Path
import math

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent


def mat(name, color, metallic=0.0, roughness=0.45, emission=None, strength=0.0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        if emission:
            bsdf.inputs["Emission Color"].default_value = emission
            bsdf.inputs["Emission Strength"].default_value = strength
    return material


def add_uv(name, loc, scale, material, segments=48, rings=24):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return obj


def add_cube(name, loc, scale, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    bevel = obj.modifiers.new("soft bevel", "BEVEL")
    bevel.width = 0.018
    bevel.segments = 3
    obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def add_cylinder(name, loc, radius, depth, material, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=36, radius=radius, depth=depth, location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return obj


def main():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.context.scene.unit_settings.system = "METRIC"

    body = mat("graphite ceramic body", (0.035, 0.04, 0.052, 1), metallic=0.15, roughness=0.34)
    trim = mat("smoked titanium trim", (0.38, 0.42, 0.46, 1), metallic=0.75, roughness=0.26)
    glow = mat("cyan optical glow", (0.15, 0.82, 1.0, 1), emission=(0.05, 0.65, 1.0, 1), strength=2.8)
    amber = mat("amber G core", (1.0, 0.55, 0.08, 1), emission=(1.0, 0.35, 0.02, 1), strength=1.6)
    glass = mat("smoked face glass", (0.025, 0.04, 0.055, 0.62), metallic=0.0, roughness=0.08)

    root = bpy.data.collections.new("Pet G companion")
    bpy.context.scene.collection.children.link(root)

    parts = [
        add_uv("soft capsule body", (0, 0, 1.36), (0.72, 0.52, 0.92), body),
        add_uv("round display head", (0, -0.01, 2.35), (0.58, 0.50, 0.48), body),
        add_uv("smoked face glass", (0, -0.46, 2.38), (0.42, 0.045, 0.25), glass, 48, 12),
        add_uv("left cyan eye", (-0.2, -0.505, 2.43), (0.07, 0.025, 0.07), glow, 24, 12),
        add_uv("right cyan eye", (0.2, -0.505, 2.43), (0.07, 0.025, 0.07), glow, 24, 12),
        add_cylinder("left antenna stem", (-0.25, 0.02, 2.82), 0.025, 0.42, trim),
        add_cylinder("right antenna stem", (0.25, 0.02, 2.82), 0.025, 0.42, trim),
        add_uv("left antenna glow", (-0.25, 0.02, 3.06), (0.075, 0.075, 0.075), glow, 24, 12),
        add_uv("right antenna glow", (0.25, 0.02, 3.06), (0.075, 0.075, 0.075), glow, 24, 12),
        add_cylinder("left arm", (-0.70, -0.02, 1.48), 0.065, 0.62, body, (0, math.radians(90), 0)),
        add_cylinder("right arm", (0.70, -0.02, 1.48), 0.065, 0.62, body, (0, math.radians(90), 0)),
        add_uv("left titanium hand", (-1.03, -0.02, 1.48), (0.11, 0.11, 0.11), trim, 24, 12),
        add_uv("right titanium hand", (1.03, -0.02, 1.48), (0.11, 0.11, 0.11), trim, 24, 12),
        add_uv("left soft foot", (-0.32, -0.04, 0.45), (0.23, 0.18, 0.11), trim, 24, 12),
        add_uv("right soft foot", (0.32, -0.04, 0.45), (0.23, 0.18, 0.11), trim, 24, 12),
    ]
    parts.extend([
        add_cube("G mark vertical", (-0.18, -0.535, 1.48), (0.11, 0.035, 0.54), amber),
        add_cube("G mark top", (0.03, -0.535, 1.72), (0.43, 0.035, 0.11), amber),
        add_cube("G mark bottom", (0.03, -0.535, 1.24), (0.43, 0.035, 0.11), amber),
        add_cube("G mark middle", (0.10, -0.535, 1.48), (0.32, 0.035, 0.10), amber),
        add_cube("G mark hook", (0.30, -0.535, 1.36), (0.10, 0.035, 0.25), amber),
    ])

    for obj in parts:
        for coll in obj.users_collection:
            coll.objects.unlink(obj)
        root.objects.link(obj)

    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 1.6))
    rig_root = bpy.context.object
    rig_root.name = "Pet G runtime root"
    root.objects.link(rig_root)
    bpy.context.collection.objects.unlink(rig_root)
    for obj in parts:
        obj.parent = rig_root

    bpy.ops.object.light_add(type="AREA", location=(0, -4.0, 5.0))
    key = bpy.context.object
    key.name = "large softbox key"
    key.data.energy = 450
    key.data.size = 4
    bpy.ops.object.camera_add(location=(2.4, -4.2, 2.3), rotation=(math.radians(66), 0, math.radians(30)))
    bpy.context.scene.camera = bpy.context.object

    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=1.35, fill_type="TRIFAN", location=(0, 0, 0.31))
    base = bpy.context.object
    base.name = "small display base"
    base.data.materials.append(mat("matte charcoal base", (0.015, 0.016, 0.018, 1), roughness=0.62))

    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.samples = 96
    bpy.context.scene.view_settings.view_transform = "Filmic"
    bpy.context.scene.render.resolution_x = 1400
    bpy.context.scene.render.resolution_y = 1400
    bpy.context.scene.render.filepath = str(ROOT / "pet_g_preview.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "pet_g.blend"))
    bpy.ops.export_scene.gltf(filepath=str(ROOT / "pet_g.glb"), export_format="GLB", export_apply=True)
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
