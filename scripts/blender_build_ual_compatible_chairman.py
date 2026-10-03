"""Upgrade the chairman's compact rig to a Quaternius-compatible hierarchy.

The mesh stays in its original rest shape. Existing deformation groups are
renamed instead of recalculating the whole character with bone heat, which is
important for the layered jacket and trousers on this generated mesh.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


RENAME = {
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

EXPECTED_HIERARCHY = {
    "root": None,
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
    return parser.parse_args(values)


def rename_vertex_groups(meshes: list[bpy.types.Object]) -> None:
    for mesh in meshes:
        for old_name, new_name in RENAME.items():
            old_group = mesh.vertex_groups.get(old_name)
            new_group = mesh.vertex_groups.get(new_name)
            if old_group is not None and new_group is None:
                old_group.name = new_name
            elif old_group is not None and new_group is not old_group:
                raise RuntimeError(
                    f"Cannot safely rename {mesh.name}:{old_name}; {new_name} already exists"
                )


def new_bone(
    armature: bpy.types.Armature,
    name: str,
    head: Vector,
    tail: Vector,
    roll_axis: Vector,
) -> bpy.types.EditBone:
    bone = armature.edit_bones.new(name)
    bone.head = head
    bone.tail = tail
    bone.align_roll(roll_axis)
    bone.use_connect = False
    return bone


def oriented_matrix(head: Vector, direction: Vector, roll_axis: Vector) -> Matrix:
    """Build a bone pose matrix whose local Y follows direction."""
    y_axis = direction.normalized()
    z_axis = (roll_axis - y_axis * roll_axis.dot(y_axis)).normalized()
    x_axis = y_axis.cross(z_axis).normalized()
    matrix = Matrix((x_axis, y_axis, z_axis)).transposed().to_4x4()
    matrix.translation = head
    return matrix


def pose_arms_to_t(rig: bpy.types.Object) -> None:
    """Pose the original A-rest arms into the UAL T-rest orientation."""
    rig.data.pose_position = "POSE"
    bpy.context.scene.frame_set(0)
    for pose_bone in rig.pose.bones:
        pose_bone.matrix_basis.identity()
    bpy.context.view_layer.update()
    for side, direction in (("L", Vector((1.0, 0.0, 0.0))), ("R", Vector((-1.0, 0.0, 0.0)))):
        chain = (f"upper_arm.{side}", f"forearm.{side}", f"hand.{side}")
        head = rig.data.bones[chain[0]].head_local.copy()
        for name in chain:
            length = rig.data.bones[name].length
            rig.pose.bones[name].matrix = oriented_matrix(
                head,
                direction,
                Vector((0.0, -1.0, 0.0)),
            )
            head = head + direction * length
            bpy.context.view_layer.update()


def bake_posed_meshes(meshes: list[bpy.types.Object], rig: bpy.types.Object) -> None:
    """Apply the original rig while it holds the T-pose, retaining groups."""
    bpy.ops.object.mode_set(mode="OBJECT") if rig.mode != "OBJECT" else None
    for mesh in meshes:
        mesh.data = mesh.data.copy()
        bpy.ops.object.select_all(action="DESELECT")
        mesh.select_set(True)
        bpy.context.view_layer.objects.active = mesh
        armature_modifiers = [modifier for modifier in mesh.modifiers if modifier.type == "ARMATURE"]
        if len(armature_modifiers) != 1:
            raise RuntimeError(f"Expected one armature modifier on {mesh.name}")
        bpy.ops.object.modifier_apply(modifier=armature_modifiers[0].name)
        world_matrix = mesh.matrix_world.copy()
        mesh.parent = None
        mesh.matrix_world = world_matrix


def reset_pose(rig: bpy.types.Object) -> None:
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    rig.data.pose_position = "POSE"
    for pose_bone in rig.pose.bones:
        pose_bone.matrix_basis.identity()
    bpy.context.view_layer.update()


def upgrade_hierarchy(rig: bpy.types.Object) -> None:
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bones = rig.data.edit_bones

    for old_name, new_name in RENAME.items():
        bone = bones.get(old_name)
        if bone is None:
            raise RuntimeError(f"Missing chairman bone: {old_name}")
        bone.name = new_name

    # The mesh was baked in this exact T-pose before editing the rest rig.
    for side, direction in (("l", Vector((1.0, 0.0, 0.0))), ("r", Vector((-1.0, 0.0, 0.0)))):
        chain = (f"upperarm_{side}", f"lowerarm_{side}", f"hand_{side}")
        head = bones[chain[0]].head.copy()
        for name in chain:
            bone = bones[name]
            length = bone.length
            bone.head = head
            bone.tail = head + direction * length
            bone.align_roll(Vector((0.0, -1.0, 0.0)))
            head = bone.tail.copy()

    elbow_l = new_bone(
        rig.data,
        "elbow_l",
        bones["upperarm_l"].tail.copy(),
        bones["upperarm_l"].tail + Vector((min(0.07, bones["lowerarm_l"].length * 0.24), 0.0, 0.0)),
        Vector((0.0, -1.0, 0.0)),
    )
    elbow_r = new_bone(
        rig.data,
        "elbow_r",
        bones["upperarm_r"].tail.copy(),
        bones["upperarm_r"].tail + Vector((-min(0.07, bones["lowerarm_r"].length * 0.24), 0.0, 0.0)),
        Vector((0.0, -1.0, 0.0)),
    )
    bones["lowerarm_l"].head = elbow_l.tail.copy()
    bones["lowerarm_r"].head = elbow_r.tail.copy()

    pelvis = bones["pelvis"]
    spine_01 = bones["spine_01"]
    spine_03 = bones["spine_03"]
    neck = bones["neck_01"]

    ground_z = min(bone.head.z for bone in bones) - 0.08
    root = new_bone(
        rig.data,
        "root",
        Vector((0.0, 0.0, ground_z)),
        Vector((0.0, 0.18, ground_z)),
        Vector((0.0, 0.0, 1.0)),
    )
    root.use_deform = False

    torso_bottom = spine_01.head.copy()
    torso_top = neck.head.copy()
    one_third = torso_bottom.lerp(torso_top, 1.0 / 3.0)
    two_thirds = torso_bottom.lerp(torso_top, 2.0 / 3.0)
    spine_01.head = torso_bottom
    spine_01.tail = one_third
    spine_01.align_roll(Vector((0.0, -1.0, 0.0)))
    spine_02 = new_bone(
        rig.data,
        "spine_02",
        one_third,
        two_thirds,
        Vector((0.0, -1.0, 0.0)),
    )
    spine_03.head = two_thirds
    spine_03.tail = torso_top
    spine_03.align_roll(Vector((0.0, -1.0, 0.0)))

    clavicle_l = new_bone(
        rig.data,
        "clavicle_l",
        Vector((0.035, 0.0, torso_top.z - 0.035)),
        bones["upperarm_l"].head.copy(),
        Vector((0.0, 0.0, 1.0)),
    )
    clavicle_r = new_bone(
        rig.data,
        "clavicle_r",
        Vector((-0.035, 0.0, torso_top.z - 0.035)),
        bones["upperarm_r"].head.copy(),
        Vector((0.0, 0.0, 1.0)),
    )

    ball_l = new_bone(
        rig.data,
        "ball_l",
        bones["foot_l"].tail.copy(),
        bones["foot_l"].tail + Vector((0.0, -0.09, 0.0)),
        Vector((0.0, 0.0, 1.0)),
    )
    ball_r = new_bone(
        rig.data,
        "ball_r",
        bones["foot_r"].tail.copy(),
        bones["foot_r"].tail + Vector((0.0, -0.09, 0.0)),
        Vector((0.0, 0.0, 1.0)),
    )
    elbow_pole_l = new_bone(
        rig.data,
        "CTRL_elbow_pole_l",
        elbow_l.head + Vector((0.0, -0.35, 0.0)),
        elbow_l.head + Vector((0.0, -0.35, 0.08)),
        Vector((0.0, -1.0, 0.0)),
    )
    elbow_pole_r = new_bone(
        rig.data,
        "CTRL_elbow_pole_r",
        elbow_r.head + Vector((0.0, -0.35, 0.0)),
        elbow_r.head + Vector((0.0, -0.35, 0.08)),
        Vector((0.0, -1.0, 0.0)),
    )
    weapon_socket_l = new_bone(
        rig.data,
        "socket_weapon_l",
        bones["hand_l"].tail.copy(),
        bones["hand_l"].tail + Vector((0.0, 0.0, 0.07)),
        Vector((0.0, -1.0, 0.0)),
    )
    weapon_socket_r = new_bone(
        rig.data,
        "socket_weapon_r",
        bones["hand_r"].tail.copy(),
        bones["hand_r"].tail + Vector((0.0, 0.0, 0.07)),
        Vector((0.0, -1.0, 0.0)),
    )
    for control in (elbow_pole_l, elbow_pole_r, weapon_socket_l, weapon_socket_r):
        control.use_deform = False

    pelvis.parent = root
    spine_01.parent = pelvis
    spine_02.parent = spine_01
    spine_03.parent = spine_02
    neck.parent = spine_03
    bones["Head"].parent = neck
    clavicle_l.parent = spine_03
    bones["upperarm_l"].parent = clavicle_l
    elbow_l.parent = bones["upperarm_l"]
    bones["lowerarm_l"].parent = elbow_l
    bones["hand_l"].parent = bones["lowerarm_l"]
    clavicle_r.parent = spine_03
    bones["upperarm_r"].parent = clavicle_r
    elbow_r.parent = bones["upperarm_r"]
    bones["lowerarm_r"].parent = elbow_r
    bones["hand_r"].parent = bones["lowerarm_r"]
    bones["thigh_l"].parent = pelvis
    bones["calf_l"].parent = bones["thigh_l"]
    bones["foot_l"].parent = bones["calf_l"]
    ball_l.parent = bones["foot_l"]
    bones["thigh_r"].parent = pelvis
    bones["calf_r"].parent = bones["thigh_r"]
    bones["foot_r"].parent = bones["calf_r"]
    ball_r.parent = bones["foot_r"]
    elbow_pole_l.parent = root
    elbow_pole_r.parent = root
    weapon_socket_l.parent = bones["hand_l"]
    weapon_socket_r.parent = bones["hand_r"]

    for name in EXPECTED_HIERARCHY:
        bone = bones[name]
        bone.use_connect = False
        if name not in {"root", "CTRL_elbow_pole_l", "CTRL_elbow_pole_r", "socket_weapon_l", "socket_weapon_r"}:
            bone.use_deform = True

    # Match the Quaternius local-axis convention closely. The retarget
    # constraint still performs owner-orientation conversion, but matching the
    # primary roll axes prevents shoulder and wrist twist from accumulating.
    for name in (
        "pelvis",
        "spine_01",
        "spine_02",
        "spine_03",
        "neck_01",
        "Head",
        "upperarm_l",
        "elbow_l",
        "lowerarm_l",
        "hand_l",
        "upperarm_r",
        "elbow_r",
        "lowerarm_r",
        "hand_r",
    ):
        bones[name].align_roll(Vector((0.0, -1.0, 0.0)))
    for name in (
        "thigh_l",
        "calf_l",
        "foot_l",
        "thigh_r",
        "calf_r",
        "foot_r",
    ):
        bones[name].align_roll(Vector((0.0, 1.0, 0.0)))

    bpy.ops.object.mode_set(mode="OBJECT")


def validate(rig: bpy.types.Object, meshes: list[bpy.types.Object]) -> dict[str, object]:
    hierarchy = {
        name: rig.data.bones[name].parent.name if rig.data.bones[name].parent else None
        for name in EXPECTED_HIERARCHY
    }
    if hierarchy != EXPECTED_HIERARCHY:
        raise RuntimeError(f"Unexpected hierarchy: {hierarchy}")
    stale_groups = {
        mesh.name: sorted(name for name in RENAME if mesh.vertex_groups.get(name))
        for mesh in meshes
    }
    stale_groups = {name: groups for name, groups in stale_groups.items() if groups}
    if stale_groups:
        raise RuntimeError(f"Old deformation groups remain: {stale_groups}")
    missing_groups = {
        mesh.name: sorted(
            new_name for new_name in RENAME.values() if mesh.vertex_groups.get(new_name) is None
        )
        for mesh in meshes
    }
    missing_groups = {name: groups for name, groups in missing_groups.items() if groups}
    if missing_groups:
        raise RuntimeError(f"Renamed deformation groups missing: {missing_groups}")
    return {
        "rig": rig.name,
        "bones": len(rig.data.bones),
        "hierarchy": hierarchy,
        "meshes": [mesh.name for mesh in meshes],
        "vertex_groups_preserved": True,
    }


def main() -> None:
    args = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(args.input.resolve()))
    rig = bpy.data.objects.get("ChairmanRig")
    if rig is None or rig.type != "ARMATURE":
        raise RuntimeError("ChairmanRig armature not found")
    meshes = [
        obj
        for obj in bpy.data.objects
        if obj.type == "MESH"
        and any(mod.type == "ARMATURE" and mod.object == rig for mod in obj.modifiers)
    ]
    if not meshes:
        raise RuntimeError("No chairman mesh bound to ChairmanRig")

    rig.animation_data_create()
    rig.animation_data.action = None
    rig.data.pose_position = "REST"
    for pose_bone in rig.pose.bones:
        pose_bone.matrix_basis.identity()
        for constraint in list(pose_bone.constraints):
            pose_bone.constraints.remove(constraint)

    pose_arms_to_t(rig)
    bake_posed_meshes(meshes, rig)
    reset_pose(rig)
    rename_vertex_groups(meshes)
    bpy.ops.object.select_all(action="DESELECT")
    upgrade_hierarchy(rig)
    rig.name = "ChairmanUALRig"
    rig.data.name = "ChairmanUALRig"
    rig.show_in_front = True
    rig.data.show_axes = True
    rig["animation_standard"] = "Quaternius Universal Animation Library 1 + 2"
    rig["retarget_method"] = "matching hierarchy + Local Owner Orientation + visual bake"

    for mesh in meshes:
        mesh.parent = rig
        mesh.matrix_parent_inverse = rig.matrix_world.inverted()
        modifier = mesh.modifiers.new(name="ChairmanUALDeform", type="ARMATURE")
        modifier.object = rig

    # Rejected prototype actions stay in the original file, not in this clean
    # compatible master.
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)

    payload = validate(rig, meshes)
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    print("UAL_COMPATIBLE=" + json.dumps(payload, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
