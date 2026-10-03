#!/usr/bin/env python3
"""Texture-skinned realistic variant of the canonical six-frame orc rig."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

BASE_SCRIPT = Path(__file__).with_name("canonical_orc_walk6.py")
BASE_SPEC = importlib.util.spec_from_file_location("canonical_orc_walk6", BASE_SCRIPT)
assert BASE_SPEC and BASE_SPEC.loader
BASE_MODULE = importlib.util.module_from_spec(BASE_SPEC)
sys.modules[BASE_SPEC.name] = BASE_MODULE
BASE_SPEC.loader.exec_module(BASE_MODULE)
ARM_SWING, PHASES, POSES = BASE_MODULE.ARM_SWING, BASE_MODULE.PHASES, BASE_MODULE.POSES


CELL = 384
S = 3
OUTLINE = (15, 13, 12, 255)


def _p(point):
    return tuple(round(value * S) for value in point)


def _texture(source: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    patch = source.crop(box).convert("RGBA")
    pixels = list(patch.getdata())
    foreground = [pixel for pixel in pixels if not (pixel[0] > 180 and pixel[1] > 180 and pixel[2] > 180 and max(pixel[:3]) - min(pixel[:3]) < 24)]
    if foreground:
        fill = tuple(sum(pixel[channel] for pixel in foreground) // len(foreground) for channel in range(3)) + (255,)
        patch.putdata([
            fill if (pixel[0] > 180 and pixel[1] > 180 and pixel[2] > 180 and max(pixel[:3]) - min(pixel[:3]) < 24) else pixel
            for pixel in pixels
        ])
    patch.thumbnail((220, 220), Image.Resampling.LANCZOS)
    tiled = Image.new("RGBA", (CELL, CELL))
    for y in range(0, CELL, patch.height):
        for x in range(0, CELL, patch.width):
            tiled.alpha_composite(patch, (x, y))
    return tiled


def _relative_box(source: Image.Image, values: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    width, height = source.size
    return tuple(round(value * (width if index % 2 == 0 else height)) for index, value in enumerate(values))


def _paint(target: Image.Image, mask: Image.Image, texture: Image.Image, outline: int = 3) -> None:
    edge = mask.filter(ImageFilter.MaxFilter(outline * 2 + 1))
    border = Image.new("RGBA", target.size, OUTLINE)
    target.alpha_composite(Image.composite(border, Image.new("RGBA", target.size), edge))
    textured = texture.copy()
    textured.putalpha(mask)
    target.alpha_composite(textured)


def _segment_mask(points, width: int) -> Image.Image:
    mask = Image.new("L", (CELL, CELL), 0)
    draw = ImageDraw.Draw(mask)
    scaled = [_p(point) for point in points]
    draw.line(scaled, fill=255, width=width, joint="curve")
    radius = width // 2
    for x, y in scaled:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
    return mask


def _leg(target: Image.Image, pose, texture: Image.Image, boot: Image.Image) -> None:
    hip, knee, ankle, toe = pose
    _paint(target, _segment_mask((hip, knee), 38), texture)
    _paint(target, _segment_mask((knee, ankle), 36), boot)
    direction = 1 if toe >= ankle[0] else -1
    foot = [
        (ankle[0] - 6, ankle[1] - 2), (toe, 110),
        (toe + direction * 2, 117), (ankle[0] - direction * 8, 118),
    ]
    mask = Image.new("L", (CELL, CELL), 0)
    ImageDraw.Draw(mask).polygon([_p(point) for point in foot], fill=255)
    _paint(target, mask, boot)


def _arm(target: Image.Image, root, swing: float, texture: Image.Image) -> None:
    elbow = (round(root[0] + swing * 8), root[1] + 18)
    hand = (round(root[0] + swing * 15), root[1] + 35)
    _paint(target, _segment_mask((root, elbow, hand), 34), texture)


def render_frame(index: int, textures: dict[str, Image.Image]) -> Image.Image:
    pose = POSES[index]
    bob = pose["bob"]
    image = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    left_front = index < 3
    order = (("right", "left") if left_front else ("left", "right"))
    for side in order:
        _leg(image, pose[side], textures[f"pants_{side}"], textures["boot"])

    swing = ARM_SWING[index]
    _arm(image, (51, 48 + bob), -swing, textures["skin_dark"])

    torso_mask = Image.new("L", image.size, 0)
    td = ImageDraw.Draw(torso_mask)
    td.ellipse((120, (37 + bob) * S, 238, (82 + bob) * S), fill=255)
    td.polygon([_p(point) for point in ((43, 40 + bob), (72, 40 + bob), (79, 73 + bob), (39, 73 + bob))], fill=255)
    _paint(image, torso_mask, textures["leather"], outline=6)

    belt = Image.new("L", image.size, 0)
    ImageDraw.Draw(belt).rounded_rectangle((120, (67 + bob) * S, 234, (76 + bob) * S), radius=6, fill=255)
    _paint(image, belt, textures["belt"], outline=3)
    _arm(image, (70, 47 + bob), swing, textures["skin"])

    head = Image.new("L", image.size, 0)
    hd = ImageDraw.Draw(head)
    hd.ellipse((39 * S, (12 + bob) * S, 75 * S, (48 + bob) * S), fill=255)
    hd.polygon([_p(point) for point in ((43, 23 + bob), (28, 29 + bob), (43, 36 + bob))], fill=255)
    hd.rounded_rectangle((55 * S, (30 + bob) * S, 81 * S, (47 + bob) * S), radius=14, fill=255)
    _paint(image, head, textures["head"], outline=6)

    draw = ImageDraw.Draw(image)
    draw.line((_p((47, 25 + bob)), _p((68, 23 + bob))), fill=(92, 96, 96, 255), width=9)
    draw.ellipse((62 * S, (25 + bob) * S, 68 * S, (31 + bob) * S), fill=(228, 151, 57, 255), outline=OUTLINE, width=4)
    draw.line((_p((55, 38 + bob)), _p((77, 40 + bob))), fill=OUTLINE, width=6)
    for x in (66, 74):
        draw.polygon([_p((x, 40 + bob)), _p((x + 5, 49 + bob)), _p((x - 4, 45 + bob))], fill=(224, 209, 172, 255), outline=OUTLINE)
    return image


def build(source_path: Path, output: Path, fps: int = 8) -> dict:
    source = Image.open(source_path).convert("RGBA")
    textures = {
        "head": _texture(source, _relative_box(source, (.38, .06, .61, .27))),
        "skin": _texture(source, _relative_box(source, (.25, .27, .38, .55))),
        "skin_dark": _texture(source, _relative_box(source, (.63, .27, .73, .55))),
        "leather": _texture(source, _relative_box(source, (.38, .27, .62, .47))),
        "belt": _texture(source, _relative_box(source, (.38, .48, .63, .55))),
        "pants_left": _texture(source, _relative_box(source, (.31, .55, .47, .74))),
        "pants_right": _texture(source, _relative_box(source, (.52, .55, .68, .74))),
        "boot": _texture(source, _relative_box(source, (.27, .76, .43, .92))),
    }
    frames = [render_frame(index, textures) for index in range(6)]
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, frame in enumerate(frames, 1):
        path = output / f"walk_{index:02d}.png"
        frame.save(path)
        paths.append(str(path))
    sheet = Image.new("RGBA", (CELL * 6, CELL), (0, 0, 0, 0))
    qa_sheet = Image.new("RGBA", sheet.size, (218, 218, 214, 255))
    qa_frames = []
    for index, frame in enumerate(frames):
        sheet.alpha_composite(frame, (CELL * index, 0))
        qa = Image.new("RGBA", frame.size, (218, 218, 214, 255))
        qa.alpha_composite(frame)
        qa_frames.append(qa)
        qa_sheet.alpha_composite(qa, (CELL * index, 0))
    sheet_path = output / "walk6_sheet.png"
    qa_sheet_path = output / "walk6_qa_sheet.png"
    gif_path = output / "walk6_preview.gif"
    qa_gif_path = output / "walk6_qa_preview.gif"
    sheet.save(sheet_path)
    qa_sheet.save(qa_sheet_path)
    frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=round(1000 / fps), loop=0, disposal=2)
    qa_frames[0].save(qa_gif_path, save_all=True, append_images=qa_frames[1:], duration=round(1000 / fps), loop=0, disposal=2)
    manifest = {
        "method": "canonical-texture-part-rig",
        "source": str(source_path), "frames": 6, "fps": fps, "phase_order": PHASES,
        "frame_paths": paths, "sheet": str(sheet_path), "preview": str(gif_path),
        "qa_sheet": str(qa_sheet_path), "qa_preview": str(qa_gif_path),
    }
    (output / "walk6_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fps", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.fps), indent=2))


if __name__ == "__main__":
    main()
