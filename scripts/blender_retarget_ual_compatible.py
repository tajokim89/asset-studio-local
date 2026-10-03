"""Retarget one Quaternius action onto the compatible chairman hierarchy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


RETARGET_MAP = {
    "root": "root",
    "pelvis": "pelvis",
    "spine_01": "spine_01",
    "spine_02": "spine_02",
    "spine_03": "spine_03",
    "neck_01": "neck_01",
    "Head": "Head",
    "clavicle_l": "clavicle_l",
    "upperarm_l": "upperarm_l",
    "elbow_l": "lowerarm_l",
    "hand_l": "hand_l",
    "clavicle_r": "clavicle_r",
    "upperarm_r": "upperarm_r",
    "elbow_r": "lowerarm_r",
    "hand_r": "hand_r",
    "thigh_l": "thigh_l",
    "calf_l": "calf_l",
    "foot_l": "foot_l",
    "ball_l": "ball_l",
    "thigh_r": "thigh_r",
    "calf_r": "calf_r",
    "foot_r": "foot_r",
    "ball_r": "ball_r",
}


def arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--glb-output", type=Path)
    parser.add_argument("--source-action", default="Walk_Loop")
    parser.add_argument("--action-name", default="Walk_Natural")
    parser.add_argument("--frames", type=int, default=32)
    return parser.parse_args(values)


def main() -> None:
    args = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(args.target.resolve()))
    target = bpy.data.objects.get("ChairmanUALRig")
    if target is None or target.type != "ARMATURE":
        raise RuntimeError("ChairmanUALRig not found")

    target.data.pose_position = "POSE"
    target.animation_data_create()
    target.animation_data.action = None
    for pose_bone in target.pose.bones:
        pose_bone.matrix_basis.identity()
        pose_bone.rotation_mode = "QUATERNION"
        for constraint in list(pose_bone.constraints):
            pose_bone.constraints.remove(constraint)

    objects_before = set(bpy.data.objects)
    actions_before = set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=str(args.source.resolve()))
    imported_objects = [obj for obj in bpy.data.objects if obj not in objects_before]
    imported_actions = [action for action in bpy.data.actions if action not in actions_before]
    source_rigs = [obj for obj in imported_objects if obj.type == "ARMATURE"]
    if len(source_rigs) != 1:
        raise RuntimeError(f"Expected one source armature, found {len(source_rigs)}")
    source = source_rigs[0]
    source_action = bpy.data.actions.get(args.source_action)
    if source_action is None:
        raise RuntimeError(f"Missing source action: {args.source_action}")
    source.animation_data_create()
    source.animation_data.action = source_action

    missing_target = sorted(set(RETARGET_MAP).difference(target.pose.bones.keys()))
    missing_source = sorted(set(RETARGET_MAP.values()).difference(source.pose.bones.keys()))
    if missing_target or missing_source:
        raise RuntimeError(f"Bone mismatch target={missing_target}, source={missing_source}")

    for target_name, source_name in RETARGET_MAP.items():
        target_bone = target.pose.bones[target_name]
        if target_name == "pelvis":
            location = target_bone.constraints.new("COPY_LOCATION")
            location.name = "UAL_Pelvis_Bob"
            location.target = source
            location.subtarget = source_name
            location.target_space = "LOCAL_OWNER_ORIENT"
            location.owner_space = "LOCAL"
            location.use_offset = False
        rotation = target_bone.constraints.new("COPY_ROTATION")
        rotation.name = "UAL_Rotation"
        rotation.target = source
        rotation.subtarget = source_name
        rotation.target_space = "LOCAL_OWNER_ORIENT"
        rotation.owner_space = "LOCAL"
        rotation.mix_mode = "REPLACE"

    scene = bpy.context.scene
    start = int(round(source_action.frame_range[0]))
    end = start + args.frames - 1
    scene.frame_start = start
    scene.frame_end = end
    scene.render.fps = 30
    bpy.context.view_layer.update()

    bpy.ops.object.mode_set(mode="OBJECT") if target.mode != "OBJECT" else None
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.mode_set(mode="POSE")
    for pose_bone in target.pose.bones:
        pose_bone.bone.select = pose_bone.name in RETARGET_MAP
    bpy.ops.nla.bake(
        frame_start=start,
        frame_end=end,
        step=1,
        only_selected=True,
        visual_keying=True,
        clear_constraints=True,
        clear_parents=False,
        use_current_action=False,
        clean_curves=True,
        bake_types={"POSE"},
    )
    bpy.ops.object.mode_set(mode="OBJECT")
    if target.animation_data is None or target.animation_data.action is None:
        raise RuntimeError("Blender did not create a baked action")
    baked_action = target.animation_data.action
    baked_action.name = args.action_name
    baked_action.frame_start = start
    baked_action.frame_end = end
    for fcurve in baked_action.fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = "LINEAR"

    for obj in imported_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for action in imported_actions:
        if action != baked_action and action.users == 0:
            bpy.data.actions.remove(action)

    target_meshes = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
        and any(modifier.type == "ARMATURE" and modifier.object == target for modifier in obj.modifiers)
    ]
    for obj in list(bpy.context.scene.objects):
        if obj.type == "MESH" and obj not in target_meshes:
            bpy.data.objects.remove(obj, do_unlink=True)
        elif obj.type == "ARMATURE" and obj != target:
            bpy.data.objects.remove(obj, do_unlink=True)

    target.animation_data.action = baked_action
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    if args.glb_output:
        bpy.ops.object.select_all(action="DESELECT")
        target.select_set(True)
        for mesh in target_meshes:
            mesh.select_set(True)
        bpy.context.view_layer.objects.active = target
        args.glb_output.resolve().parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.gltf(
            filepath=str(args.glb_output.resolve()),
            export_format="GLB",
            use_selection=True,
            export_materials="EXPORT",
            export_animations=True,
            export_animation_mode="ACTIONS",
            export_frame_range=False,
            export_force_sampling=True,
            export_skins=True,
            export_def_bones=False,
            export_leaf_bone=False,
            export_optimize_animation_size=False,
            export_yup=True,
        )
    print(
        "UAL_RETARGET="
        + json.dumps(
            {
                "output": str(args.output.resolve()),
                "glb_output": str(args.glb_output.resolve()) if args.glb_output else None,
                "source_action": args.source_action,
                "target_action": baked_action.name,
                "frames": [start, end],
                "bones": len(RETARGET_MAP),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
