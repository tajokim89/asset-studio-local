"""Render evenly sampled action frames from a Blender master or animation GLB."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--actions", default="Walk,Run")
    parser.add_argument("--frames", type=int, default=8)
    parser.add_argument("--width", type=int, default=256)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--transparent", action="store_true")
    parser.add_argument(
        "--view",
        choices=("front", "side", "three-quarter", "N", "NE", "E", "SE", "S", "SW", "W", "NW"),
        default="three-quarter",
    )
    return parser.parse_args(values)


def import_source(source: Path) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    suffix = source.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(source))
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(source))
    elif suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(source))
    else:
        raise RuntimeError(f"Unsupported source: {source}")


def point_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def mesh_bounds() -> tuple[Vector, Vector]:
    points = [
        obj.matrix_world @ Vector(corner)
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
        for corner in obj.bound_box
    ]
    if not points:
        return Vector((-1.0, -0.5, 0.0)), Vector((1.0, 0.5, 2.0))
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def setup_preview_scene(view: str, resolution_x: int, resolution_y: int, *, transparent: bool = False) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = transparent
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.fps = 30
    if scene.world is None:
        scene.world = bpy.data.worlds.new("PreviewWorld")
    scene.world.color = (0.055, 0.065, 0.085)

    bounds_min, bounds_max = mesh_bounds()
    target = (bounds_min + bounds_max) * 0.5
    height = max(0.1, bounds_max.z - bounds_min.z)
    width = max(0.1, bounds_max.x - bounds_min.x, bounds_max.y - bounds_min.y)
    distance = max(5.0, height * 3.0)
    camera_positions = {
        "front": (0.0, -1.0),
        "side": (-1.0, 0.0),
        "three-quarter": (0.707, -0.707),
        "S": (0.0, -1.0),
        "SE": (-0.707, -0.707),
        "E": (-1.0, 0.0),
        "NE": (-0.707, 0.707),
        "N": (0.0, 1.0),
        "NW": (0.707, 0.707),
        "W": (1.0, 0.0),
        "SW": (0.707, -0.707),
    }
    camera_data = bpy.data.cameras.new("PreviewCamera")
    camera = bpy.data.objects.new("PreviewCamera", camera_data)
    bpy.context.collection.objects.link(camera)
    horizontal = camera_positions[view]
    camera.location = target + Vector((horizontal[0] * distance, horizontal[1] * distance, height * 0.03))
    camera.data.type = "ORTHO"
    aspect = max(0.1, resolution_x / resolution_y)
    camera.data.ortho_scale = max(height * 1.14, width * 1.14 / aspect)
    point_at(camera, target)
    scene.camera = camera

    for name, location, energy, size in (
        ("Key", (-3.5, -4.0, 5.0), 950.0, 4.0),
        ("Fill", (4.0, -1.0, 2.5), 650.0, 3.0),
        ("Rim", (0.0, 4.0, 3.5), 800.0, 2.5),
    ):
        light_data = bpy.data.lights.new(name=name, type="AREA")
        light_data.energy = energy
        light_data.shape = "DISK"
        light_data.size = size
        light = bpy.data.objects.new(name, light_data)
        bpy.context.collection.objects.link(light)
        light.location = location
        point_at(light, target)

    if not transparent:
        bpy.ops.mesh.primitive_plane_add(size=max(20.0, height * 10.0), location=(target.x, target.y, bounds_min.z - 0.005))
        floor = bpy.context.object
        floor.name = "PreviewGround"
        material = bpy.data.materials.new("PreviewGroundMaterial")
        material.diffuse_color = (0.035, 0.042, 0.055, 1.0)
        material.roughness = 1.0
        floor.data.materials.append(material)


def main() -> None:
    args = arguments()
    if args.input:
        import_source(args.input.resolve())
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    action_names = [value.strip() for value in args.actions.split(",") if value.strip()]
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(rigs) > 1 or (not rigs and any(name.upper() != "REST" for name in action_names)):
        raise RuntimeError("Expected one armature for animated previews")
    rig = rigs[0] if rigs else None
    if rig is not None:
        rig.animation_data_create()
    setup_preview_scene(args.view, args.width, args.height, transparent=args.transparent)
    scene = bpy.context.scene
    for name in action_names:
        if name.upper() == "REST":
            if rig is not None:
                rig.animation_data.action = None
                rig.data.pose_position = "REST"
            scene.frame_set(0)
            scene.render.filepath = str(output / "rest_00.png")
            bpy.ops.render.render(write_still=True)
            continue
        action = bpy.data.actions.get(name)
        if action is None:
            raise RuntimeError(f"Missing action: {name}")
        rig.animation_data.action = action
        start, end = action.frame_range
        cycle = max(1.0, end - start + 1.0)
        for index in range(args.frames):
            scene.frame_set(math.floor(start + cycle * index / args.frames))
            scene.render.filepath = str(output / f"{name.lower()}_{index:02d}.png")
            bpy.ops.render.render(write_still=True)
    print(f"PREVIEW={output}", flush=True)


if __name__ == "__main__":
    main()
