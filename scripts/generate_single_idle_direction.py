"""Generate one focused idle direction from the approved front identity master."""

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


DIRECTION_COPY = {
    "N": "strict back view; face fully hidden; back of hair, jacket, trousers, and both heels visible",
    "NE": "back-right three-quarter view; mostly back with a small right cheek profile",
    "E": "strict right profile; one eye profile and the right side of the body visible",
    "SE": "front-right three-quarter view; face and chest mostly visible",
}


def prompt(direction: str) -> str:
    return f"""IMAGE 1 is the only approved identity, face, body proportion, and clothing reference.
Create exactly one complete full-body drawing of that same young man in a relaxed planted idle stance, now shown from {direction}: {DIRECTION_COPY[direction]}.

The pose/depth/mannequin controls define camera direction, joints, and foot contact only. Never copy the mannequin's muscles, narrow waist, broad shoulders, tight legs, fists, or clothing silhouette.

Preserve the approved outfit exactly:
- loose untucked navy work jacket extending over the hips and completely hiding the waistband;
- beige inner collar, buttons, one chest pocket, two lower pockets, rolled beige cuffs, and worn elbow patches;
- very loose wide dark work trousers with gathered ankle cuffs and the same sewn knee patch;
- dark slip-on shoes;
- ordinary lean build and relaxed open hands.

There is no belt, tucked shirt, armor, shoulder cap, visible abdomen, muscle suit, tight trouser, or superhero anatomy. Infer the same real jacket and trousers from the requested camera angle without redesigning them.

One connected character only, centered at the same scale and bottom baseline as the supplied pose. Keep the face and hair coherent for this angle. No green holes inside the body, sliced face, rectangular seams, detached fragments, duplicate people, missing limbs, floor, shadow, scenery, text, border, watermark, weapon, or prop.
Use a perfectly flat #00FF00 background. Clean hand-painted 2D game-character art ready for 32-bit refined RPG pixel reduction, not pixelated yet."""


def green_canvas(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    subject = source.convert("RGBA")
    bbox = subject.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("front master has no visible subject")
    subject = subject.crop(bbox)
    scale = min((size[0] * 0.82) / subject.width, (size[1] * 0.90) / subject.height)
    subject = subject.resize(
        (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
        Image.Resampling.NEAREST,
    )
    canvas = Image.new("RGBA", size, (0, 255, 0, 255))
    x = (size[0] - subject.width) // 2
    y = round(size[1] * 0.95) - subject.height
    canvas.alpha_composite(subject, (x, y))
    return canvas


def opaque_guide(source: Image.Image) -> Image.Image:
    rgba = source.convert("RGBA")
    canvas = Image.new("RGBA", rgba.size, (243, 245, 247, 255))
    canvas.alpha_composite(rgba)
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("direction", choices=tuple(DIRECTION_COPY))
    parser.add_argument("guide", type=Path)
    parser.add_argument("identity", type=Path)
    parser.add_argument("front_master", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--resolution", type=int, default=96)
    parser.add_argument("--palette", type=int, default=32)
    parser.add_argument("--seed", type=int, default=24080400)
    parser.add_argument("--denoise", type=float, default=0.90)
    args = parser.parse_args()

    with Image.open(args.guide.resolve()) as source:
        guide = opaque_guide(source)
    with Image.open(args.identity.resolve()) as source:
        identity = source.convert("RGBA")
    with Image.open(args.front_master.resolve()) as source:
        start = green_canvas(source, guide.size)

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
    start_path = input_job / "start.png"
    _save_input_image(identity, identity_path)
    _save_input_image(guide, guide_path)
    _save_input_image(start, start_path)
    identity_name = (relative_job / identity_path.name).as_posix()
    guide_name = (relative_job / guide_path.name).as_posix()
    start_name = (relative_job / start_path.name).as_posix()

    try:
        controls = client.run(build_controls_prompt(guide_name, output_prefix))
        pose_path = input_job / "pose.png"
        depth_path = input_job / "depth.png"
        shutil.copy2(client.output_path(controls, "3"), pose_path)
        shutil.copy2(client.output_path(controls, "7"), depth_path)
        qwen = client.run(build_qwen_prompt(
            identity_name,
            start_name,
            (relative_job / pose_path.name).as_posix(),
            (relative_job / depth_path.name).as_posix(),
            guide_name,
            output_prefix,
            action="idle",
            direction=args.direction,
            style="32-bit refined RPG",
            shape_lock=94,
            pixel_simplify=60,
            seed=args.seed,
            prompt_text=prompt(args.direction),
            denoise=args.denoise,
            megapixels=1.0,
        ))
        painted_path = input_job / "painted.png"
        shutil.copy2(client.output_path(qwen, "22"), painted_path)
        background = client.run(build_background_prompt(
            (relative_job / painted_path.name).as_posix(),
            output_prefix,
        ))
        cutout_path = client.output_path(background, "3")
        with Image.open(cutout_path) as source:
            cutout = source.convert("RGBA")
        repeated = Image.new("RGBA", (cutout.width * 4, cutout.height * 2), (0, 0, 0, 0))
        for index in range(8):
            repeated.alpha_composite(cutout, ((index % 4) * cutout.width, (index // 4) * cutout.height))
        _atlas, frames, qa = pixelize_action_sheet(
            repeated,
            cell_width=args.resolution,
            palette_colors=args.palette,
        )

        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        shutil.copy2(client.output_path(qwen, "22"), output / "painted.png")
        shutil.copy2(cutout_path, output / "cutout.png")
        (output / "master.png").write_bytes(_png_bytes(frames[0]))
        metadata = {
            "provider": "local-comfyui",
            "model": "Qwen-Image-Edit-2511-Lightning-4steps",
            "method": "focused-single-direction+approved-front-identity",
            "direction": args.direction,
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
