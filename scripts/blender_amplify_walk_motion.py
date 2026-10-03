"""Amplify an existing walk action without changing the rig or character mesh."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector


def arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--glb-output", type=Path)
    parser.add_argument("--action", default="Walk_Natural")
    parser.add_argument("--arm-factor", type=float, default=2.0)
    parser.add_argument("--elbow-bend", type=float, default=0.28)
    return parser.parse_args(values)


def mean_quaternion(values: list[Quaternion]) -> Quaternion:
    reference = values[0]
    components = [0.0, 0.0, 0.0, 0.0]
    for value in values:
        aligned = value if reference.dot(value) >= 0 else -value
        for index in range(4):
            components[index] += aligned[index]
    result = Quaternion(tuple(component / len(values) for component in components))
    result.normalize()
    return result


def rotation_vector(value: Quaternion) -> Vector:
    axis, angle = value.to_axis_angle()
    return axis * angle


def quaternion_from_rotation_vector(value: Vector) -> Quaternion:
    angle = value.length
    if angle <= 1e-8:
        return Quaternion()
    return Quaternion(value.normalized(), angle)


def amplified_quaternion(
    neutral: Quaternion,
    value: Quaternion,
    factor: float,
    *,
    swing_axis: Vector | None = None,
) -> Quaternion:
    aligned = value if neutral.dot(value) >= 0 else -value
    delta = neutral.inverted() @ aligned
    delta_vector = rotation_vector(delta)
    if swing_axis is None:
        amplified_vector = delta_vector * factor
    else:
        main_swing = swing_axis * delta_vector.dot(swing_axis)
        residual = delta_vector - main_swing
        amplified_vector = main_swing * factor + residual
    result = neutral @ quaternion_from_rotation_vector(amplified_vector)
    result.normalize()
    return result


def amplify_bone(
    rig: bpy.types.Object,
    action: bpy.types.Action,
    bone_name: str,
    factor: float,
    *,
    primary_axis_only: bool = False,
) -> None:
    pose_bone = rig.pose.bones.get(bone_name)
    if pose_bone is None:
        raise RuntimeError(f"Missing pose bone: {bone_name}")
    data_path = f'pose.bones["{bone_name}"].rotation_quaternion'
    curves = [curve for curve in action.fcurves if curve.data_path == data_path]
    if len(curves) != 4:
        raise RuntimeError(f"Expected four quaternion curves for {bone_name}, found {len(curves)}")
    frames = sorted({round(point.co.x) for curve in curves for point in curve.keyframe_points})
    samples: list[Quaternion] = []
    scene = bpy.context.scene
    for frame in frames:
        scene.frame_set(frame)
        samples.append(pose_bone.rotation_quaternion.copy())
    neutral = mean_quaternion(samples)
    swing_axis = None
    if primary_axis_only:
        deltas = [rotation_vector(neutral.inverted() @ sample) for sample in samples]
        strongest = max(deltas, key=lambda value: value.length)
        if strongest.length <= 1e-8:
            raise RuntimeError(f"No swing axis found for {bone_name}")
        swing_axis = strongest.normalized()
    amplified = [
        amplified_quaternion(neutral, sample, factor, swing_axis=swing_axis)
        for sample in samples
    ]
    amplified_by_frame = dict(zip(frames, amplified))
    for curve in curves:
        for point in curve.keyframe_points:
            frame = round(point.co.x)
            value = amplified_by_frame[frame]
            point.co[1] = value[curve.array_index]
            point.interpolation = "LINEAR"
        curve.update()


def lock_elbow_bend(
    rig: bpy.types.Object,
    action: bpy.types.Action,
    bone_name: str,
    bend_ratio: float,
) -> None:
    pose_bone = rig.pose.bones.get(bone_name)
    if pose_bone is None:
        raise RuntimeError(f"Missing pose bone: {bone_name}")
    data_path = f'pose.bones["{bone_name}"].rotation_quaternion'
    curves = [curve for curve in action.fcurves if curve.data_path == data_path]
    if len(curves) != 4:
        raise RuntimeError(f"Expected four quaternion curves for {bone_name}, found {len(curves)}")
    frames = sorted({round(point.co.x) for curve in curves for point in curve.keyframe_points})
    samples: list[Quaternion] = []
    scene = bpy.context.scene
    for frame in frames:
        scene.frame_set(frame)
        samples.append(pose_bone.rotation_quaternion.copy())
    neutral = mean_quaternion(samples)
    target = Quaternion().slerp(neutral, max(0.0, min(1.0, bend_ratio)))
    target.normalize()
    for curve in curves:
        for point in curve.keyframe_points:
            point.co[1] = target[curve.array_index]
            point.interpolation = "LINEAR"
        curve.update()


def export_glb(path: Path, rig: bpy.types.Object) -> None:
    meshes = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
        and any(modifier.type == "ARMATURE" and modifier.object == rig for modifier in obj.modifiers)
    ]
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    for mesh in meshes:
        mesh.select_set(True)
    bpy.context.view_layer.objects.active = rig
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
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


def main() -> None:
    args = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(args.input.resolve()))
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(rigs) != 1:
        raise RuntimeError(f"Expected one armature, found {len(rigs)}")
    rig = rigs[0]
    action = bpy.data.actions.get(args.action)
    if action is None:
        raise RuntimeError(f"Missing action: {args.action}")
    rig.animation_data_create()
    rig.animation_data.action = action
    start, end = (round(value) for value in action.frame_range)
    for bone_name in ("upperarm_l", "upperarm_r"):
        amplify_bone(rig, action, bone_name, args.arm_factor, primary_axis_only=True)
    for bone_name in ("elbow_l", "elbow_r"):
        lock_elbow_bend(rig, action, bone_name, args.elbow_bend)
    bpy.context.scene.frame_set(start)
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    if args.glb_output:
        export_glb(args.glb_output.resolve(), rig)
    print(
        "AMPLIFIED_WALK="
        + json.dumps(
            {
                "output": str(args.output.resolve()),
                "glb_output": str(args.glb_output.resolve()) if args.glb_output else None,
                "action": action.name,
                "frames": [start, end],
                "arm_factor": args.arm_factor,
                "elbow_bend": args.elbow_bend,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
