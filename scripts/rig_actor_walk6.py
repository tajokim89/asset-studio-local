#!/usr/bin/env python3
"""Build a deterministic six-frame walk cycle from one transparent actor image.

This is deliberately not an image-to-video workflow.  Appearance is sampled once,
split into reusable body layers, then animated with a fixed six-pose skeleton.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


FRAME_COUNT = 6
LEG_PHASES = (-18, -10, 0, 18, 10, 0)
ROOT_BOB = (0, 3, 1, 0, 3, 1)
LEFT_KNEE_PHASES = (2, 14, 22, 4, 8, 5)
RIGHT_KNEE_PHASES = (4, 8, 5, 2, 14, 22)
LEFT_LEG_TRANSLATION = ((88, 0), (68, 1), (38, -5), (48, -8), (38, -6), (25, -10))
RIGHT_LEG_TRANSLATION = ((-48, -8), (-38, -6), (-25, -10), (-88, 0), (-68, 1), (-38, -5))


@dataclass(frozen=True)
class Rig:
    left_hip: tuple[int, int]
    right_hip: tuple[int, int]
    left_knee: tuple[int, int]
    right_knee: tuple[int, int]
    baseline: int


def _fit_actor(source: Image.Image, canvas: int) -> Image.Image:
    actor = source.convert("RGBA")
    # The production reference can be a flattened preview on a plain background.
    # Key only the corner-derived neutral background; never rebuild body textures.
    corners = [actor.getpixel((0, 0)), actor.getpixel((actor.width - 1, 0)), actor.getpixel((0, actor.height - 1)), actor.getpixel((actor.width - 1, actor.height - 1))]
    bg = tuple(sum(pixel[channel] for pixel in corners) // len(corners) for channel in range(3))
    pixels = []
    for red, green, blue, alpha in actor.getdata():
        distance = max(abs(red - bg[0]), abs(green - bg[1]), abs(blue - bg[2]))
        pixels.append((red, green, blue, 0 if distance < 18 else alpha))
    actor.putdata(pixels)
    bbox = actor.getchannel("A").getbbox()
    if bbox:
        actor = actor.crop(bbox)
    actor.thumbnail((round(canvas * 0.72), round(canvas * 0.96)), Image.Resampling.LANCZOS)
    fitted = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    fitted.alpha_composite(actor, ((canvas - actor.width) // 2, canvas - actor.height - 4))
    return fitted


def _polygon_mask(size: tuple[int, int], points: list[tuple[float, float]]) -> Image.Image:
    w, h = size
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon([(round(x * w), round(y * h)) for x, y in points], fill=255)
    return mask


def _masked(image: Image.Image, shape: Image.Image) -> Image.Image:
    layer = image.copy()
    layer.putalpha(ImageChops.multiply(image.getchannel("A"), shape))
    return layer


def split_layers(actor: Image.Image) -> dict[str, Image.Image]:
    """Split a front/three-quarter humanoid into overlapping rig-safe layers."""
    size = actor.size
    masks = {
        "left_thigh": _polygon_mask(size, [(.24, .48), (.51, .47), (.50, .76), (.24, .76)]),
        "right_thigh": _polygon_mask(size, [(.49, .47), (.76, .48), (.76, .76), (.50, .76)]),
        "left_shin": _polygon_mask(size, [(.20, .68), (.51, .68), (.51, .98), (.18, .98)]),
        "right_shin": _polygon_mask(size, [(.49, .68), (.80, .68), (.82, .98), (.49, .98)]),
        # A flattened source does not contain the pixels hidden behind bent arms.
        # Preserve the complete upper body instead of inventing destructive arm cuts.
        "upper_body": _polygon_mask(size, [(.00, .00), (1.00, .00), (1.00, .63), (.00, .63)]),
    }
    return {name: _masked(actor, mask) for name, mask in masks.items()}


def default_rig(canvas: int) -> Rig:
    return Rig(
        left_hip=(round(canvas * .445), round(canvas * .535)),
        right_hip=(round(canvas * .555), round(canvas * .535)),
        left_knee=(round(canvas * .405), round(canvas * .735)),
        right_knee=(round(canvas * .595), round(canvas * .735)),
        baseline=round(canvas * .97),
    )


def _rotate(layer: Image.Image, degrees: float, pivot: tuple[int, int]) -> Image.Image:
    return layer.rotate(degrees, resample=Image.Resampling.BICUBIC, center=pivot)


def _rotate_point(point: tuple[int, int], pivot: tuple[int, int], degrees: float) -> tuple[int, int]:
    from math import cos, radians, sin

    angle = radians(degrees)
    x, y = point[0] - pivot[0], point[1] - pivot[1]
    return (
        round(pivot[0] + x * cos(angle) - y * sin(angle)),
        round(pivot[1] + x * sin(angle) + y * cos(angle)),
    )


def _two_bone(
    upper: Image.Image,
    lower: Image.Image,
    root: tuple[int, int],
    joint: tuple[int, int],
    root_angle: float,
    joint_angle: float,
) -> tuple[Image.Image, Image.Image]:
    moved_upper = _rotate(upper, root_angle, root)
    moved_joint = _rotate_point(joint, root, root_angle)
    moved_lower = _rotate(_rotate(lower, root_angle, root), joint_angle, moved_joint)
    return moved_upper, moved_lower


def _translate(layer: Image.Image, offset: tuple[int, int]) -> Image.Image:
    moved = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    moved.alpha_composite(layer, offset)
    return moved


def render_walk6(source: Image.Image, canvas: int = 384) -> tuple[list[Image.Image], Rig]:
    actor = _fit_actor(source, canvas)
    layers = split_layers(actor)
    rig = default_rig(canvas)
    frames: list[Image.Image] = []

    for index in range(FRAME_COUNT):
        left_thigh, left_shin = _two_bone(
            layers["left_thigh"], layers["left_shin"], rig.left_hip, rig.left_knee,
            LEG_PHASES[index], LEFT_KNEE_PHASES[index],
        )
        right_thigh, right_shin = _two_bone(
            layers["right_thigh"], layers["right_shin"], rig.right_hip, rig.right_knee,
            -LEG_PHASES[index], -RIGHT_KNEE_PHASES[index],
        )
        left_thigh = _translate(left_thigh, LEFT_LEG_TRANSLATION[index])
        left_shin = _translate(left_shin, LEFT_LEG_TRANSLATION[index])
        right_thigh = _translate(right_thigh, RIGHT_LEG_TRANSLATION[index])
        right_shin = _translate(right_shin, RIGHT_LEG_TRANSLATION[index])
        pose = Image.new("RGBA", actor.size, (0, 0, 0, 0))
        # Legs move behind one untouched upper-body layer.  This preserves identity,
        # clothing and hands exactly when the source has no reconstructable arm layers.
        for layer in (
            right_shin, right_thigh, left_shin, left_thigh, layers["upper_body"],
        ):
            pose.alpha_composite(layer)

        bbox = pose.getchannel("A").getbbox()
        if bbox:
            # Keep every footfall on one production baseline; the small root bob is explicit.
            offset = rig.baseline + ROOT_BOB[index] - bbox[3]
            shifted = Image.new("RGBA", pose.size, (0, 0, 0, 0))
            shifted.alpha_composite(pose, (0, offset))
            pose = shifted
        frames.append(pose)
    return frames, rig


def save_package(frames: list[Image.Image], rig: Rig, output: Path, fps: int = 8) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    width, height = frames[0].size
    sheet = Image.new("RGBA", (width * len(frames), height), (0, 0, 0, 0))
    frame_paths = []
    for index, frame in enumerate(frames, 1):
        path = output / f"walk_{index:02d}.png"
        frame.save(path)
        frame_paths.append(str(path))
        sheet.alpha_composite(frame, ((index - 1) * width, 0))
    sheet_path = output / "walk6_sheet.png"
    sheet.save(sheet_path)

    gif_path = output / "walk6_preview.gif"
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=round(1000 / fps),
        loop=0,
        disposal=2,
    )
    manifest = {
        "method": "layered-2d-rig",
        "frames": FRAME_COUNT,
        "fps": fps,
        "canvas": [width, height],
        "phase_order": ["left_contact", "left_down", "left_pass", "right_contact", "right_down", "right_pass"],
        "rig": {
            "left_hip": rig.left_hip,
            "right_hip": rig.right_hip,
            "left_knee": rig.left_knee,
            "right_knee": rig.right_knee,
            "baseline": rig.baseline,
        },
        "frame_paths": frame_paths,
        "sheet": str(sheet_path),
        "preview": str(gif_path),
    }
    manifest_path = output / "walk6_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--canvas", type=int, default=384)
    parser.add_argument("--fps", type=int, default=8)
    args = parser.parse_args()
    frames, rig = render_walk6(Image.open(args.source), args.canvas)
    print(json.dumps(save_package(frames, rig, args.output, args.fps), indent=2))


if __name__ == "__main__":
    main()
