from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


CANVAS_SIZE = 64
FRAME_SEQUENCE = ("left", "neutral", "right", "neutral")
PREVIEW_SCALE = 8


VARIANTS = {
    "trial_1_soft": {
        "label": "1 SOFT",
        "upper_left": (0, 1),
        "left_left": (-1, 0),
        "right_left": (0, -1),
        "upper_right": (0, 1),
        "left_right": (0, -1),
        "right_right": (1, 0),
    },
    "trial_2_clear": {
        "label": "2 CLEAR",
        "upper_left": (0, 1),
        "left_left": (-1, 1),
        "right_left": (1, -1),
        "upper_right": (0, 1),
        "left_right": (-1, -1),
        "right_right": (1, 1),
    },
    "trial_3_bouncy": {
        "label": "3 BOUNCY",
        "upper_left": (-1, 2),
        "left_left": (-2, 1),
        "right_left": (1, -2),
        "upper_right": (1, 2),
        "left_right": (-1, -2),
        "right_right": (2, 1),
    },
}


def _paste(canvas: Image.Image, layer: Image.Image, offset: tuple[int, int]) -> None:
    canvas.alpha_composite(layer, dest=offset)


def _binary_alpha(image: Image.Image, threshold: int = 32) -> Image.Image:
    result = image.convert("RGBA")
    alpha = result.getchannel("A").point(lambda value: 255 if value >= threshold else 0)
    result.putalpha(alpha)
    return result


def _quantize_rgba(image: Image.Image, colors: int = 32) -> Image.Image:
    image = _binary_alpha(image)
    alpha = image.getchannel("A")
    matte = Image.new("RGB", image.size, (255, 0, 255))
    matte.paste(image.convert("RGB"), mask=alpha)
    palette = matte.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    result = palette.convert("RGB").convert("RGBA")
    result.putalpha(alpha)
    return result


def build_layers(source_path: Path) -> tuple[Image.Image, Image.Image, Image.Image, Image.Image]:
    source = Image.open(source_path).convert("RGBA")
    bbox = source.getchannel("A").getbbox()
    if not bbox:
        raise ValueError(f"Source has no visible pixels: {source_path}")

    # The generated source is deliberately large, blocky pixel art. Reduce it to
    # its approximate native pixel grid before recomposing the proportions.
    subject = source.crop(bbox).resize((46, 108), Image.Resampling.NEAREST)

    head_piece = subject.crop((4, 0, 42, 39)).resize((36, 32), Image.Resampling.NEAREST)
    torso_piece = subject.crop((0, 30, 46, 75)).resize((42, 22), Image.Resampling.NEAREST)
    legs_piece = subject.crop((4, 67, 42, 108)).resize((36, 21), Image.Resampling.NEAREST)

    head = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    torso = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    legs = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    head.alpha_composite(_binary_alpha(head_piece), dest=(14, 0))
    torso.alpha_composite(_binary_alpha(torso_piece), dest=(11, 27))
    legs.alpha_composite(_binary_alpha(legs_piece), dest=(14, 43))

    upper = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    upper.alpha_composite(torso)
    upper.alpha_composite(head)

    left_leg = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    right_leg = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    left_leg.alpha_composite(legs.crop((0, 0, 32, CANVAS_SIZE)), dest=(0, 0))
    right_leg.alpha_composite(legs.crop((32, 0, CANVAS_SIZE, CANVAS_SIZE)), dest=(32, 0))

    master = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    master.alpha_composite(left_leg)
    master.alpha_composite(right_leg)
    master.alpha_composite(upper)
    master = _quantize_rgba(master)

    # Re-split the quantized master using the construction masks, so every frame
    # shares exactly the same colors and only rigid pixel translations occur.
    upper_mask = Image.new("L", (CANVAS_SIZE, CANVAS_SIZE))
    upper_mask.paste(upper.getchannel("A"))
    left_mask = left_leg.getchannel("A")
    right_mask = right_leg.getchannel("A")
    quant_upper = Image.new("RGBA", master.size)
    quant_left = Image.new("RGBA", master.size)
    quant_right = Image.new("RGBA", master.size)
    quant_upper.paste(master, mask=upper_mask)
    quant_left.paste(master, mask=left_mask)
    quant_right.paste(master, mask=right_mask)
    return master, quant_upper, quant_left, quant_right


def make_frame(
    upper: Image.Image,
    left_leg: Image.Image,
    right_leg: Image.Image,
    upper_offset: tuple[int, int],
    left_offset: tuple[int, int],
    right_offset: tuple[int, int],
) -> Image.Image:
    frame = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    _paste(frame, left_leg, left_offset)
    _paste(frame, right_leg, right_offset)
    _paste(frame, upper, upper_offset)
    return _binary_alpha(frame)


def render_variant(
    output_dir: Path,
    name: str,
    spec: dict[str, object],
    master: Image.Image,
    upper: Image.Image,
    left_leg: Image.Image,
    right_leg: Image.Image,
) -> list[Image.Image]:
    variant_dir = output_dir / name
    frames_dir = variant_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    neutral = master.copy()
    left = make_frame(
        upper,
        left_leg,
        right_leg,
        spec["upper_left"],
        spec["left_left"],
        spec["right_left"],
    )
    right = make_frame(
        upper,
        left_leg,
        right_leg,
        spec["upper_right"],
        spec["left_right"],
        spec["right_right"],
    )
    poses = {"left": left, "neutral": neutral, "right": right}
    frames = [poses[pose].copy() for pose in FRAME_SEQUENCE]

    for index, frame in enumerate(frames):
        frame.save(frames_dir / f"walk_{index:02d}.png")

    atlas = Image.new("RGBA", (CANVAS_SIZE * len(frames), CANVAS_SIZE))
    for index, frame in enumerate(frames):
        atlas.alpha_composite(frame, dest=(index * CANVAS_SIZE, 0))
    atlas.save(variant_dir / "walk_64x64_atlas.png")

    preview_frames = []
    for frame in frames:
        scaled = frame.resize(
            (CANVAS_SIZE * PREVIEW_SCALE, CANVAS_SIZE * PREVIEW_SCALE),
            Image.Resampling.NEAREST,
        )
        preview = Image.new("RGBA", scaled.size, (239, 236, 228, 255))
        preview.alpha_composite(scaled)
        preview_frames.append(preview.convert("P", palette=Image.Palette.ADAPTIVE, colors=64))
    preview_frames[0].save(
        variant_dir / "walk_preview.gif",
        save_all=True,
        append_images=preview_frames[1:],
        duration=125,
        loop=0,
        disposal=2,
    )

    (variant_dir / "metadata.json").write_text(
        json.dumps(
            {
                "name": name,
                "label": spec["label"],
                "frame_size": [CANVAS_SIZE, CANVAS_SIZE],
                "frame_count": len(frames),
                "sequence": list(FRAME_SEQUENCE),
                "duration_ms": 125,
                "technique": "rigid pixel-layer stomp; no per-frame AI regeneration",
                "offsets": {key: value for key, value in spec.items() if key != "label"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return frames


def make_comparison(output_dir: Path, rendered: list[tuple[str, dict[str, object], list[Image.Image]]]) -> None:
    scale = 6
    cell = CANVAS_SIZE * scale
    gap = 12
    comparison_frames = []
    for sequence_index in range(len(FRAME_SEQUENCE)):
        canvas = Image.new("RGBA", (cell * 3 + gap * 4, cell + 48), (239, 236, 228, 255))
        draw = ImageDraw.Draw(canvas)
        for column, (_, spec, frames) in enumerate(rendered):
            x = gap + column * (cell + gap)
            scaled = frames[sequence_index].resize((cell, cell), Image.Resampling.NEAREST)
            canvas.alpha_composite(scaled, dest=(x, 36))
            draw.text((x + 8, 10), str(spec["label"]), fill=(32, 31, 36, 255))
        comparison_frames.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE, colors=96))
    comparison_frames[0].save(
        output_dir / "comparison_preview.gif",
        save_all=True,
        append_images=comparison_frames[1:],
        duration=125,
        loop=0,
        disposal=2,
    )

    sheet = Image.new(
        "RGBA",
        (CANVAS_SIZE * 4 * 4 + 40, CANVAS_SIZE * 3 * 4 + 80),
        (239, 236, 228, 255),
    )
    draw = ImageDraw.Draw(sheet)
    for row, (_, spec, frames) in enumerate(rendered):
        y = 24 + row * (CANVAS_SIZE * 4 + 16)
        draw.text((8, y + 4), str(spec["label"]), fill=(32, 31, 36, 255))
        for column, frame in enumerate(frames):
            scaled = frame.resize((CANVAS_SIZE * 4, CANVAS_SIZE * 4), Image.Resampling.NEAREST)
            sheet.alpha_composite(scaled, dest=(40 + column * CANVAS_SIZE * 4, y))
    sheet.save(output_dir / "comparison_sheet.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    master, upper, left_leg, right_leg = build_layers(args.source)
    master.save(args.output / "chibi_master_64x64.png")

    rendered = []
    for name, spec in VARIANTS.items():
        frames = render_variant(args.output, name, spec, master, upper, left_leg, right_leg)
        rendered.append((name, spec, frames))
    make_comparison(args.output, rendered)

    (args.output / "metadata.json").write_text(
        json.dumps(
            {
                "source": str(args.source),
                "frame_size": [CANVAS_SIZE, CANVAS_SIZE],
                "variants": list(VARIANTS),
                "shared_identity": True,
                "per_frame_ai_generation": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
