#!/usr/bin/env python3
"""Validate Sprite Sheet Maker with a procedural rig in Blender background mode."""

from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector
from PIL import Image

from bl_ext.user_default.sprite_sheet_maker.modules.combine_frames import (
    CombineMode,
    SpriteAlign,
    SpriteConsistency,
)
from bl_ext.user_default.sprite_sheet_maker.modules.sprite_sheet_utils import (
    FrameSelectionMode,
    RowParam,
    SpriteSheetMaker,
    SpriteSheetParam,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "generated" / "blender_sprite_sheet_maker_validation"
SHEET = OUT / "procedural_actor_sheet.png"
REPORT = OUT / "report.json"
SCENE = OUT / "procedural_actor.blend"
FRAME_COUNT = 4
ROW_COUNT = 3
CELL_SIZE = 64


def material(name: str, color: tuple[float, float, float, float]):
    value = bpy.data.materials.new(name)
    value.diffuse_color = color
    return value


def bone_parent(obj, armature, bone_name: str) -> None:
    world = obj.matrix_world.copy()
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    obj.matrix_world = world


def cube(name, location, scale, mat, armature, bone_name):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    bone_parent(obj, armature, bone_name)
    return obj


def sphere(name, location, scale, mat, armature, bone_name):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    bone_parent(obj, armature, bone_name)
    return obj


def create_actor():
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    armature = bpy.context.object
    armature.name = "ProceduralOrcRig"
    bones = armature.data.edit_bones
    bones.remove(bones[0])

    def add_bone(name, head, tail, parent=None):
        value = bones.new(name)
        value.head = head
        value.tail = tail
        value.parent = parent
        return value

    root = add_bone("root", (0, 0, 0), (0, 0, 1))
    torso = add_bone("torso", (0, 0, 1), (0, 0, 2), root)
    head = add_bone("head", (0, 0, 2), (0, 0, 2.65), torso)
    add_bone("arm.L", (0.55, 0, 1.85), (1.15, 0, 1.05), torso)
    add_bone("arm.R", (-0.55, 0, 1.85), (-1.15, 0, 1.05), torso)
    add_bone("leg.L", (0.3, 0, 1.0), (0.3, 0, 0.05), root)
    add_bone("leg.R", (-0.3, 0, 1.0), (-0.3, 0, 0.05), root)
    bpy.ops.object.mode_set(mode="POSE")
    for pose_bone in armature.pose.bones:
        pose_bone.rotation_mode = "XYZ"
    bpy.ops.object.mode_set(mode="OBJECT")

    skin = material("CharcoalSkin", (0.055, 0.07, 0.09, 1))
    leather = material("BrownLeather", (0.24, 0.105, 0.035, 1))
    eye = material("GoldEyeMarker", (1.0, 0.32, 0.015, 1))
    parts = [
        cube("Torso", (0, 0, 1.5), (0.58, 0.33, 0.55), leather, armature, "torso"),
        sphere("Head", (0, -0.03, 2.33), (0.43, 0.38, 0.43), skin, armature, "head"),
        cube("ArmL", (0.82, 0, 1.43), (0.19, 0.2, 0.55), skin, armature, "arm.L"),
        cube("ArmR", (-0.82, 0, 1.43), (0.19, 0.2, 0.55), skin, armature, "arm.R"),
        cube("LegL", (0.3, 0, 0.53), (0.23, 0.25, 0.48), leather, armature, "leg.L"),
        cube("LegR", (-0.3, 0, 0.53), (0.23, 0.25, 0.48), leather, armature, "leg.R"),
        sphere("EyeMarker", (0.17, -0.37, 2.39), (0.075, 0.035, 0.055), eye, armature, "head"),
    ]
    return armature, parts


def reset_pose(armature) -> None:
    for bone in armature.pose.bones:
        bone.location = (0, 0, 0)
        bone.rotation_euler = (0, 0, 0)
        bone.scale = (1, 1, 1)


def create_action(armature, name: str, poses: list[dict[str, tuple]]) -> bpy.types.Action:
    action = bpy.data.actions.new(name)
    armature.animation_data_create()
    armature.animation_data.action = action
    for frame, pose in enumerate(poses, start=1):
        reset_pose(armature)
        for bone_name, values in pose.items():
            bone = armature.pose.bones[bone_name]
            if "rotation" in values:
                bone.rotation_euler = values["rotation"]
            if "location" in values:
                bone.location = values["location"]
        for bone in armature.pose.bones:
            bone.keyframe_insert("rotation_euler", frame=frame, group=bone.name)
            bone.keyframe_insert("location", frame=frame, group=bone.name)
    armature.animation_data.action = None
    return action


def create_actions(armature):
    deg = math.radians
    idle = create_action(
        armature,
        "Idle",
        [
            {},
            {"torso": {"location": (0, 0, 0.025)}},
            {},
            {"torso": {"location": (0, 0, -0.02)}},
        ],
    )
    walk = create_action(
        armature,
        "Walk",
        [
            {"leg.L": {"rotation": (deg(30), 0, 0)}, "leg.R": {"rotation": (deg(-30), 0, 0)},
             "arm.L": {"rotation": (deg(-22), 0, 0)}, "arm.R": {"rotation": (deg(22), 0, 0)}},
            {"root": {"location": (0, 0, 0.035)}},
            {"leg.L": {"rotation": (deg(-30), 0, 0)}, "leg.R": {"rotation": (deg(30), 0, 0)},
             "arm.L": {"rotation": (deg(22), 0, 0)}, "arm.R": {"rotation": (deg(-22), 0, 0)}},
            {"root": {"location": (0, 0, 0.035)}},
        ],
    )
    attack = create_action(
        armature,
        "Attack",
        [
            {"torso": {"rotation": (0, 0, deg(10))}, "arm.R": {"rotation": (deg(-50), 0, deg(-20))}},
            {"torso": {"rotation": (0, 0, deg(-12))}, "arm.R": {"rotation": (deg(55), 0, deg(35))}},
            {"torso": {"rotation": (0, 0, deg(-18))}, "arm.R": {"rotation": (deg(75), 0, deg(45))}},
            {},
        ],
    )
    return idle, walk, attack


def configure_render() -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.resolution_x = CELL_SIZE
    scene.render.resolution_y = CELL_SIZE
    scene.render.resolution_percentage = 100
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.view_settings.look = "AgX - Medium High Contrast"


def create_fixed_camera(armature):
    head = Vector((0, 0, 2))
    desired_location = Vector((4, -4, 3.4))
    camera_data = bpy.data.cameras.new("Fixed64Camera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 3.45
    camera = bpy.data.objects.new("Fixed64Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = desired_location - head
    camera.rotation_euler = (head - desired_location).to_track_quat("-Z", "Y").to_euler()
    follow = camera.constraints.new("COPY_LOCATION")
    follow.target = armature
    follow.subtarget = "head"
    follow.use_offset = True
    bpy.context.scene.camera = camera
    return camera


def build_sheet(armature, parts, actions, camera) -> None:
    params = SpriteSheetParam()
    params.delete_temp_folder = True
    for action in actions:
        row = RowParam()
        row.label = action.name
        row.capture_items = [(armature, action, ""), (camera, None, "")] + [
            (part, None, "") for part in parts
        ]
        row.custom_camera = camera
        row.to_auto_capture = False
        row.frame_selection_mode = FrameSelectionMode.ALL_FRAMES
        params.animation_rows.append(row)

    assemble = params.assemble_param
    assemble.combine_mode = CombineMode.SHEET
    assemble.consistency = SpriteConsistency.ALL
    assemble.align = SpriteAlign.MIDDLE_CENTER
    assemble.font_size = 0
    assemble.surrounding_margin = (0, 0, 0, 0)
    assemble.label_margin = 0
    assemble.image_margin = 0
    SpriteSheetMaker().create_sprite_sheet(params, str(SHEET))


def validate_sheet() -> dict:
    image = Image.open(SHEET).convert("RGBA")
    cell_width = image.width // FRAME_COUNT
    cell_height = image.height // ROW_COUNT
    frames = []
    top_edges = []
    for row in range(ROW_COUNT):
        for column in range(FRAME_COUNT):
            cell = image.crop((
                column * cell_width,
                row * cell_height,
                (column + 1) * cell_width,
                (row + 1) * cell_height,
            ))
            alpha_box = cell.getchannel("A").getbbox()
            if alpha_box is None:
                raise RuntimeError(f"empty sprite at row={row}, frame={column}")
            top_edges.append(alpha_box[1])
            frames.append({"row": row, "frame": column, "alpha_bbox": alpha_box})
    report = {
        "passed": (
            len(frames) == ROW_COUNT * FRAME_COUNT
            and [cell_width, cell_height] == [CELL_SIZE, CELL_SIZE]
            and max(top_edges) - min(top_edges) <= 2
        ),
        "sheet": str(SHEET),
        "scene": str(SCENE),
        "sheet_size": [image.width, image.height],
        "cell_size": [cell_width, cell_height],
        "frame_count": len(frames),
        "head_anchor_top_edge_spread_px": max(top_edges) - min(top_edges),
        "frames": frames,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError(f"Sprite Sheet Maker validation failed: {report}")
    return report


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    configure_render()
    armature, parts = create_actor()
    actions = create_actions(armature)
    camera = create_fixed_camera(armature)
    build_sheet(armature, parts, actions, camera)
    bpy.ops.wm.save_as_mainfile(filepath=str(SCENE))
    print("SPRITE_SHEET_MAKER_VALIDATION", json.dumps(validate_sheet()))


if __name__ == "__main__":
    main()
