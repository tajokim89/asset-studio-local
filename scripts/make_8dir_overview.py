"""Create a labeled overview of eight directional action atlases."""

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
    args = parser.parse_args()

    atlases: list[tuple[str, Image.Image]] = []
    for direction in DIRECTIONS:
        matches = sorted((args.root / direction).glob(f"{args.action}_*x*_atlas.png"))
        if len(matches) != 1:
            raise SystemExit(f"Expected one {args.action} atlas for {direction}, found {len(matches)}")
        with Image.open(matches[0]) as source:
            atlases.append((direction, source.convert("RGBA").copy()))

    width, height = atlases[0][1].size
    label_height = 32
    columns = 4
    rows = 2
    sheet = Image.new("RGBA", (width * columns, (height + label_height) * rows), (18, 20, 26, 255))
    draw = ImageDraw.Draw(sheet)
    for index, (direction, atlas) in enumerate(atlases):
        column = index % columns
        row = index // columns
        x = column * width
        y = row * (height + label_height)
        checker = Image.new("RGBA", atlas.size, (31, 34, 43, 255))
        checker.alpha_composite(atlas)
        sheet.alpha_composite(checker, (x, y))
        draw.rectangle((x, y + height, x + width, y + height + label_height), fill=(12, 14, 19, 255))
        draw.text((x + 12, y + height + 8), direction, fill=(233, 238, 247, 255))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(args.output, quality=95)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
