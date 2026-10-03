"""Animate all eight directional frame sets in one review GIF."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--action", default="walk")
    parser.add_argument("--scale", type=int, default=2)
    args = parser.parse_args()

    direction_frames: dict[str, list[Image.Image]] = {}
    for direction in DIRECTIONS:
        paths = sorted((args.root / direction / "frames").glob(f"{args.action}_*.png"))
        if len(paths) != 8:
            raise SystemExit(f"Expected eight {args.action} frames for {direction}, found {len(paths)}")
        direction_frames[direction] = []
        for path in paths:
            with Image.open(path) as source:
                direction_frames[direction].append(source.convert("RGBA").copy())

    frame_width, frame_height = direction_frames["N"][0].size
    tile_width = frame_width * args.scale
    tile_height = frame_height * args.scale
    label_height = 24
    columns = 4
    rows = 2
    rendered: list[Image.Image] = []
    for frame_index in range(8):
        canvas = Image.new(
            "RGB",
            (tile_width * columns, (tile_height + label_height) * rows),
            (28, 31, 39),
        )
        draw = ImageDraw.Draw(canvas)
        for index, direction in enumerate(DIRECTIONS):
            column = index % columns
            row = index // columns
            x = column * tile_width
            y = row * (tile_height + label_height)
            actor = direction_frames[direction][frame_index].resize(
                (tile_width, tile_height), Image.Resampling.NEAREST
            )
            canvas.paste(actor.convert("RGB"), (x, y), actor.getchannel("A"))
            draw.rectangle((x, y + tile_height, x + tile_width, y + tile_height + label_height), fill=(12, 14, 19))
            draw.text((x + 8, y + tile_height + 5), direction, fill=(235, 239, 246))
        rendered.append(canvas)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered[0].save(
        args.output,
        format="GIF",
        save_all=True,
        append_images=rendered[1:],
        duration=120,
        loop=0,
        disposal=2,
        optimize=False,
    )
    print(args.output.resolve())


if __name__ == "__main__":
    main()
