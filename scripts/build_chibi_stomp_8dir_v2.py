from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 96
SUBJECT_HEIGHT = 92
COLORS = 64
DIRECTIONS = ("S", "SW", "W", "NW", "N", "NE", "E", "SE")
BASE_DIRECTIONS = ("S", "SW", "W", "NW", "N")
MIRRORS = {"NE": "NW", "E": "W", "SE": "SW"}
SEQUENCE = ("left_contact", "neutral", "right_contact", "neutral")
BG = (239, 236, 228, 255)


def hard_alpha(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    image.putalpha(image.getchannel("A").point(lambda value: 255 if value >= 32 else 0))
    return image


def normalized_source(path: Path) -> Image.Image:
    source = Image.open(path).convert("RGBA")
    bbox = source.getchannel("A").getbbox()
    if not bbox:
        raise ValueError(f"No visible pixels in {path}")
    source = source.crop(bbox)
    width = min(SIZE - 4, max(1, round(source.width * SUBJECT_HEIGHT / source.height)))
    source = source.resize((width, SUBJECT_HEIGHT), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (SIZE, SIZE))
    canvas.alpha_composite(source, ((SIZE - width) // 2, 2))
    return hard_alpha(canvas)


def layers(
    path: Path, *, split_profile_legs: bool = True
) -> tuple[Image.Image, Image.Image, Image.Image]:
    neutral = normalized_source(path)
    x0, y0, x1, y1 = neutral.getchannel("A").getbbox()
    center = (x0 + x1) // 2
    split_y = y0 + round((y1 - y0) * 0.59)
    leg_start_y = max(y0, split_y - 4)
    pelvis_cover_end_y = min(y1, split_y + 7)
    half = max(8, round((x1 - x0) * 0.40))
    leg_x0, leg_x1 = max(x0, center - half), min(x1, center + half)
    upper = neutral.copy()
    alpha = upper.getchannel("A")
    # Keep a fixed pelvis band over the moving legs. Both legs start four pixels
    # above the visible cut and remain hidden behind this seven-pixel cover, so
    # their translation can never expose a hollow horizontal seam.
    alpha.paste(0, (leg_x0, pelvis_cover_end_y, leg_x1, SIZE))
    upper.putalpha(alpha)
    legs = Image.new("RGBA", neutral.size)
    legs.alpha_composite(
        neutral.crop((leg_x0, leg_start_y, leg_x1, SIZE)),
        (leg_x0, leg_start_y),
    )
    if not split_profile_legs:
        return upper, legs, Image.new("RGBA", neutral.size)
    left, right = Image.new("RGBA", neutral.size), Image.new("RGBA", neutral.size)
    left.alpha_composite(legs.crop((0, 0, center, SIZE)), (0, 0))
    right.alpha_composite(legs.crop((center, 0, SIZE, SIZE)), (center, 0))
    return upper, left, right


def compose(parts, offsets) -> Image.Image:
    upper, left, right = parts
    upper_offset, left_offset, right_offset = offsets
    frame = Image.new("RGBA", (SIZE, SIZE))
    frame.alpha_composite(left, left_offset)
    frame.alpha_composite(right, right_offset)
    frame.alpha_composite(upper, upper_offset)
    return hard_alpha(frame)


def make_frames(path: Path, *, profile: bool = False) -> list[Image.Image]:
    parts = layers(path, split_profile_legs=not profile)
    if profile:
        poses = {
            "neutral": compose(parts, ((0, 0), (0, 0), (0, 0))),
            "left_contact": compose(parts, ((0, 1), (-1, 1), (0, 0))),
            "right_contact": compose(parts, ((0, 1), (1, 1), (0, 0))),
        }
        return [poses[name].copy() for name in SEQUENCE]
    poses = {
        "neutral": compose(parts, ((0, 0), (0, 0), (0, 0))),
        "left_contact": compose(parts, ((0, 1), (-2, 2), (1, -1))),
        "right_contact": compose(parts, ((0, 1), (-1, -1), (2, 2))),
    }
    return [poses[name].copy() for name in SEQUENCE]


def shared_quantize(raw: dict[str, list[Image.Image]]) -> dict[str, list[Image.Image]]:
    atlas = Image.new("RGBA", (SIZE * 4, SIZE * 8))
    for row, direction in enumerate(DIRECTIONS):
        for column, frame in enumerate(raw[direction]):
            atlas.alpha_composite(frame, (column * SIZE, row * SIZE))
    alpha = atlas.getchannel("A")
    matte = Image.new("RGB", atlas.size, (255, 0, 255))
    matte.paste(atlas.convert("RGB"), mask=alpha)
    result = matte.quantize(colors=COLORS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGBA")
    result.putalpha(alpha)
    return {
        direction: [result.crop((column * SIZE, row * SIZE, (column + 1) * SIZE, (row + 1) * SIZE)) for column in range(4)]
        for row, direction in enumerate(DIRECTIONS)
    }


def save_direction(root: Path, direction: str, frames: list[Image.Image]) -> None:
    folder = root / direction
    frame_dir = folder / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    atlas = Image.new("RGBA", (SIZE * 4, SIZE))
    gif_frames = []
    for index, frame in enumerate(frames):
        frame.save(frame_dir / f"walk_{index:02d}.png")
        atlas.alpha_composite(frame, (index * SIZE, 0))
        scaled = frame.resize((480, 480), Image.Resampling.NEAREST)
        preview = Image.new("RGBA", scaled.size, BG)
        preview.alpha_composite(scaled)
        gif_frames.append(preview.convert("P", palette=Image.Palette.ADAPTIVE, colors=128))
    atlas.save(folder / "walk_96x96_atlas.png")
    gif_frames[0].save(folder / "walk_preview.gif", save_all=True, append_images=gif_frames[1:], duration=125, loop=0, disposal=2)


def save_full_outputs(root: Path, frames: dict[str, list[Image.Image]]) -> None:
    atlas = Image.new("RGBA", (SIZE * 4, SIZE * 8))
    for row, direction in enumerate(DIRECTIONS):
        for column, frame in enumerate(frames[direction]):
            atlas.alpha_composite(frame, (column * SIZE, row * SIZE))
    atlas.save(root / "walk_8dir_96x96_atlas.png")
    cell, gap = SIZE * 4, 12
    width, height = 4 * cell + 5 * gap, 2 * (cell + 28) + 3 * gap
    animation = []
    for frame_index in range(4):
        sheet = Image.new("RGBA", (width, height), BG)
        draw = ImageDraw.Draw(sheet)
        for index, direction in enumerate(DIRECTIONS):
            row, column = divmod(index, 4)
            x, y = gap + column * (cell + gap), gap + row * (cell + 28 + gap)
            draw.text((x + 4, y), direction, fill=(32, 31, 36, 255))
            sprite = frames[direction][frame_index].resize((cell, cell), Image.Resampling.NEAREST)
            sheet.alpha_composite(sprite, (x, y + 20))
        animation.append(sheet)
    animation[1].save(root / "direction_masters.png")
    animation[0].save(root / "contact_left_qa.png")
    animation[2].save(root / "contact_right_qa.png")
    gif_frames = [frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=128) for frame in animation]
    gif_frames[0].save(root / "walk_8dir_preview.gif", save_all=True, append_images=gif_frames[1:], duration=125, loop=0, disposal=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    raw = {
        direction: make_frames(
            args.source_dir / f"{direction}_alpha.png",
            profile=direction == "W",
        )
        for direction in BASE_DIRECTIONS
    }
    for target, source in MIRRORS.items():
        raw[target] = [frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT) for frame in raw[source]]
    frames = shared_quantize(raw)
    for direction in DIRECTIONS:
        save_direction(args.output, direction, frames[direction])
    save_full_outputs(args.output, frames)
    (args.output / "metadata.json").write_text(json.dumps({
        "frame_size": [SIZE, SIZE], "frame_count_per_direction": 4,
        "direction_order": list(DIRECTIONS), "sequence": list(SEQUENCE),
        "duration_ms": 125, "palette_colors": COLORS,
        "technique": "reference-preserving 96px rigid two-contact stomp",
        "identity_anchor": "user-supplied S_reference_green.png",
        "mirrored_directions": MIRRORS,
        "eye_rules": {"S": 2, "SW": 2, "SE": 2, "W": 1, "E": 1, "NW": 0, "N": 0, "NE": 0},
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
