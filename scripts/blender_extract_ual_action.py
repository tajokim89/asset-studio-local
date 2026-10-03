"""Extract one untouched Quaternius UAL action into a compact pose-guide asset."""

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
    parser.add_argument("--action", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--blend-output", type=Path)
    return parser.parse_args(values)


def main() -> None:
    args = arguments()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(args.input.resolve()))
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(rigs) != 1:
        raise RuntimeError(f"Expected one UAL armature, found {len(rigs)}")
    rig = rigs[0]
    action = bpy.data.actions.get(args.action)
    if action is None:
        available = sorted(item.name for item in bpy.data.actions)
        raise RuntimeError(f"Missing UAL action {args.action!r}; available={available}")
    rig.animation_data_create()
    rig.animation_data.action = action
    for other in list(bpy.data.actions):
        if other != action:
            bpy.data.actions.remove(other)
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.frame_start = round(action.frame_range[0])
    scene.frame_end = round(action.frame_range[1])
    source_path = args.input.resolve()
    rig["animation_source"] = "Quaternius Universal Animation Library"
    rig["source_file"] = source_path.name
    rig["source_action"] = action.name
    rig["retargeted"] = False

    if args.blend_output:
        blend_output = args.blend_output.resolve()
        blend_output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_output))

    selected = [rig]
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        if obj.parent == rig or any(modifier.type == "ARMATURE" and modifier.object == rig for modifier in obj.modifiers):
            selected.append(obj)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in selected:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
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
        export_def_bones=False,
        export_leaf_bone=False,
        export_optimize_animation_size=False,
        export_yup=True,
    )
    print(
        "UAL_ACTION="
        + json.dumps(
            {
                "source": str(source_path),
                "action": action.name,
                "frame_range": [scene.frame_start, scene.frame_end],
                "bones": len(rig.data.bones),
                "retargeted": False,
                "output": str(output),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
