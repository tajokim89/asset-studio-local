"""Generate one identity-locked eight-direction character turnaround sheet."""

from __future__ import annotations

import argparse
import base64
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
    _build_identity_start_sheet,
    _png_bytes,
    _save_input_image,
    build_background_prompt,
    build_controls_prompt,
    build_qwen_prompt,
    local_3d_pipeline_health,
    pixelize_action_sheet,
)


DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def direction_master_prompt() -> str:
    return """IMAGE 1 is the only character identity and clothing design reference.
Create one consistent eight-direction turnaround sheet of that exact character in a relaxed neutral standing pose, using the pose/depth/3D controls only for camera angle, joints, ground contact, and cell layout.

The exact 4 columns by 2 rows order is:
top row: N strict back, NE back-right, E right profile, SE front-right;
bottom row: S strict front, SW front-left, W left profile, NW back-left.

All eight cells must depict the same person and the same unchanged outfit. Lock identical standing height, head size, shoulder width, torso length, arm thickness, leg length, and shoe size across every direction. Preserve the blue work jacket's exact length, loose fit, collar, buttons, pockets, rolled cuffs, and both elbow patches. Preserve the same loose dark pants, knee patch, ankle cuffs, and dark slip-on shoes. Rear and side views must infer the same garment construction instead of inventing a new shirt, belt, waistband, armor, muscles, or accessories.

The 3D mannequin is not an appearance or clothing silhouette reference. Use IMAGE 1 for proportions and garment volume. Keep one complete full-body character centered at equal scale and equal foot baseline in each cell. Use clean hand-painted 2D game-character art with crisp edges, ready for 32-bit refined RPG pixel reduction but not pixelated yet.

Use a perfectly flat #00FF00 background edge-to-edge. No floor, shadow, scenery, text, labels, border, watermark, weapons, or extra objects."""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("guide", type=Path)
    parser.add_argument("identity", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--resolution", type=int, default=96)
    parser.add_argument("--palette", type=int, default=32)
    parser.add_argument("--seed", type=int, default=24080301)
    args = parser.parse_args()

    with Image.open(args.guide.resolve()) as source:
        guide = source.convert("RGBA")
    with Image.open(args.identity.resolve()) as source:
        identity = source.convert("RGBA")
    if guide.width % 4 or guide.height % 2:
        raise SystemExit("Guide must be a 4x2 sheet")

    client = ComfyClient()
    health = local_3d_pipeline_health(client=client)
    if not health.get("available"):
        raise SystemExit(json.dumps(health, ensure_ascii=False, indent=2))

    run_id = uuid.uuid4().hex
    relative_job = Path("asset_studio") / run_id
    input_job = client.paths.input / relative_job
    input_job.mkdir(parents=True, exist_ok=False)
    output_prefix = f"AssetStudio/{run_id}"
    guide_path = input_job / "guide.png"
    identity_path = input_job / "identity.png"
    identity_sheet_path = input_job / "identity-sheet.png"
    _save_input_image(guide, guide_path)
    _save_input_image(identity, identity_path)
    _save_input_image(_build_identity_start_sheet(identity, guide), identity_sheet_path)
    guide_name = (relative_job / guide_path.name).as_posix()
    identity_name = (relative_job / identity_path.name).as_posix()
    identity_sheet_name = (relative_job / identity_sheet_path.name).as_posix()

    try:
        controls = client.run(build_controls_prompt(guide_name, output_prefix))
        pose_path = input_job / "pose.png"
        depth_path = input_job / "depth.png"
        shutil.copy2(client.output_path(controls, "3"), pose_path)
        shutil.copy2(client.output_path(controls, "7"), depth_path)

        qwen = client.run(
            build_qwen_prompt(
                identity_name,
                identity_sheet_name,
                (relative_job / pose_path.name).as_posix(),
                (relative_job / depth_path.name).as_posix(),
                guide_name,
                output_prefix,
                action="idle",
                direction="S",
                style="32-bit refined RPG",
                shape_lock=84,
                pixel_simplify=64,
                seed=args.seed,
                prompt_text=direction_master_prompt(),
            )
        )
        painted_path = input_job / "painted.png"
        shutil.copy2(client.output_path(qwen, "22"), painted_path)
        background = client.run(
            build_background_prompt((relative_job / painted_path.name).as_posix(), output_prefix)
        )
        with Image.open(client.output_path(background, "3")) as cutout:
            atlas, frames, qa = pixelize_action_sheet(
                cutout.convert("RGBA"),
                cell_width=args.resolution,
                palette_colors=args.palette,
            )

        output = args.output.resolve()
        masters = output / "masters"
        masters.mkdir(parents=True, exist_ok=True)
        (output / "direction_masters_atlas.png").write_bytes(_png_bytes(atlas))
        for direction, frame in zip(DIRECTIONS, frames, strict=True):
            (masters / f"{direction}.png").write_bytes(_png_bytes(frame))
        metadata = {
            "provider": "local-comfyui",
            "model": "Qwen-Image-Edit-2511-Lightning-4steps",
            "method": "single-pass-8dir-turnaround+shared-scale+shared-palette",
            "directions": list(DIRECTIONS),
            "frame_width": args.resolution,
            "frame_height": args.resolution * 2,
            "palette_colors": args.palette,
            "seed": args.seed,
            "qa": qa,
        }
        (output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"success": True, "output": str(output), **metadata}, ensure_ascii=False, indent=2))
    finally:
        shutil.rmtree(input_job, ignore_errors=True)
        try:
            input_job.parent.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    main()
