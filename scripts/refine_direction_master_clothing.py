"""Restore approved clothing on an already coherent eight-direction pose sheet."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from asset_studio.local_3d_pipeline import (  # noqa: E402
    ComfyClient,
    _png_bytes,
    _save_input_image,
    build_background_prompt,
    build_controls_prompt,
    build_qwen_prompt,
    local_3d_pipeline_health,
    pixelize_action_sheet,
)


DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def refinement_prompt() -> str:
    return """IMAGE 1 is the only approved character identity and clothing construction reference.
The supplied 4x2 pose-base sheet already has the correct eight camera directions and body poses. Edit clothing and body proportions only. Do not change any direction, head angle, joint position, foot contact, scale, cell layout, or the N, NE, E, SE / S, SW, W, NW order.

Restore the exact outfit from IMAGE 1 in every cell:
- a loose untucked navy work jacket extending down over the hips and fully covering the abdomen and waistband;
- beige inner collar, front buttons, one chest pocket, two lower patch pockets, rolled beige cuffs, and worn elbow patches;
- very loose wide dark work trousers with gathered ankle cuffs and the same sewn knee patch;
- the same dark slip-on shoes.

Remove the invented belt, tucked shirt, armored shoulder caps, skin-tight trousers, visible abs, chest muscles, thigh muscles, and superhero anatomy. The person has the same ordinary lean build and relaxed open hands as IMAGE 1. Side and back views must infer the same loose jacket hem, pockets, sleeve construction, and trouser volume without inventing accessories.

Keep each face and hair shape coherent for its camera angle. Every figure must be one clean connected silhouette with no green holes, sliced faces, rectangular seams, detached pieces, duplicates, or missing limbs.
Use a perfectly flat #00FF00 background edge-to-edge. No floor, shadow, scenery, text, labels, border, watermark, weapon, or prop. Clean hand-painted 2D game-character art, ready for 32-bit refined RPG pixel reduction but not pixelated yet."""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pose_base", type=Path)
    parser.add_argument("guide", type=Path)
    parser.add_argument("identity", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--resolution", type=int, default=96)
    parser.add_argument("--palette", type=int, default=32)
    parser.add_argument("--seed", type=int, default=24080302)
    parser.add_argument("--denoise", type=float, default=0.58)
    args = parser.parse_args()

    with Image.open(args.pose_base.resolve()) as source:
        pose_base = source.convert("RGBA")
    with Image.open(args.guide.resolve()) as source:
        guide = source.convert("RGBA")
    with Image.open(args.identity.resolve()) as source:
        identity = source.convert("RGBA")

    client = ComfyClient()
    health = local_3d_pipeline_health(client=client)
    if not health.get("available"):
        raise SystemExit(json.dumps(health, ensure_ascii=False, indent=2))

    run_id = uuid.uuid4().hex
    relative_job = Path("asset_studio") / run_id
    input_job = client.paths.input / relative_job
    input_job.mkdir(parents=True, exist_ok=False)
    output_prefix = f"AssetStudio/{run_id}"
    identity_path = input_job / "identity.png"
    guide_path = input_job / "guide.png"
    pose_base_path = input_job / "pose-base.png"
    _save_input_image(identity, identity_path)
    _save_input_image(guide, guide_path)
    _save_input_image(pose_base, pose_base_path)
    identity_name = (relative_job / identity_path.name).as_posix()
    guide_name = (relative_job / guide_path.name).as_posix()
    pose_base_name = (relative_job / pose_base_path.name).as_posix()

    try:
        controls = client.run(build_controls_prompt(guide_name, output_prefix))
        pose_path = input_job / "pose.png"
        depth_path = input_job / "depth.png"
        shutil.copy2(client.output_path(controls, "3"), pose_path)
        shutil.copy2(client.output_path(controls, "7"), depth_path)
        qwen = client.run(build_qwen_prompt(
            identity_name,
            pose_base_name,
            (relative_job / pose_path.name).as_posix(),
            (relative_job / depth_path.name).as_posix(),
            guide_name,
            output_prefix,
            action="idle",
            direction="8dir",
            style="32-bit refined RPG",
            shape_lock=96,
            pixel_simplify=60,
            seed=args.seed,
            prompt_text=refinement_prompt(),
            denoise=args.denoise,
        ))
        painted_path = input_job / "painted.png"
        shutil.copy2(client.output_path(qwen, "22"), painted_path)
        background = client.run(build_background_prompt(
            (relative_job / painted_path.name).as_posix(),
            output_prefix,
        ))
        cutout_path = client.output_path(background, "3")
        with Image.open(cutout_path) as cutout:
            atlas, frames, qa = pixelize_action_sheet(
                cutout.convert("RGBA"),
                cell_width=args.resolution,
                palette_colors=args.palette,
            )

        output = args.output.resolve()
        masters = output / "masters"
        masters.mkdir(parents=True, exist_ok=True)
        shutil.copy2(client.output_path(qwen, "22"), output / "refined_painted.png")
        shutil.copy2(cutout_path, output / "refined_cutout.png")
        (output / "direction_masters_atlas.png").write_bytes(_png_bytes(atlas))
        for direction, frame in zip(DIRECTIONS, frames, strict=True):
            (masters / f"{direction}.png").write_bytes(_png_bytes(frame))
        metadata = {
            "provider": "local-comfyui",
            "model": "Qwen-Image-Edit-2511-Lightning-4steps",
            "method": "fixed-pose-clothing-restoration+shared-palette",
            "directions": list(DIRECTIONS),
            "frame_width": args.resolution,
            "frame_height": args.resolution * 2,
            "palette_colors": args.palette,
            "seed": args.seed,
            "denoise": args.denoise,
            "qa": qa,
            "comfy_run_id": run_id,
        }
        (output / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({"success": True, "output": str(output), **metadata}, ensure_ascii=False, indent=2))
    finally:
        shutil.rmtree(input_job, ignore_errors=True)
        try:
            input_job.parent.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    main()
