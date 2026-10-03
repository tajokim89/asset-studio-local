"""Bind an unrigged T-pose character to a Quaternius-compatible skeleton."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


DEFORM_HIERARCHY = {
    "pelvis": "root",
    "spine_01": "pelvis",
    "spine_02": "spine_01",
    "spine_03": "spine_02",
    "neck_01": "spine_03",
    "Head": "neck_01",
    "clavicle_l": "spine_03",
    "upperarm_l": "clavicle_l",
    "elbow_l": "upperarm_l",
    "lowerarm_l": "elbow_l",
    "hand_l": "lowerarm_l",
    "clavicle_r": "spine_03",
    "upperarm_r": "clavicle_r",
    "elbow_r": "upperarm_r",
    "lowerarm_r": "elbow_r",
    "hand_r": "lowerarm_r",
    "thigh_l": "pelvis",
    "calf_l": "thigh_l",
    "foot_l": "calf_l",
    "ball_l": "foot_l",
    "thigh_r": "pelvis",
    "calf_r": "thigh_r",
    "foot_r": "calf_r",
    "ball_r": "foot_r",
}

CONTROL_HIERARCHY = {
    "root": None,
    "CTRL_elbow_pole_l": "root",
    "CTRL_elbow_pole_r": "root",
    "socket_weapon_l": "hand_l",
    "socket_weapon_r": "hand_r",
}


def arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    return parser.parse_args(values)


def mesh_bounds(mesh: bpy.types.Object) -> tuple[Vector, Vector]:
    points = [mesh.matrix_world @ vertex.co for vertex in mesh.data.vertices]
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def normalize_meshes(meshes: list[bpy.types.Object]) -> bpy.types.Object:
    if not meshes:
        raise RuntimeError("Input GLB contains no mesh")
    bpy.ops.object.select_all(action="DESELECT")
    for mesh in meshes:
        mesh.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    mesh = bpy.context.view_layer.objects.active
    lower, upper = mesh_bounds(mesh)
    height = upper.z - lower.z
    if height <= 1e-6:
        raise RuntimeError("Input mesh has no usable height")
    center = (lower + upper) * 0.5
    scale = 2.0 / height
    world = mesh.matrix_world.copy()
    for vertex in mesh.data.vertices:
        vertex.co = (world @ vertex.co - center) * scale
    mesh.parent = None
    mesh.matrix_world = Matrix.Identity(4)
    mesh.name = "ChairmanMesh"
    mesh.data.name = "ChairmanMesh"
    mesh.data.update()
    return mesh


def add_bone(
    armature: bpy.types.Armature,
    name: str,
    head: tuple[float, float, float],
    tail: tuple[float, float, float],
    parent: str | None,
    roll_axis: tuple[float, float, float],
    deform: bool = True,
) -> None:
    bone = armature.edit_bones.new(name)
    bone.head = head
    bone.tail = tail
    bone.use_connect = False
    bone.use_deform = deform
    if parent is not None:
        bone.parent = armature.edit_bones[parent]
    bone.align_roll(Vector(roll_axis))


def create_rig() -> bpy.types.Object:
    armature = bpy.data.armatures.new("ChairmanUALRig")
    rig = bpy.data.objects.new("ChairmanUALRig", armature)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    add_bone(armature, "root", (0.0, 0.0, -1.0), (0.0, 0.18, -1.0), None, (0.0, 0.0, 1.0), False)
    add_bone(armature, "pelvis", (0.0, 0.0, -0.11), (0.0, 0.0, 0.07), "root", (0.0, -1.0, 0.0))
    add_bone(armature, "spine_01", (0.0, 0.0, 0.07), (0.0, 0.0, 0.23), "pelvis", (0.0, -1.0, 0.0))
    add_bone(armature, "spine_02", (0.0, 0.0, 0.23), (0.0, 0.0, 0.39), "spine_01", (0.0, -1.0, 0.0))
    add_bone(armature, "spine_03", (0.0, 0.0, 0.39), (0.0, 0.0, 0.55), "spine_02", (0.0, -1.0, 0.0))
    add_bone(armature, "neck_01", (0.0, 0.0, 0.55), (0.0, 0.0, 0.67), "spine_03", (0.0, -1.0, 0.0))
    add_bone(armature, "Head", (0.0, 0.0, 0.67), (0.0, 0.0, 0.91), "neck_01", (0.0, -1.0, 0.0))

    add_bone(armature, "clavicle_l", (0.035, 0.0, 0.53), (0.20, 0.0, 0.50), "spine_03", (0.0, 0.0, 1.0))
    add_bone(armature, "upperarm_l", (0.20, 0.0, 0.50), (0.49, 0.0, 0.50), "clavicle_l", (0.0, -1.0, 0.0))
    add_bone(armature, "elbow_l", (0.49, 0.0, 0.50), (0.56, 0.0, 0.50), "upperarm_l", (0.0, -1.0, 0.0))
    add_bone(armature, "lowerarm_l", (0.56, 0.0, 0.50), (0.80, 0.0, 0.50), "elbow_l", (0.0, -1.0, 0.0))
    add_bone(armature, "hand_l", (0.80, 0.0, 0.50), (0.92, 0.0, 0.50), "lowerarm_l", (0.0, -1.0, 0.0))

    add_bone(armature, "clavicle_r", (-0.035, 0.0, 0.53), (-0.20, 0.0, 0.50), "spine_03", (0.0, 0.0, 1.0))
    add_bone(armature, "upperarm_r", (-0.20, 0.0, 0.50), (-0.49, 0.0, 0.50), "clavicle_r", (0.0, -1.0, 0.0))
    add_bone(armature, "elbow_r", (-0.49, 0.0, 0.50), (-0.56, 0.0, 0.50), "upperarm_r", (0.0, -1.0, 0.0))
    add_bone(armature, "lowerarm_r", (-0.56, 0.0, 0.50), (-0.80, 0.0, 0.50), "elbow_r", (0.0, -1.0, 0.0))
    add_bone(armature, "hand_r", (-0.80, 0.0, 0.50), (-0.92, 0.0, 0.50), "lowerarm_r", (0.0, -1.0, 0.0))

    for side, sign in (("l", 1.0), ("r", -1.0)):
        hip_x = 0.105 * sign
        add_bone(armature, f"thigh_{side}", (hip_x, 0.0, -0.08), (hip_x, 0.0, -0.45), "pelvis", (0.0, 1.0, 0.0))
        add_bone(armature, f"calf_{side}", (hip_x, 0.0, -0.45), (hip_x, 0.02, -0.82), f"thigh_{side}", (0.0, 1.0, 0.0))
        add_bone(armature, f"foot_{side}", (hip_x, 0.02, -0.82), (hip_x, -0.14, -0.91), f"calf_{side}", (0.0, 1.0, 0.0))
        add_bone(armature, f"ball_{side}", (hip_x, -0.14, -0.91), (hip_x, -0.23, -0.91), f"foot_{side}", (0.0, 0.0, 1.0))

    add_bone(armature, "CTRL_elbow_pole_l", (0.49, -0.34, 0.50), (0.49, -0.34, 0.58), "root", (0.0, -1.0, 0.0), False)
    add_bone(armature, "CTRL_elbow_pole_r", (-0.49, -0.34, 0.50), (-0.49, -0.34, 0.58), "root", (0.0, -1.0, 0.0), False)
    add_bone(armature, "socket_weapon_l", (0.92, 0.0, 0.50), (0.92, 0.0, 0.57), "hand_l", (0.0, -1.0, 0.0), False)
    add_bone(armature, "socket_weapon_r", (-0.92, 0.0, 0.50), (-0.92, 0.0, 0.57), "hand_r", (0.0, -1.0, 0.0), False)

    bpy.ops.object.mode_set(mode="OBJECT")
    rig.show_in_front = True
    rig.data.show_axes = True
    rig["animation_standard"] = "Quaternius Universal Animation Library 1 + 2"
    rig["arm_chain"] = "clavicle > upperarm > elbow > lowerarm > hand"
    return rig


def bind(mesh: bpy.types.Object, rig: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    modifiers = [modifier for modifier in mesh.modifiers if modifier.type == "ARMATURE"]
    if len(modifiers) != 1 or modifiers[0].object != rig:
        raise RuntimeError("Automatic weighting did not bind the mesh to ChairmanUALRig")


def group_vertex_counts(mesh: bpy.types.Object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for group in mesh.vertex_groups:
        counts[group.name] = sum(
            1
            for vertex in mesh.data.vertices
            if any(item.group == group.index and item.weight > 1e-6 for item in vertex.groups)
        )
    return counts


def validate(mesh: bpy.types.Object, rig: bpy.types.Object) -> dict[str, object]:
    expected = {**CONTROL_HIERARCHY, **DEFORM_HIERARCHY}
    hierarchy = {
        name: rig.data.bones[name].parent.name if rig.data.bones[name].parent else None
        for name in expected
    }
    if hierarchy != expected:
        raise RuntimeError(f"Unexpected rig hierarchy: {hierarchy}")
    counts = group_vertex_counts(mesh)
    missing_groups = sorted(name for name in DEFORM_HIERARCHY if name not in counts)
    empty_joints = sorted(name for name in ("elbow_l", "elbow_r", "lowerarm_l", "lowerarm_r") if counts.get(name, 0) == 0)
    if missing_groups:
        raise RuntimeError(f"Missing deformation groups: {missing_groups}")
    if empty_joints:
        raise RuntimeError(f"Arm joint groups received no vertices: {empty_joints}")
    lower, upper = mesh_bounds(mesh)
    return {
        "rig": rig.name,
        "bones": len(rig.data.bones),
        "mesh": mesh.name,
        "vertices": len(mesh.data.vertices),
        "bounds_min": [round(value, 5) for value in lower],
        "bounds_max": [round(value, 5) for value in upper],
        "hierarchy": hierarchy,
        "weighted_vertices": {name: counts.get(name, 0) for name in DEFORM_HIERARCHY},
        "elbows": {"left": counts["elbow_l"], "right": counts["elbow_r"]},
        "weapon_sockets": ["socket_weapon_l", "socket_weapon_r"],
    }


def main() -> None:
    args = arguments()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(args.input.resolve()))
    imported_meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    mesh = normalize_meshes(imported_meshes)
    for obj in list(bpy.context.scene.objects):
        if obj != mesh and obj.type != "MESH":
            bpy.data.objects.remove(obj, do_unlink=True)
    rig = create_rig()
    bind(mesh, rig)
    report = validate(mesh, rig)
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    if args.report:
        args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.report.resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("UAL_TPOSE_RIG=" + json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
