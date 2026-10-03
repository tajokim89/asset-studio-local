"""Bake Quaternius animation onto the chairman rig with Blender bone-space correction."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy


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
    parser.add_argument("--frames", default=32, type=int)
    return parser.parse_args(values)


def main() -> None:
    args = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(args.target.resolve()))
    target = bpy.data.objects.get("ChairmanRig")
    if target is None:
        raise RuntimeError("ChairmanRig not found")
    imported_before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(args.source.resolve()))
    imported = [obj for obj in bpy.data.objects if obj not in imported_before]
    sources = [obj for obj in imported if obj.type == "ARMATURE"]
    if len(sources) != 1:
        raise RuntimeError(f"Expected one source armature, found {len(sources)}")
    source = sources[0]
    source_action = bpy.data.actions.get(args.source_action)
    if source_action is None:
        raise RuntimeError(f"Missing source action: {args.source_action}")
    source.animation_data_create()
    source.animation_data.action = source_action

    target.animation_data_create()
    target.animation_data.action = None
    for pose_bone in target.pose.bones:
        pose_bone.matrix_basis.identity()
        pose_bone.rotation_mode = "QUATERNION"
        for constraint in list(pose_bone.constraints):
            pose_bone.constraints.remove(constraint)
    for target_name, source_name in BONE_MAP.items():
        constraint = target.pose.bones[target_name].constraints.new("COPY_ROTATION")
        constraint.name = "UAL_Retarget"
        constraint.target = source
        constraint.subtarget = source_name
        constraint.target_space = "LOCAL_OWNER_ORIENT"
        constraint.owner_space = "LOCAL"
        constraint.mix_mode = "REPLACE"
        clavicle_name = {"upper_arm.L": "clavicle_l", "upper_arm.R": "clavicle_r"}.get(target_name)
        if clavicle_name:
            clavicle = target.pose.bones[target_name].constraints.new("COPY_ROTATION")
            clavicle.name = "UAL_Clavicle_Retarget"
            clavicle.target = source
            clavicle.subtarget = clavicle_name
            clavicle.target_space = "LOCAL_OWNER_ORIENT"
            clavicle.owner_space = "LOCAL"
            clavicle.mix_mode = "BEFORE"

    scene = bpy.context.scene
    start = int(round(source_action.frame_range[0]))
    end = start + args.frames - 1
    scene.frame_start = start
    scene.frame_end = end
    scene.render.fps = 30
    bpy.ops.object.mode_set(mode="OBJECT") if target.mode != "OBJECT" else None
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.mode_set(mode="POSE")
    for pose_bone in target.pose.bones:
        pose_bone.bone.select = pose_bone.name in BONE_MAP
    bpy.ops.nla.bake(
        frame_start=start,
        frame_end=end,
        step=1,
        only_selected=True,
        visual_keying=True,
        clear_constraints=True,
        clear_parents=False,
        use_current_action=False,
        bake_types={"POSE"},
    )
    bpy.ops.object.mode_set(mode="OBJECT")
    if target.animation_data is None or target.animation_data.action is None:
        raise RuntimeError("Blender did not create a baked target action")
    target.animation_data.action.name = args.action_name
    target.animation_data.action.frame_start = start
    target.animation_data.action.frame_end = end

    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    print(f"RETARGETED={args.output.resolve()}")


if __name__ == "__main__":
    main()
