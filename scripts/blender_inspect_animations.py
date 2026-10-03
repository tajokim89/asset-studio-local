"""Print armature and animation metadata from a GLB/FBX file.

Run with Blender in background mode::

    blender -b --python scripts/blender_inspect_animations.py -- INPUT_FILE
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy


def arguments_after_separator() -> tuple[Path, set[str] | None]:
    if "--" not in sys.argv:
        raise SystemExit("usage: blender ... -- INPUT_FILE")
    values = sys.argv[sys.argv.index("--") + 1 :]
    if not values:
        raise SystemExit("usage: blender ... -- INPUT_FILE [bone1,bone2,...]")
    selected = set(values[1].split(",")) if len(values) > 1 else None
    return Path(values[0]).resolve(), selected


def import_scene(source: Path) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    suffix = source.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(source))
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(source))
    elif suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(source))
    else:
        raise SystemExit(f"unsupported file type: {suffix}")


def main() -> None:
    source, selected_bones = arguments_after_separator()
    import_scene(source)
    payload = {
        "source": str(source),
        "armatures": [
            {
                "name": obj.name,
                "bones": len(obj.data.bones),
                "bone_names": [bone.name for bone in obj.data.bones],
                "bone_rest": {
                    bone.name: {
                        "head": [round(value, 5) for value in bone.head_local],
                        "tail": [round(value, 5) for value in bone.tail_local],
                        "parent": bone.parent.name if bone.parent else None,
                        "use_connect": bone.use_connect,
                        "matrix": [
                            [round(value, 5) for value in row]
                            for row in bone.matrix_local
                        ],
                    }
                    for bone in obj.data.bones
                    if selected_bones is None or bone.name in selected_bones
                },
                "dimensions": [round(value, 5) for value in obj.dimensions],
            }
            for obj in bpy.context.scene.objects
            if obj.type == "ARMATURE"
        ],
        "meshes": [
            {
                "name": obj.name,
                "vertices": len(obj.data.vertices),
                "parent": obj.parent.name if obj.parent else None,
                "modifiers": [modifier.type for modifier in obj.modifiers],
                "dimensions": [round(value, 5) for value in obj.dimensions],
                "bounds_min": [
                    round(min((obj.matrix_world @ obj.data.vertices[index].co)[axis] for index in range(len(obj.data.vertices))), 5)
                    for axis in range(3)
                ],
                "bounds_max": [
                    round(max((obj.matrix_world @ obj.data.vertices[index].co)[axis] for index in range(len(obj.data.vertices))), 5)
                    for axis in range(3)
                ],
            }
            for obj in bpy.context.scene.objects
            if obj.type == "MESH"
        ],
        "actions": [
            {
                "name": action.name,
                "frame_start": round(action.frame_range[0], 3),
                "frame_end": round(action.frame_range[1], 3),
                "slots": len(action.slots),
                "slot_details": [
                    {
                        "identifier": slot.identifier,
                        "target_id_type": slot.target_id_type,
                    }
                    for slot in action.slots
                ],
            }
            for action in bpy.data.actions
        ],
    }
    print("ASSET_STUDIO_ANIMATIONS=" + json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
