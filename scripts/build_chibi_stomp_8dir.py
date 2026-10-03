from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


CANVAS_SIZE = 64
FRAME_SEQUENCE = ("left", "neutral", "right", "neutral")
DIRECTION_ORDER = ("S", "SW", "W", "NW", "N", "NE", "E", "SE")
BASE_DIRECTIONS = ("S", "SW", "W", "NW", "N")
MIRROR_DIRECTIONS = {"NE": "NW", "E": "W", "SE": "SW"}
PREVIEW_BACKGROUND = (239, 236, 228, 255)


TRIAL_2_OFFSETS = {
    "upper_left": (0, 1),
    "left_left": (-1, 1),
    "right_left": (1, -1),
    "upper_right": (0, 1),
    "left_right": (-1, -1),
    "right_right": (1, 1),
}


def binary_alpha(image: Image.Image, threshold: int = 32) -> Image.Image:
    result = image.convert("RGBA")
    alpha = result.getchannel("A").point(lambda value: 255 if value >= threshold else 0)
    result.putalpha(alpha)
    return result


def quantize_rgba(image: Image.Image, colors: int = 32) -> Image.Image:
    image = binary_alpha(image)
    alpha = image.getchannel("A")
    matte = Image.new("RGB", image.size, (255, 0, 255))
    matte.paste(image.convert("RGB"), mask=alpha)
    palette = matte.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    result = palette.convert("RGB").convert("RGBA")
    result.putalpha(alpha)
    return result


def centered_layer(piece: Image.Image, y: int) -> Image.Image:
    layer = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    x = (CANVAS_SIZE - piece.width) // 2
    layer.alpha_composite(binary_alpha(piece), dest=(x, y))
    return layer


def build_layers(source_path: Path) -> tuple[Image.Image, Image.Image, Image.Image]:
    source = Image.open(source_path).convert("RGBA")
    bbox = source.getchannel("A").getbbox()
    if not bbox:
        raise ValueError(f"Source has no visible pixels: {source_path}")

    cropped = source.crop(bbox)
    normalized_width = max(20, round(cropped.width * 108 / cropped.height))
    subject = cropped.resize((normalized_width, 108), Image.Resampling.NEAREST)

    head_width = max(18, round(normalized_width * 36 / 46))
    torso_width = max(20, round(normalized_width * 42 / 46))
    legs_width = max(18, round(normalized_width * 36 / 46))
    head_piece = subject.crop((0, 0, normalized_width, 39)).resize(
        (head_width, 32), Image.Resampling.NEAREST
    )
    torso_piece = subject.crop((0, 30, normalized_width, 75)).resize(
        (torso_width, 22), Image.Resampling.NEAREST
    )
    legs_piece = subject.crop((0, 67, normalized_width, 108)).resize(
        (legs_width, 21), Image.Resampling.NEAREST
    )

    head = centered_layer(head_piece, 0)
    torso = centered_layer(torso_piece, 27)
    legs = centered_layer(legs_piece, 43)

    upper = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    upper.alpha_composite(torso)
    upper.alpha_composite(head)

    left_leg = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    right_leg = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    left_leg.alpha_composite(legs.crop((0, 0, 32, CANVAS_SIZE)), dest=(0, 0))
    right_leg.alpha_composite(legs.crop((32, 0, CANVAS_SIZE, CANVAS_SIZE)), dest=(32, 0))
    return upper, left_leg, right_leg


def compose_frame(
    upper: Image.Image,
    left_leg: Image.Image,
    right_leg: Image.Image,
    upper_offset: tuple[int, int] = (0, 0),
    left_offset: tuple[int, int] = (0, 0),
    right_offset: tuple[int, int] = (0, 0),
) -> Image.Image:
    frame = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    frame.alpha_composite(left_leg, dest=left_offset)
    frame.alpha_composite(right_leg, dest=right_offset)
    frame.alpha_composite(upper, dest=upper_offset)
    return binary_alpha(frame)


def build_base_frames(source_path: Path) -> list[Image.Image]:
    upper, left_leg, right_leg = build_layers(source_path)
    neutral = compose_frame(upper, left_leg, right_leg)
    left = compose_frame(
        upper,
        left_leg,
        right_leg,
        TRIAL_2_OFFSETS["upper_left"],
        TRIAL_2_OFFSETS["left_left"],
        TRIAL_2_OFFSETS["right_left"],
    )
    right = compose_frame(
        upper,
        left_leg,
        right_leg,
        TRIAL_2_OFFSETS["upper_right"],
        TRIAL_2_OFFSETS["left_right"],
        TRIAL_2_OFFSETS["right_right"],
    )
    poses = {"left": left, "neutral": neutral, "right": right}
    return [poses[pose].copy() for pose in FRAME_SEQUENCE]


def quantize_all_frames(raw_frames: dict[str, list[Image.Image]]) -> dict[str, list[Image.Image]]:
    combined = Image.new(
        "RGBA",
        (CANVAS_SIZE * len(FRAME_SEQUENCE), CANVAS_SIZE * len(DIRECTION_ORDER)),
    )
    for row, direction in enumerate(DIRECTION_ORDER):
        for column, frame in enumerate(raw_frames[direction]):
            combined.alpha_composite(frame, dest=(column * CANVAS_SIZE, row * CANVAS_SIZE))
    quantized = quantize_rgba(combined, colors=32)

    result: dict[str, list[Image.Image]] = {}
    for row, direction in enumerate(DIRECTION_ORDER):
        result[direction] = []
        for column in range(len(FRAME_SEQUENCE)):
            result[direction].append(
                quantized.crop(
                    (
                        column * CANVAS_SIZE,
                        row * CANVAS_SIZE,
                        (column + 1) * CANVAS_SIZE,
                        (row + 1) * CANVAS_SIZE,
                    )
                )
            )
    return result


def save_direction(output_dir: Path, direction: str, frames: list[Image.Image]) -> None:
    direction_dir = output_dir / direction
    frames_dir = direction_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        frame.save(frames_dir / f"walk_{index:02d}.png")

    atlas = Image.new("RGBA", (CANVAS_SIZE * len(frames), CANVAS_SIZE))
    for index, frame in enumerate(frames):
        atlas.alpha_composite(frame, dest=(index * CANVAS_SIZE, 0))
    atlas.save(direction_dir / "walk_64x64_atlas.png")

    preview_frames = []
    for frame in frames:
        scaled = frame.resize((384, 384), Image.Resampling.NEAREST)
        preview = Image.new("RGBA", scaled.size, PREVIEW_BACKGROUND)
        preview.alpha_composite(scaled)
        preview_frames.append(preview.convert("P", palette=Image.Palette.ADAPTIVE, colors=64))
    preview_frames[0].save(
        direction_dir / "walk_preview.gif",
        save_all=True,
        append_images=preview_frames[1:],
        duration=125,
        loop=0,
        disposal=2,
    )


def save_full_atlas(output_dir: Path, frames: dict[str, list[Image.Image]]) -> None:
    atlas = Image.new(
        "RGBA",
        (CANVAS_SIZE * len(FRAME_SEQUENCE), CANVAS_SIZE * len(DIRECTION_ORDER)),
    )
    for row, direction in enumerate(DIRECTION_ORDER):
        for column, frame in enumerate(frames[direction]):
            atlas.alpha_composite(frame, dest=(column * CANVAS_SIZE, row * CANVAS_SIZE))
    atlas.save(output_dir / "walk_8dir_64x64_atlas.png")


def save_comparison_preview(output_dir: Path, frames: dict[str, list[Image.Image]]) -> None:
    scale = 4
    cell = CANVAS_SIZE * scale
    gap = 12
    columns = 4
    preview_frames = []
    for frame_index in range(len(FRAME_SEQUENCE)):
        canvas = Image.new(
            "RGBA",
            (columns * cell + (columns + 1) * gap, 2 * (cell + 30) + 3 * gap),
            PREVIEW_BACKGROUND,
        )
        draw = ImageDraw.Draw(canvas)
        for index, direction in enumerate(DIRECTION_ORDER):
            row, column = divmod(index, columns)
            x = gap + column * (cell + gap)
            y = gap + row * (cell + 30 + gap)
            draw.text((x + 4, y), direction, fill=(32, 31, 36, 255))
            scaled = frames[direction][frame_index].resize((cell, cell), Image.Resampling.NEAREST)
            canvas.alpha_composite(scaled, dest=(x, y + 24))
        preview_frames.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE, colors=96))
    preview_frames[0].save(
        output_dir / "walk_8dir_preview.gif",
        save_all=True,
        append_images=preview_frames[1:],
        duration=125,
        loop=0,
        disposal=2,
    )


def save_master_sheet(output_dir: Path, frames: dict[str, list[Image.Image]]) -> None:
    scale = 5
    cell = CANVAS_SIZE * scale
    sheet = Image.new("RGBA", (cell * 4 + 80, cell * 2 + 72), PREVIEW_BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    for index, direction in enumerate(DIRECTION_ORDER):
        row, column = divmod(index, 4)
        x = 16 + column * cell
        y = 20 + row * (cell + 28)
        draw.text((x + 4, y), direction, fill=(32, 31, 36, 255))
        scaled = frames[direction][1].resize((cell, cell), Image.Resampling.NEAREST)
        sheet.alpha_composite(scaled, dest=(x, y + 20))
    sheet.save(output_dir / "direction_masters.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    raw_frames = {
        direction: build_base_frames(args.source_dir / f"{direction}_alpha.png")
        for direction in BASE_DIRECTIONS
    }
    for target, source in MIRROR_DIRECTIONS.items():
        raw_frames[target] = [frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT) for frame in raw_frames[source]]

    frames = quantize_all_frames(raw_frames)
    for direction in DIRECTION_ORDER:
        save_direction(args.output, direction, frames[direction])
    save_full_atlas(args.output, frames)
    save_comparison_preview(args.output, frames)
    save_master_sheet(args.output, frames)

    (args.output / "metadata.json").write_text(
        json.dumps(
            {
                "frame_size": [CANVAS_SIZE, CANVAS_SIZE],
                "frame_count_per_direction": len(FRAME_SEQUENCE),
                "direction_order": list(DIRECTION_ORDER),
                "sequence": list(FRAME_SEQUENCE),
                "duration_ms": 125,
                "palette_colors": 32,
                "technique": "Trial 2 rigid pixel-layer stomp; no per-frame AI regeneration",
                "generated_direction_masters": list(BASE_DIRECTIONS),
                "mirrored_directions": MIRROR_DIRECTIONS,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
