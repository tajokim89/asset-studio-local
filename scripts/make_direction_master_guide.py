"""Assemble eight neutral 3D direction renders into a 4x2 guide sheet."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="Directory containing one subdirectory per compass direction")
    parser.add_argument("output", type=Path)
    parser.add_argument("--contact", type=Path)
    parser.add_argument("--fit-subject", action="store_true")
    args = parser.parse_args()

    images: list[tuple[str, Image.Image]] = []
    for direction in DIRECTIONS:
        matches = sorted((args.root / direction).glob("idle_loop_*.png"))
        if len(matches) != 1:
            raise SystemExit(f"Expected one idle render for {direction}, found {len(matches)}")
        with Image.open(matches[0]) as source:
            images.append((direction, source.convert("RGBA").copy()))

    width, height = images[0][1].size
    if args.fit_subject:
        cropped = []
        for direction, source in images:
            bbox = source.getchannel("A").getbbox()
            if bbox is None:
                raise SystemExit(f"No visible subject in {direction}")
            cropped.append((direction, source.crop(bbox)))
        scale = min(
            (width * 0.82) / max(source.width for _, source in cropped),
            (height * 0.88) / max(source.height for _, source in cropped),
        )
        images = [
            (
                direction,
                source.resize(
                    (max(1, round(source.width * scale)), max(1, round(source.height * scale))),
                    Image.Resampling.LANCZOS,
                ),
            )
            for direction, source in cropped
        ]

    guide = Image.new("RGBA", (width * 4, height * 2), (243, 245, 247, 255))
    for index, (_, source) in enumerate(images):
        cell_x = (index % 4) * width
        cell_y = (index // 4) * height
        x = cell_x + (width - source.width) // 2
        y = cell_y + round(height * 0.95) - source.height
        guide.alpha_composite(source, (x, y))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    guide.save(args.output)

    if args.contact:
        label_height = 26
        contact = Image.new("RGBA", (width * 4, (height + label_height) * 2), (243, 245, 247, 255))
        draw = ImageDraw.Draw(contact)
        for index, (direction, source) in enumerate(images):
            x = (index % 4) * width
            y = (index // 4) * (height + label_height)
            source_x = x + (width - source.width) // 2
            source_y = y + round(height * 0.95) - source.height
            contact.alpha_composite(source, (source_x, source_y))
            draw.rectangle((x, y + height, x + width, y + height + label_height), fill=(10, 12, 17))
            draw.text((x + 8, y + height + 5), direction, fill=(235, 239, 246))
        args.contact.parent.mkdir(parents=True, exist_ok=True)
        contact.save(args.contact)

    print(args.output.resolve())


if __name__ == "__main__":
    main()
