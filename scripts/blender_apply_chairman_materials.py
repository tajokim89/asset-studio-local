"""Apply a stable game-ready chairman palette to the rigged character mesh.

The source model is a single watertight mesh, so material regions are selected
from rest-pose bone weights and local surface position. This keeps clothing,
skin, hair, patches, and shoes identical across every animation frame.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import bpy


def arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--glb-output", required=True, type=Path)
    return parser.parse_args(values)


def srgb_channel(value: int) -> float:
    channel = value / 255.0
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def rgba(hex_color: str) -> tuple[float, float, float, float]:
    value = hex_color.removeprefix("#")
    red, green, blue = (int(value[index : index + 2], 16) for index in (0, 2, 4))
    return srgb_channel(red), srgb_channel(green), srgb_channel(blue), 1.0


def material(name: str, hex_color: str, roughness: float = 0.82) -> bpy.types.Material:
    current = bpy.data.materials.get(name)
    if current is None:
        current = bpy.data.materials.new(name)
    current.use_nodes = True
    current.diffuse_color = rgba(hex_color)
    current.roughness = roughness
    nodes = current.node_tree.nodes
    shader = nodes.get("Principled BSDF")
    if shader is None:
        shader = next((node for node in nodes if node.type == "BSDF_PRINCIPLED"), None)
    if shader is not None:
        shader.inputs["Base Color"].default_value = rgba(hex_color)
        shader.inputs["Roughness"].default_value = roughness
        shader.inputs["Metallic"].default_value = 0.0
        if "Specular IOR Level" in shader.inputs:
            shader.inputs["Specular IOR Level"].default_value = 0.28
    return current


def dominant_group(mesh: bpy.types.Object, polygon: bpy.types.MeshPolygon) -> str:
    weights: defaultdict[str, float] = defaultdict(float)
    for vertex_index in polygon.vertices:
        for membership in mesh.data.vertices[vertex_index].groups:
            weights[mesh.vertex_groups[membership.group].name] += membership.weight
    return max(weights, key=weights.get) if weights else ""


def local_center(mesh: bpy.types.Object, polygon: bpy.types.MeshPolygon):
    center = sum((mesh.data.vertices[index].co for index in polygon.vertices), mesh.location.copy() * 0.0)
    return center / len(polygon.vertices)


def choose_material(center, group: str) -> str:
    x, y, z = center
    arm = group.startswith(("clavicle_", "upperarm_", "elbow_", "lowerarm_"))
    leg = group.startswith(("pelvis", "thigh_", "calf_"))

    if group.startswith(("foot_", "ball_")) or z < -0.79:
        return "Chairman Shoes"
    if group.startswith("hand_") or (arm and abs(x) > 0.79):
        return "Chairman Skin"
    if group == "Head":
        if z < 0.72 and abs(x) > 0.16:
            return "Chairman Shirt"
        if z < 0.67:
            if abs(x) < 0.10 and z > 0.58:
                return "Chairman Skin"
            if y < -0.055 and z > 0.48 and abs(x) < 0.27:
                return "Chairman Shirt"
            return "Chairman Jacket"
        if z > 0.91 or (z > 0.86 and (y > -0.015 or abs(x) > 0.20)):
            return "Chairman Hair"
        return "Chairman Skin"
    if group == "neck_01":
        if z > 0.63 and abs(x) < 0.10:
            return "Chairman Skin"
        if y < -0.055 and z > 0.48 and abs(x) < 0.27:
            return "Chairman Shirt"
        return "Chairman Jacket"
    if group == "pelvis" and z > 0.0:
        return "Chairman Jacket"
    if leg:
        if -0.26 < x < -0.07 and y < -0.08 and -0.56 < z < -0.32:
            return "Chairman Cloth Patch"
        return "Chairman Pants"
    if arm:
        if 0.70 < abs(x) < 0.79:
            return "Chairman Shirt"
        if 0.48 < abs(x) < 0.64 and y < -0.07 and 0.20 < z < 0.43:
            return "Chairman Cloth Patch"
        return "Chairman Jacket"

    # The collar and lapels are the front-most surfaces around the neck.
    if y < -0.13 and 0.49 < z < 0.60 and abs(x) < 0.13:
        return "Chairman Shirt"
    # A narrow dark strip preserves the visible button/seam rhythm at sprite size.
    if y < -0.175 and -0.04 < z < 0.34 and abs(x) < 0.050:
        return "Chairman Buttons"
    return "Chairman Jacket"


def apply_palette(mesh: bpy.types.Object) -> Counter[str]:
    palette = (
        material("Chairman Hair", "#0B0D15", 0.76),
        material("Chairman Skin", "#B76B3F", 0.68),
        material("Chairman Jacket", "#182342", 0.88),
        material("Chairman Shirt", "#9C7A55", 0.90),
        material("Chairman Pants", "#292526", 0.93),
        material("Chairman Shoes", "#171820", 0.84),
        material("Chairman Cloth Patch", "#6B5748", 0.95),
        material("Chairman Buttons", "#332B2A", 0.78),
    )
    mesh.data.materials.clear()
    for current in palette:
        mesh.data.materials.append(current)
    indices = {current.name: index for index, current in enumerate(palette)}

    counts: Counter[str] = Counter()
    for polygon in mesh.data.polygons:
        name = choose_material(local_center(mesh, polygon), dominant_group(mesh, polygon))
        polygon.material_index = indices[name]
        counts[name] += 1
    return counts


def export_glb(output: Path, mesh: bpy.types.Object, rig: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(output),
        export_format="GLB",
        use_selection=True,
        export_materials="EXPORT",
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_frame_range=False,
        export_force_sampling=True,
        export_skins=True,
    )


def main() -> None:
    args = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(args.input.resolve()))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj.name != "PreviewGround"]
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(meshes) != 1 or len(rigs) != 1:
        raise RuntimeError(f"Expected one character mesh and one armature, got {len(meshes)} meshes and {len(rigs)} rigs")

    mesh, rig = meshes[0], rigs[0]
    counts = apply_palette(mesh)
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    export_glb(args.glb_output.resolve(), mesh, rig)
    print(
        "CHAIRMAN_MATERIALS="
        + json.dumps(
            {
                "blend": str(args.output.resolve()),
                "glb": str(args.glb_output.resolve()),
                "polygons": dict(counts),
                "actions": [action.name for action in bpy.data.actions],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
