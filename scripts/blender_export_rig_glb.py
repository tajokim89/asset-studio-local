"""Export a clean rigged Blender master as an animated GLB."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


def arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(values)


def main() -> None:
    args = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(args.input.resolve()))
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(rigs) != 1:
        raise RuntimeError(f"Expected one armature, found {len(rigs)}")
    rig = rigs[0]
    meshes = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
        and any(modifier.type == "ARMATURE" and modifier.object == rig for modifier in obj.modifiers)
    ]
    if not meshes:
        raise RuntimeError("No mesh is bound to the armature")
    extra_meshes = [obj.name for obj in bpy.context.scene.objects if obj.type == "MESH" and obj not in meshes]
    if extra_meshes:
        raise RuntimeError(f"Refusing to export unrelated meshes: {extra_meshes}")

    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    for mesh in meshes:
        mesh.select_set(True)
    bpy.context.view_layer.objects.active = rig
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(args.output.resolve()),
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
        "RIG_GLB_EXPORT="
        + json.dumps(
            {
                "output": str(args.output.resolve()),
                "rig": rig.name,
                "bones": len(rig.data.bones),
                "meshes": [mesh.name for mesh in meshes],
                "actions": [action.name for action in bpy.data.actions],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
