"""Promote a reviewed ComfyUI frame sequence into canonical sprite-cycle exports."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--pattern", default="frame_*.png")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--action", required=True)
    parser.add_argument("--gif", required=True, type=Path)
    parser.add_argument("--fps", type=float, default=12.0)
    parser.add_argument("--pingpong", action="store_true")
    parser.add_argument("--drop-loop-closure", action="store_true")
    return parser.parse_args()


def chroma_alpha(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = []
    for red, green, blue, alpha in rgba.get_flattened_data():
        is_green = green >= 100 and green - max(red, blue) >= 35
        pixels.append((red, green, blue, 0 if is_green else alpha))
    rgba.putdata(pixels)
    return rgba


def main() -> None:
    args = arguments()
    sources = sorted(args.input.glob(args.pattern))
    if not sources:
        raise SystemExit(f"No input frames matched {args.pattern!r} in {args.input}")

    export_sources = sources[:-1] if args.drop_loop_closure else sources
    if not export_sources:
        raise SystemExit("No export frames remain after dropping the loop-closure frame")

    green_dir = args.output / "green"
    alpha_dir = args.output / "frames"
    green_dir.mkdir(parents=True, exist_ok=True)
    alpha_dir.mkdir(parents=True, exist_ok=True)

    expected_names = {f"{args.action}_{index:02d}.png" for index in range(len(export_sources))}
    stale = {
        path.name
        for folder in (green_dir, alpha_dir)
        for path in folder.glob(f"{args.action}_*.png")
        if path.name not in expected_names
    }
    if stale:
        raise SystemExit(f"Refusing to overwrite an export with stale extra frames: {sorted(stale)}")

    for index, source in enumerate(export_sources):
        name = f"{args.action}_{index:02d}.png"
        shutil.copy2(source, green_dir / name)
        with Image.open(source) as image:
            chroma_alpha(image).save(alpha_dir / name)

    if args.pingpong or args.drop_loop_closure:
        gif_frames = []
        for source in export_sources:
            with Image.open(source) as image:
                gif_frames.append(image.convert("RGB"))
        preview_frames = (
            gif_frames + [frame.copy() for frame in gif_frames[-2:0:-1]]
            if args.pingpong
            else gif_frames
        )
        preview_frames[0].save(
            args.output / "preview.gif",
            save_all=True,
            append_images=preview_frames[1:],
            duration=max(10, round(1000 / args.fps)),
            loop=0,
            disposal=2,
            optimize=False,
        )
        loop_mode = "pingpong" if args.pingpong else "forward"
    else:
        shutil.copy2(args.gif, args.output / "preview.gif")
        preview_frames = export_sources
        loop_mode = "forward"
    print(
        json.dumps(
            {
                "source_frames": len(sources),
                "exported_source_frames": len(export_sources),
                "green_frames": len(list(green_dir.glob(f"{args.action}_*.png"))),
                "alpha_frames": len(list(alpha_dir.glob(f"{args.action}_*.png"))),
                "preview_frames": len(preview_frames),
                "loop_mode": loop_mode,
                "fps": args.fps,
                "preview": str((args.output / "preview.gif").resolve()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
