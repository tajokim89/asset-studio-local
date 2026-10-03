"""Create a compact humanoid rig and export loopable Idle/Walk/Run GLB clips.

This script is executed by Blender, not by the regular Python interpreter.
It accepts either a static GLB or an existing rigged .blend.  Static humanoid
meshes are normalized, auto-weighted, animated in place, and exported as one
game-ready GLB containing all three actions.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


ACTION_NAMES = ("Idle", "Walk", "Run")


def parse_args() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--blend-output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--actions", default=",".join(ACTION_NAMES))
    return parser.parse_args(values)


def add_bone(
    armature: bpy.types.Armature,
    name: str,
    head: tuple[float, float, float],
    tail: tuple[float, float, float],
    parent: str | None = None,
    connected: bool = False,
) -> None:
    bone = armature.edit_bones.new(name)
    bone.head = head
    bone.tail = tail
    if parent:
        bone.parent = armature.edit_bones[parent]
        bone.use_connect = connected


def create_rig() -> bpy.types.Object:
    armature_data = bpy.data.armatures.new("AssetStudioRig")
    rig = bpy.data.objects.new("AssetStudioRig", armature_data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    add_bone(armature_data, "pelvis", (0, 0, -0.08), (0, 0, 0.10))
    add_bone(armature_data, "spine", (0, 0, 0.10), (0, 0, 0.34), "pelvis", True)
    add_bone(armature_data, "chest", (0, 0, 0.34), (0, 0, 0.55), "spine", True)
    add_bone(armature_data, "neck", (0, 0, 0.55), (0, 0, 0.68), "chest", True)
    add_bone(armature_data, "head", (0, 0, 0.68), (0, 0, 0.93), "neck", True)

    for side, sign in (("L", 1.0), ("R", -1.0)):
        hip_x = 0.115 * sign
        shoulder_x = 0.205 * sign
        add_bone(armature_data, f"thigh.{side}", (hip_x, 0, -0.05), (hip_x, 0, -0.43), "pelvis")
        add_bone(armature_data, f"shin.{side}", (hip_x, 0, -0.43), (hip_x, 0, -0.78), f"thigh.{side}", True)
        add_bone(armature_data, f"foot.{side}", (hip_x, 0, -0.78), (hip_x, -0.18, -0.86), f"shin.{side}", True)
        add_bone(armature_data, f"upper_arm.{side}", (shoulder_x, 0, 0.51), (0.39 * sign, 0, 0.27), "chest")
        add_bone(armature_data, f"forearm.{side}", (0.39 * sign, 0, 0.27), (0.49 * sign, 0, 0.03), f"upper_arm.{side}", True)
        add_bone(armature_data, f"hand.{side}", (0.49 * sign, 0, 0.03), (0.53 * sign, 0, -0.14), f"forearm.{side}", True)

    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def normalize_joined_mesh(meshes: list[bpy.types.Object]) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    for mesh in meshes:
        mesh.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    mesh = meshes[0]
    corners = [mesh.matrix_world @ Vector(corner) for corner in mesh.bound_box]
    lower = Vector((min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners)))
    upper = Vector((max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners)))
    height = upper.z - lower.z
    if height <= 1e-6:
        raise RuntimeError("The generated mesh has no usable height")
    center = (lower + upper) * 0.5
    scale = 2.0 / height
    world = mesh.matrix_world.copy()
    for vertex in mesh.data.vertices:
        vertex.co = (world @ vertex.co - center) * scale
    mesh.matrix_world = Matrix.Identity(4)
    mesh.data.update()
    return mesh


def auto_rig_imported_mesh(meshes: list[bpy.types.Object]) -> tuple[bpy.types.Object, list[bpy.types.Object]]:
    if not meshes:
        raise RuntimeError("The GLB contains no mesh objects")
    mesh = normalize_joined_mesh(meshes)
    rig = create_rig()
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    if not mesh.vertex_groups:
        raise RuntimeError("Blender automatic weights created no vertex groups")
    return rig, [mesh]


def load_source(source: Path) -> tuple[bpy.types.Object, list[bpy.types.Object]]:
    if source.suffix.lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(source))
        rigs = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
        meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
        if len(rigs) != 1 or not meshes:
            raise RuntimeError("The Blender source must contain one armature and at least one mesh")
        return rigs[0], meshes
    if source.suffix.lower() != ".glb":
        raise RuntimeError("Input must be a .glb or .blend file")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if len(rigs) == 1 and meshes:
        return rigs[0], meshes
    if rigs:
        raise RuntimeError("The GLB must contain at most one armature")
    return auto_rig_imported_mesh(meshes)


def reset_pose(rig: bpy.types.Object) -> None:
    for bone in rig.pose.bones:
        bone.rotation_mode = "XYZ"
        bone.location = (0.0, 0.0, 0.0)
        bone.rotation_euler = (0.0, 0.0, 0.0)
        bone.scale = (1.0, 1.0, 1.0)


def apply_pose(rig: bpy.types.Object, pose: dict[str, float]) -> None:
    reset_pose(rig)
    deg = math.radians
    pelvis = rig.pose.bones["pelvis"]
    pelvis.location.z = pose.get("bounce", 0.0)
    pelvis.rotation_euler.x = deg(pose.get("pelvis", 0.0))
    pelvis.rotation_euler.y = deg(pose.get("pelvis_y", 0.0))
    pelvis.rotation_euler.z = deg(pose.get("pelvis_z", 0.0))
    rig.pose.bones["chest"].rotation_euler.x = deg(pose.get("chest", -pose.get("pelvis", 0.0) * 0.55))
    rig.pose.bones["chest"].rotation_euler.z = deg(pose.get("chest_z", 0.0))
    rig.pose.bones["head"].rotation_euler.x = deg(pose.get("head", 0.0))
    for side, key in (("L", "l"), ("R", "r")):
        rig.pose.bones[f"thigh.{side}"].rotation_euler.x = deg(pose.get(f"thigh_{key}", 0.0))
        rig.pose.bones[f"shin.{side}"].rotation_euler.x = deg(pose.get(f"knee_{key}", 0.0))
        rig.pose.bones[f"foot.{side}"].rotation_euler.x = deg(pose.get(f"foot_{key}", 0.0))
        rig.pose.bones[f"upper_arm.{side}"].rotation_euler.x = deg(pose.get(f"arm_{key}", 0.0))
        rig.pose.bones[f"forearm.{side}"].rotation_euler.x = deg(pose.get(f"elbow_{key}", 0.0))


def key_pose(rig: bpy.types.Object, frame: int) -> None:
    for bone in rig.pose.bones:
        bone.keyframe_insert("rotation_euler", frame=frame, group=bone.name)
        bone.keyframe_insert("location", frame=frame, group=bone.name)
        bone.keyframe_insert("scale", frame=frame, group=bone.name)


def minimum_mesh_z(meshes: list[bpy.types.Object]) -> float:
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    minimum = float("inf")
    for mesh in meshes:
        evaluated = mesh.evaluated_get(depsgraph)
        world = evaluated.matrix_world
        minimum = min(minimum, min((world @ vertex.co).z for vertex in evaluated.data.vertices))
    return minimum


def create_action(
    rig: bpy.types.Object,
    name: str,
    poses: list[dict[str, float]],
    frame_step: int,
    interpolation: str,
    meshes: list[bpy.types.Object],
    ground_feet: bool,
    ground_z: float,
) -> bpy.types.Action:
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    action["asset_studio_loop"] = True
    rig.animation_data_create()
    rig.animation_data.action = action
    for index, pose in enumerate([*poses, poses[0]]):
        frame = 1 + index * frame_step
        apply_pose(rig, pose)
        if ground_feet:
            rig.pose.bones["pelvis"].location.z += ground_z - minimum_mesh_z(meshes) + pose.get("flight", 0.0)
            bpy.context.view_layer.update()
        key_pose(rig, frame)
    for fcurve in action.fcurves:
        for point in fcurve.keyframe_points:
            point.interpolation = interpolation
    action["asset_studio_duration_frames"] = len(poses) * frame_step
    rig.animation_data.action = None
    return action


def action_poses() -> dict[str, tuple[list[dict[str, float]], int, str]]:
    idle = [
        {"bounce": 0.000, "chest": 0.0, "head": 0.0, "arm_l": 2, "arm_r": -2},
        {"bounce": 0.012, "chest": -1.2, "head": 0.5, "arm_l": 1, "arm_r": -1},
        {"bounce": 0.020, "chest": -2.0, "head": 0.8, "arm_l": 0, "arm_r": 0},
        {"bounce": 0.010, "chest": -1.0, "head": 0.4, "arm_l": 1, "arm_r": -1},
    ]
    walk = [
        {"thigh_l": -25, "thigh_r": 23, "knee_l": 4, "knee_r": 12, "foot_l": 7, "foot_r": -8, "arm_l": 17, "arm_r": -17, "elbow_l": 14, "elbow_r": -14, "pelvis": -2},
        {"thigh_l": -14, "thigh_r": 15, "knee_l": 12, "knee_r": 28, "foot_l": 3, "foot_r": -1, "arm_l": 11, "arm_r": -11, "elbow_l": 16, "elbow_r": -16, "pelvis": -1},
        {"thigh_l": 2, "thigh_r": 1, "knee_l": 7, "knee_r": 43, "foot_l": -3, "foot_r": 13, "arm_l": 2, "arm_r": -2, "elbow_l": 17, "elbow_r": -17, "pelvis": 0},
        {"thigh_l": 17, "thigh_r": -11, "knee_l": 4, "knee_r": 29, "foot_l": -8, "foot_r": 8, "arm_l": -11, "arm_r": 11, "elbow_l": 15, "elbow_r": -15, "pelvis": 2},
        {"thigh_l": 23, "thigh_r": -25, "knee_l": 12, "knee_r": 4, "foot_l": -8, "foot_r": 7, "arm_l": -17, "arm_r": 17, "elbow_l": 14, "elbow_r": -14, "pelvis": 2},
        {"thigh_l": 15, "thigh_r": -14, "knee_l": 28, "knee_r": 12, "foot_l": -1, "foot_r": 3, "arm_l": -11, "arm_r": 11, "elbow_l": 16, "elbow_r": -16, "pelvis": 1},
        {"thigh_l": 1, "thigh_r": 2, "knee_l": 43, "knee_r": 7, "foot_l": 13, "foot_r": -3, "arm_l": -2, "arm_r": 2, "elbow_l": 17, "elbow_r": -17, "pelvis": 0},
        {"thigh_l": -11, "thigh_r": 17, "knee_l": 29, "knee_r": 4, "foot_l": 8, "foot_r": -8, "arm_l": 11, "arm_r": -11, "elbow_l": 15, "elbow_r": -15, "pelvis": -2},
    ]
    run = [
        {"thigh_l": -33, "thigh_r": 27, "knee_l": 7, "knee_r": 34, "foot_l": 10, "foot_r": -12, "arm_l": 27, "arm_r": -27, "elbow_l": 78, "elbow_r": -78, "pelvis": -7, "chest": 9, "head": -2},
        {"thigh_l": -20, "thigh_r": 17, "knee_l": 19, "knee_r": 56, "foot_l": 5, "foot_r": 3, "arm_l": 18, "arm_r": -18, "elbow_l": 82, "elbow_r": -82, "pelvis": -7, "chest": 9, "head": -2},
        {"thigh_l": 4, "thigh_r": 2, "knee_l": 18, "knee_r": 70, "foot_l": -4, "foot_r": 17, "arm_l": 2, "arm_r": -2, "elbow_l": 86, "elbow_r": -86, "pelvis": -6, "chest": 8, "head": -2, "flight": 0.035},
        {"thigh_l": 25, "thigh_r": -16, "knee_l": 10, "knee_r": 54, "foot_l": -12, "foot_r": 9, "arm_l": -22, "arm_r": 22, "elbow_l": 80, "elbow_r": -80, "pelvis": -7, "chest": 9, "head": -2, "flight": 0.06},
        {"thigh_l": 27, "thigh_r": -33, "knee_l": 34, "knee_r": 7, "foot_l": -12, "foot_r": 10, "arm_l": -27, "arm_r": 27, "elbow_l": 78, "elbow_r": -78, "pelvis": -7, "chest": 9, "head": -2},
        {"thigh_l": 17, "thigh_r": -20, "knee_l": 56, "knee_r": 19, "foot_l": 3, "foot_r": 5, "arm_l": -18, "arm_r": 18, "elbow_l": 82, "elbow_r": -82, "pelvis": -7, "chest": 9, "head": -2},
        {"thigh_l": 2, "thigh_r": 4, "knee_l": 70, "knee_r": 18, "foot_l": 17, "foot_r": -4, "arm_l": -2, "arm_r": 2, "elbow_l": 86, "elbow_r": -86, "pelvis": -6, "chest": 8, "head": -2, "flight": 0.035},
        {"thigh_l": -16, "thigh_r": 25, "knee_l": 54, "knee_r": 10, "foot_l": 9, "foot_r": -12, "arm_l": 22, "arm_r": -22, "elbow_l": 80, "elbow_r": -80, "pelvis": -7, "chest": 9, "head": -2, "flight": 0.06},
    ]
    return {
        "Idle": (idle, 12, "BEZIER"),
        "Walk": (walk, 3, "LINEAR"),
        "Run": (run, 2, "LINEAR"),
    }


def create_actions(rig: bpy.types.Object, meshes: list[bpy.types.Object], selected_names: tuple[str, ...]) -> list[bpy.types.Action]:
    if rig.animation_data:
        rig.animation_data.action = None
    reset_pose(rig)
    ground_z = minimum_mesh_z(meshes)
    actions = []
    for name, (poses, frame_step, interpolation) in action_poses().items():
        if name not in selected_names:
            continue
        existing = bpy.data.actions.get(name)
        if existing:
            bpy.data.actions.remove(existing)
        actions.append(create_action(rig, name, poses, frame_step, interpolation, meshes, name in {"Walk", "Run"}, ground_z))
    reset_pose(rig)
    return actions


def export_glb(output: Path, rig: bpy.types.Object, meshes: list[bpy.types.Object]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    for mesh in meshes:
        mesh.select_set(True)
    bpy.context.view_layer.objects.active = rig
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
        export_def_bones=True,
        export_leaf_bone=False,
        export_optimize_animation_size=False,
        export_yup=True,
    )


def main() -> None:
    args = parse_args()
    source = args.input.resolve()
    output = args.output.resolve()
    if not source.is_file():
        raise RuntimeError(f"Input file does not exist: {source}")
    selected_names = tuple(
        name for name in ACTION_NAMES
        if name.lower() in {value.strip().lower() for value in args.actions.split(",") if value.strip()}
    )
    if not selected_names:
        raise RuntimeError("At least one of Idle, Walk, or Run must be selected")
    rig, meshes = load_source(source)
    missing = [name for name in ("pelvis", "chest", "head", "thigh.L", "thigh.R", "shin.L", "shin.R", "upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R") if name not in rig.pose.bones]
    if missing:
        raise RuntimeError(f"Humanoid rig is missing bones: {', '.join(missing)}")
    rig.location = (0.0, 0.0, 0.0)
    bpy.context.scene.render.fps = max(1, args.fps)
    actions = create_actions(rig, meshes, selected_names)
    export_glb(output, rig, meshes)
    if args.blend_output:
        blend_output = args.blend_output.resolve()
        blend_output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_output))
    report = {
        "success": True,
        "input": str(source),
        "output": str(output),
        "blend": str(args.blend_output.resolve()) if args.blend_output else None,
        "fps": bpy.context.scene.render.fps,
        "bones": len(rig.data.bones),
        "meshes": len(meshes),
        "created_actions": [
            {"name": action.name, "start": float(action.frame_range[0]), "end": float(action.frame_range[1])}
            for action in actions
        ],
        "actions": sorted(action.name for action in bpy.data.actions if action.name in ACTION_NAMES),
    }
    if args.report:
        report_path = args.report.resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ASSET_STUDIO_ANIMATION_REPORT=" + json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
