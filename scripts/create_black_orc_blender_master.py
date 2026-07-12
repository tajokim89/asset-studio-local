#!/usr/bin/env python3
"""Build a detailed, rig-ready black orc master and render an SE approval image."""

from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "generated" / "black_orc_blender_master"
BLEND_PATH = OUT / "black_orc_blender_master.blend"
RENDER_PATH = OUT / "black_orc_blender_master_se.png"
REPORT_PATH = OUT / "report.json"
REFERENCE_PATH = ROOT / "assets" / "generated" / "black_orc_se_v2" / "master" / "black_orc_se_direction_master.png"


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.materials, bpy.data.curves, bpy.data.meshes, bpy.data.armatures):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def material(name: str, color, roughness=0.65, metallic=0.0, texture_scale=0.0, texture_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    if texture_scale > 0 and texture_strength > 0:
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = texture_scale
        noise.inputs["Detail"].default_value = 4.0
        noise.inputs["Roughness"].default_value = 0.7
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = texture_strength
        bump.inputs["Distance"].default_value = 0.08
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return mat


def apply_material(obj, mat) -> None:
    obj.data.materials.append(mat)


def smooth(obj) -> None:
    if hasattr(obj.data, "polygons"):
        for polygon in obj.data.polygons:
            polygon.use_smooth = True


def ellipsoid(name, location, scale, mat, *, rotation=(0, 0, 0), segments=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=max(12, segments // 2), location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    smooth(obj)
    apply_material(obj, mat)
    return obj


def ellipsoid_between(name, start, end, radii, mat, *, segments=32):
    start = Vector(start)
    end = Vector(end)
    direction = end - start
    obj = ellipsoid(name, (start + end) / 2, (radii[0], radii[1], direction.length / 2), mat, segments=segments)
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    return obj


def bevel_cube(name, location, scale, mat, *, rotation=(0, 0, 0), bevel=0.08):
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    modifier = obj.modifiers.new("Soft leather edges", "BEVEL")
    modifier.width = bevel
    modifier.segments = 3
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    smooth(obj)
    apply_material(obj, mat)
    return obj


def cone_between(name, start, end, radius_start, radius_end, mat, vertices=24):
    start = Vector(start)
    end = Vector(end)
    direction = end - start
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=radius_start,
        radius2=radius_end,
        depth=direction.length,
        location=(start + end) / 2,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    smooth(obj)
    apply_material(obj, mat)
    return obj


def curve_strip(name, points, radius, mat, bevel_resolution=3):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = radius
    curve.bevel_resolution = bevel_resolution
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for point, coordinate in zip(spline.bezier_points, points):
        point.co = coordinate
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    apply_material(obj, mat)
    return obj


def leather_panel(name, vertices, mat, thickness=0.08, bevel=0.045):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], [list(range(len(vertices)))])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    solidify = obj.modifiers.new("Leather thickness", "SOLIDIFY")
    solidify.thickness = thickness
    solidify.offset = 0
    edge = obj.modifiers.new("Worn rounded edge", "BEVEL")
    edge.width = bevel
    edge.segments = 3
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=solidify.name)
    bpy.ops.object.modifier_apply(modifier=edge.name)
    smooth(obj)
    apply_material(obj, mat)
    return obj


def bone_parent(obj, rig, bone_name: str) -> None:
    world = obj.matrix_world.copy()
    obj.parent = rig
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    obj.matrix_world = world


def create_rig():
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    rig = bpy.context.object
    rig.name = "BlackOrc_Rig"
    rig.show_in_front = True
    bones = rig.data.edit_bones
    bones.remove(bones[0])

    def add(name, head, tail, parent=None):
        bone = bones.new(name)
        bone.head = head
        bone.tail = tail
        bone.parent = parent
        return bone

    root = add("root", (0, 0, 0.15), (0, 0, 1.0))
    pelvis = add("pelvis", (0, 0, 2.9), (0, 0, 3.65), root)
    spine = add("spine", (0, 0, 3.55), (0, 0, 5.35), pelvis)
    neck = add("neck", (0, 0, 5.25), (0, -0.02, 6.0), spine)
    head = add("head", (0, -0.02, 5.85), (0, -0.05, 6.85), neck)
    upper_arm_l = add("upper_arm.L", (0.8, 0, 5.05), (1.42, -0.02, 4.05), spine)
    forearm_l = add("forearm.L", upper_arm_l.tail, (1.6, -0.06, 3.12), upper_arm_l)
    hand_l = add("hand.L", forearm_l.tail, (1.62, -0.2, 2.62), forearm_l)
    upper_arm_r = add("upper_arm.R", (-0.8, 0, 5.05), (-1.42, -0.02, 4.05), spine)
    forearm_r = add("forearm.R", upper_arm_r.tail, (-1.6, -0.06, 3.12), upper_arm_r)
    hand_r = add("hand.R", forearm_r.tail, (-1.62, -0.2, 2.62), forearm_r)
    thigh_l = add("thigh.L", (0.48, 0, 3.05), (0.52, 0.02, 1.8), pelvis)
    shin_l = add("shin.L", thigh_l.tail, (0.52, -0.02, 0.72), thigh_l)
    foot_l = add("foot.L", shin_l.tail, (0.52, -0.62, 0.28), shin_l)
    thigh_r = add("thigh.R", (-0.48, 0, 3.05), (-0.52, 0.02, 1.8), pelvis)
    shin_r = add("shin.R", thigh_r.tail, (-0.52, -0.02, 0.72), thigh_r)
    foot_r = add("foot.R", shin_r.tail, (-0.52, -0.62, 0.28), shin_r)
    bpy.ops.object.mode_set(mode="POSE")
    for pose_bone in rig.pose.bones:
        pose_bone.rotation_mode = "XYZ"
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def build_orc(rig):
    skin = material("Charcoal black skin", (0.035, 0.045, 0.055), 0.58, texture_scale=7.0, texture_strength=0.12)
    skin_high = material("Skin highlight", (0.085, 0.1, 0.115), 0.52, texture_scale=9.0, texture_strength=0.08)
    skin_dark = material("Skin shadow", (0.018, 0.022, 0.028), 0.7)
    leather = material("Warm brown leather", (0.19, 0.075, 0.025), 0.72, texture_scale=13.0, texture_strength=0.18)
    leather_dark = material("Dark worn leather", (0.075, 0.03, 0.014), 0.8, texture_scale=15.0, texture_strength=0.14)
    leather_edge = material("Leather edge", (0.31, 0.135, 0.045), 0.62, texture_scale=18.0, texture_strength=0.08)
    trousers = material("Brown cloth", (0.095, 0.052, 0.028), 0.9, texture_scale=28.0, texture_strength=0.16)
    bronze = material("Worn bronze", (0.34, 0.16, 0.055), 0.34, metallic=0.72, texture_scale=9.0, texture_strength=0.08)
    ivory = material("Warm tusk ivory", (0.78, 0.62, 0.38), 0.48, texture_scale=8.0, texture_strength=0.05)
    eye = material("Amber eyes", (0.95, 0.24, 0.015), 0.22, metallic=0.05)
    black = material("Eye and hair black", (0.003, 0.004, 0.005), 0.72)

    parts = []

    def add(obj, bone):
        bone_parent(obj, rig, bone)
        parts.append(obj)
        return obj

    # Pelvis and massive torso anatomy underneath the clothing.
    add(ellipsoid("Pelvis mass", (0, 0.02, 3.18), (0.78, 0.52, 0.58), skin_dark), "pelvis")
    add(ellipsoid("Ribcage", (0, 0.02, 4.55), (1.28, 0.66, 1.30), skin), "spine")
    add(ellipsoid("Left pectoral", (0.47, -0.49, 4.88), (0.62, 0.25, 0.45), skin_high), "spine")
    add(ellipsoid("Right pectoral", (-0.47, -0.49, 4.88), (0.62, 0.25, 0.45), skin_high), "spine")
    add(ellipsoid("Left trapezius", (0.43, 0.0, 5.25), (0.72, 0.46, 0.38), skin), "spine")
    add(ellipsoid("Right trapezius", (-0.43, 0.0, 5.25), (0.72, 0.46, 0.38), skin), "spine")
    add(ellipsoid("Neck", (0, 0.0, 5.62), (0.48, 0.43, 0.58), skin), "neck")

    # Head, heavy jaw and layered facial planes.
    add(ellipsoid("Skull", (0, -0.01, 6.34), (0.58, 0.51, 0.66), skin), "head")
    add(ellipsoid("Heavy jaw", (0, -0.43, 6.04), (0.66, 0.34, 0.43), skin), "head")
    add(ellipsoid("Chin", (0, -0.61, 5.87), (0.44, 0.20, 0.24), skin_dark), "head")
    add(ellipsoid("Broad nose", (0, -0.62, 6.31), (0.25, 0.19, 0.22), skin_high), "head")
    add(ellipsoid("Left nostril", (0.10, -0.758, 6.27), (0.045, 0.022, 0.035), black, segments=20), "head")
    add(ellipsoid("Right nostril", (-0.10, -0.758, 6.27), (0.045, 0.022, 0.035), black, segments=20), "head")
    add(ellipsoid("Brow ridge", (0, -0.51, 6.54), (0.55, 0.18, 0.12), skin_dark, rotation=(math.radians(-3), 0, 0)), "head")
    for x in (-0.22, 0.22):
        add(ellipsoid(f"Eye socket {x}", (x, -0.655, 6.47), (0.145, 0.06, 0.085), black, segments=20), "head")
        add(ellipsoid(f"Amber eye {x}", (x, -0.713, 6.475), (0.050, 0.020, 0.026), eye, segments=20), "head")
    add(bevel_cube("Lower lip", (0, -0.735, 6.08), (0.31, 0.055, 0.055), skin_dark, bevel=0.04), "head")
    add(cone_between("Left tusk", (-0.30, -0.67, 6.00), (-0.31, -0.78, 6.34), 0.105, 0.015, ivory), "head")
    add(cone_between("Right tusk", (0.30, -0.67, 6.00), (0.31, -0.78, 6.34), 0.105, 0.015, ivory), "head")
    left_ear = add(cone_between("Left ear", (-0.46, 0.00, 6.42), (-1.12, 0.10, 6.47), 0.22, 0.025, skin), "head")
    right_ear = add(cone_between("Right ear", (0.46, 0.00, 6.42), (1.12, 0.10, 6.47), 0.22, 0.025, skin), "head")
    left_ear.scale.y = 0.45
    right_ear.scale.y = 0.45
    add(cone_between("Left ear inset", (-0.55, -0.09, 6.42), (-1.00, -0.02, 6.46), 0.10, 0.012, skin_dark), "head")
    add(cone_between("Right ear inset", (0.55, -0.09, 6.42), (1.00, -0.02, 6.46), 0.10, 0.012, skin_dark), "head")

    # Segmented muscular arms and readable hands.
    arm_data = {
        "L": ((0.83, 0, 5.02), (1.43, -0.02, 4.08), (1.60, -0.08, 3.12), 1),
        "R": ((-0.83, 0, 5.02), (-1.43, -0.02, 4.08), (-1.60, -0.08, 3.12), -1),
    }
    for side, (shoulder, elbow, wrist, sign) in arm_data.items():
        add(ellipsoid(f"{side} deltoid", shoulder, (0.54, 0.51, 0.58), skin_high), f"upper_arm.{side}")
        add(ellipsoid_between(f"{side} biceps", shoulder, elbow, (0.43, 0.40), skin), f"upper_arm.{side}")
        add(ellipsoid(f"{side} biceps peak", (1.18 * sign, -0.22, 4.53), (0.38, 0.25, 0.42), skin_high), f"upper_arm.{side}")
        add(ellipsoid_between(f"{side} forearm", elbow, wrist, (0.36, 0.32), skin), f"forearm.{side}")
        add(ellipsoid(f"{side} forearm ridge", (1.53 * sign, -0.23, 3.55), (0.28, 0.20, 0.42), skin_high), f"forearm.{side}")
        palm = (1.61 * sign, -0.13, 2.86)
        add(ellipsoid(f"{side} palm", palm, (0.30, 0.22, 0.40), skin), f"hand.{side}")
        for index in range(4):
            x = palm[0] + sign * (-0.19 + index * 0.12)
            add(ellipsoid(f"{side} finger {index}", (x, -0.24, 2.57), (0.065, 0.08, 0.21), skin_dark, segments=20), f"hand.{side}")
        add(ellipsoid(f"{side} thumb", (palm[0] - sign * 0.25, -0.27, 2.87), (0.09, 0.09, 0.22), skin_dark, rotation=(0, math.radians(35) * sign, 0), segments=20), f"hand.{side}")

    # Leather vest panels, piping and lacing.
    add(ellipsoid("Vest torso", (0, -0.30, 4.23), (1.08, 0.36, 0.91), leather), "spine")
    add(leather_panel("Left shaped vest panel", [(-1.02, -0.69, 4.05), (-0.92, -0.68, 5.17), (-0.66, -0.71, 5.42), (-0.03, -0.79, 4.47), (-0.08, -0.77, 4.03)], leather), "spine")
    add(leather_panel("Right shaped vest panel", [(1.02, -0.69, 4.05), (0.92, -0.68, 5.17), (0.66, -0.71, 5.42), (0.03, -0.79, 4.47), (0.08, -0.77, 4.03)], leather), "spine")
    add(curve_strip("Vest neckline", [(-0.72, -0.76, 5.19), (0, -0.84, 4.55), (0.72, -0.76, 5.19)], 0.045, leather_edge), "spine")
    for index, z in enumerate((4.52, 4.30, 4.08)):
        add(curve_strip(f"Vest lace {index}", [(-0.13, -0.78, z + 0.07), (0.13, -0.78, z - 0.07)], 0.027, leather_edge, 2), "spine")

    # Belt, buckle and layered skirt tabs.
    add(bevel_cube("Belt", (0, -0.15, 3.48), (1.04, 0.52, 0.13), leather_dark, bevel=0.07), "pelvis")
    add(bevel_cube("Buckle outer", (0, -0.72, 3.49), (0.30, 0.07, 0.27), bronze, bevel=0.045), "pelvis")
    add(bevel_cube("Buckle inset", (0, -0.795, 3.49), (0.17, 0.025, 0.14), black, bevel=0.025), "pelvis")
    add(bevel_cube("Buckle tongue", (0.02, -0.825, 3.49), (0.16, 0.025, 0.025), bronze, bevel=0.015), "pelvis")
    for index, x in enumerate((-0.76, -0.38, 0, 0.38, 0.76)):
        add(bevel_cube(f"Leather skirt tab {index}", (x, -0.31, 3.00), (0.21, 0.28, 0.52), leather, rotation=(0, math.radians(x * 6), math.radians(-x * 5)), bevel=0.06), "pelvis")

    # Trousers, boot shafts, cuffs and large grounded feet.
    leg_data = {
        "L": ((0.48, 0, 3.05), (0.52, 0, 1.78), (0.52, -0.02, 0.72), 1),
        "R": ((-0.48, 0, 3.05), (-0.52, 0, 1.78), (-0.52, -0.02, 0.72), -1),
    }
    for side, (hip, knee, ankle, sign) in leg_data.items():
        add(ellipsoid_between(f"{side} trouser thigh", hip, knee, (0.51, 0.46), trousers), f"thigh.{side}")
        add(ellipsoid_between(f"{side} trouser calf", knee, ankle, (0.40, 0.37), trousers), f"shin.{side}")
        add(bevel_cube(f"{side} boot cuff", (0.52 * sign, -0.01, 1.48), (0.43, 0.38, 0.18), leather, bevel=0.08), f"shin.{side}")
        add(ellipsoid(f"{side} boot shaft", (0.52 * sign, -0.05, 0.89), (0.38, 0.35, 0.66), leather_dark), f"shin.{side}")
        add(bevel_cube(f"{side} boot foot", (0.52 * sign, -0.40, 0.31), (0.40, 0.61, 0.26), leather, bevel=0.15), f"foot.{side}")
        add(bevel_cube(f"{side} boot sole", (0.52 * sign, -0.43, 0.12), (0.43, 0.66, 0.075), leather_dark, bevel=0.05), f"foot.{side}")
        add(ellipsoid(f"{side} toe cap", (0.52 * sign, -0.83, 0.35), (0.39, 0.34, 0.23), leather_edge), f"foot.{side}")
        for band_index, y in enumerate((-0.16, -0.41, -0.66)):
            add(curve_strip(f"{side} boot seam {band_index}", [(0.17 * sign, y, 0.48), (0.52 * sign, y - 0.05, 0.57), (0.87 * sign, y, 0.48)], 0.025, leather_dark, 2), f"foot.{side}")

    return parts


def configure_scene(rig):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.film_transparent = True
    scene.render.resolution_x = 768
    scene.render.resolution_y = 768
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = str(RENDER_PATH)
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.world.color = (0.008, 0.008, 0.012)

    target = Vector((0, -0.10, 3.45))
    camera_data = bpy.data.cameras.new("SE_Orthographic_Camera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 7.65
    camera = bpy.data.objects.new("SE_Orthographic_Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (7.8, -10.5, 6.3)
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera

    def area(name, location, energy, color, size):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.color = color
        data.shape = "DISK"
        data.size = size
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        obj.location = location
        obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()
        return obj

    area("Warm key", (5.5, -7.0, 9.0), 1250, (1.0, 0.72, 0.50), 5.0)
    area("Cool fill", (-5.0, -4.0, 5.5), 720, (0.38, 0.55, 1.0), 4.0)
    area("Rim", (-2.0, 4.5, 8.5), 1450, (0.55, 0.70, 1.0), 3.5)
    rig.hide_render = True
    return camera


def validate(parts) -> dict:
    image = Image.open(RENDER_PATH).convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise RuntimeError("render is empty")
    coverage = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / (image.width * image.height)
    required_names = {
        "Skull", "Heavy jaw", "Left tusk", "Right tusk", "Left pectoral", "Right pectoral",
        "Warm brown leather", "Buckle outer", "L boot foot", "R boot foot", "L palm", "R palm",
    }
    available = {obj.name for obj in parts} | {mat.name for mat in bpy.data.materials}
    missing = sorted(required_names - available)
    report = {
        "passed": not missing and len(parts) >= 80 and 0.30 <= coverage <= 0.82,
        "reference": str(REFERENCE_PATH),
        "blend": str(BLEND_PATH),
        "render": str(RENDER_PATH),
        "render_size": [image.width, image.height],
        "alpha_bbox": list(bbox),
        "bbox_coverage": round(coverage, 4),
        "rig_bones": len(bpy.data.objects["BlackOrc_Rig"].data.bones),
        "visible_parts": len(parts),
        "missing_required_parts": missing,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError(f"black orc master validation failed: {report}")
    return report


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    clear_scene()
    rig = create_rig()
    parts = build_orc(rig)
    configure_scene(rig)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    bpy.ops.render.render(write_still=True)
    print("BLACK_ORC_BLENDER_MASTER", json.dumps(validate(parts)))


if __name__ == "__main__":
    main()
