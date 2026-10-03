"""Retarget Quaternius Walk_Loop onto the existing 17-bone chairman rig."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


BONE_MAP = {
    "pelvis": "pelvis",
    "spine": "spine_01",
    "chest": "spine_03",
    "neck": "neck_01",
    "head": "Head",
    "upper_arm.L": "upperarm_l",
    "forearm.L": "lowerarm_l",
    "hand.L": "hand_l",
    "upper_arm.R": "upperarm_r",
    "forearm.R": "lowerarm_r",
    "hand.R": "hand_r",
    "thigh.L": "thigh_l",
    "shin.L": "calf_l",
    "foot.L": "foot_l",
    "thigh.R": "thigh_r",
    "shin.R": "calf_r",
    "foot.R": "foot_r",
}


def arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-action", default="Walk_Loop")
    parser.add_argument("--action-name", default="Walk_Natural")
    parser.add_argument("--frames", type=int, default=32)
    return parser.parse_args(values)


def relative_rest(bone: bpy.types.Bone) -> Matrix:
    if bone.parent:
        return bone.parent.matrix_local.inverted_safe() @ bone.matrix_local
    return bone.matrix_local.copy()


def relative_pose(pose_bone: bpy.types.PoseBone) -> Matrix:
    if pose_bone.parent:
        return pose_bone.parent.matrix.inverted_safe() @ pose_bone.matrix
    return pose_bone.matrix.copy()


def minimum_mesh_z(meshes: list[bpy.types.Object]) -> float:
    minimum = float("inf")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for mesh in meshes:
        evaluated = mesh.evaluated_get(depsgraph)
        world = evaluated.matrix_world
        minimum = min(minimum, min((world @ vertex.co).z for vertex in evaluated.data.vertices))
    return minimum


def reset_pose(rig: bpy.types.Object) -> None:
    for pose_bone in rig.pose.bones:
        pose_bone.matrix_basis.identity()
        pose_bone.rotation_mode = "QUATERNION"


def main() -> None:
    args = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(args.target.resolve()))
    target_rig = bpy.data.objects.get("ChairmanRig")
    if target_rig is None or target_rig.type != "ARMATURE":
        raise RuntimeError("ChairmanRig armature not found")
    target_meshes = [obj for obj in bpy.data.objects if obj.type == "MESH" and obj.parent == target_rig]
    if not target_meshes:
        raise RuntimeError("No skinned chairman mesh found")

    initial_objects = set(bpy.data.objects)
    reset_pose(target_rig)
    target_rig.animation_data_create()
    target_rig.animation_data.action = None
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    ground_z = minimum_mesh_z(target_meshes)

    bpy.ops.import_scene.gltf(filepath=str(args.source.resolve()))
    imported = [obj for obj in bpy.data.objects if obj not in initial_objects]
    source_rigs = [obj for obj in imported if obj.type == "ARMATURE"]
    if len(source_rigs) != 1:
        raise RuntimeError(f"Expected one imported source armature, found {len(source_rigs)}")
    source_rig = source_rigs[0]
    source_action = bpy.data.actions.get(args.source_action)
    if source_action is None:
        raise RuntimeError(f"Source action not found: {args.source_action}")
    source_rig.animation_data_create()
    source_rig.animation_data.action = source_action

    missing_target = sorted(set(BONE_MAP).difference(target_rig.pose.bones.keys()))
    missing_source = sorted(set(BONE_MAP.values()).difference(source_rig.pose.bones.keys()))
    if missing_target or missing_source:
        raise RuntimeError(f"Bone mapping incomplete: target={missing_target}, source={missing_source}")

    target_action = bpy.data.actions.get(args.action_name)
    if target_action:
        bpy.data.actions.remove(target_action)
    target_action = bpy.data.actions.new(args.action_name)
    target_rig.animation_data.action = target_action
    height_ratio = max(0.1, target_rig.dimensions.z) / max(0.1, source_rig.dimensions.z)

    scene = bpy.context.scene
    scene.render.fps = 30
    for index in range(args.frames):
        source_frame = int(round(source_action.frame_range[0] + index))
        target_frame = source_frame
        scene.frame_set(source_frame)
        bpy.context.view_layer.update()

        for target_name, source_name in BONE_MAP.items():
            target_pose = target_rig.pose.bones[target_name]
            source_pose = source_rig.pose.bones[source_name]
            source_rest = source_pose.bone.matrix_local
            target_rest = target_pose.bone.matrix_local
            rest_offset = source_rest.to_quaternion().inverted() @ target_rest.to_quaternion()
            target_rotation = source_pose.matrix.to_quaternion() @ rest_offset
            if target_pose.parent:
                target_relative_rest = relative_rest(target_pose.bone)
                target_location = target_pose.parent.matrix @ target_relative_rest.translation
            else:
                source_delta = (source_pose.matrix.translation - source_rest.translation) * height_ratio
                target_location = target_rest.translation + source_delta
            target_pose.matrix = Matrix.LocRotScale(
                target_location,
                target_rotation,
                Vector((1.0, 1.0, 1.0)),
            )

        bpy.context.view_layer.update()
        pelvis = target_rig.pose.bones["pelvis"]
        pelvis.location.z += ground_z - minimum_mesh_z(target_meshes)
        bpy.context.view_layer.update()
        for target_name in BONE_MAP:
            pose_bone = target_rig.pose.bones[target_name]
            pose_bone.keyframe_insert(data_path="location", frame=target_frame, group=target_name)
            pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=target_frame, group=target_name)
            pose_bone.keyframe_insert(data_path="scale", frame=target_frame, group=target_name)

    for fcurve in target_action.fcurves:
        for point in fcurve.keyframe_points:
            point.interpolation = "LINEAR"
    target_action.frame_start = source_action.frame_range[0]
    target_action.frame_end = source_action.frame_range[0] + args.frames - 1
    scene.frame_start = int(target_action.frame_start)
    scene.frame_end = int(target_action.frame_end)
    target_rig.animation_data.action = target_action

    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    print(f"RETARGETED={args.output.resolve()}")


if __name__ == "__main__":
    main()
