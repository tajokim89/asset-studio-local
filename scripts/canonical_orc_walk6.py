#!/usr/bin/env python3
"""Canonical, reusable six-frame chibi walk rig with an orc appearance skin."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


SCALE = 3
CELL = 128
PHASES = ("left_contact", "left_down", "left_pass", "right_contact", "right_down", "right_pass")
ARM_SWING = (1.0, 0.55, 0.0, -1.0, -0.55, 0.0)

SKIN = "#303335"
SKIN_LIGHT = "#44484a"
OUTLINE = "#151719"
LEATHER = "#633a22"
LEATHER_LIGHT = "#855336"
PANTS = "#3f2d24"
BOOT = "#4e2f20"
METAL = "#b58b4e"


POSES = (
    {"bob": 0, "left": ((61, 74), (72, 91), (82, 110), 94), "right": ((58, 74), (50, 92), (43, 111), 34)},
    {"bob": 3, "left": ((61, 77), (74, 97), (82, 111), 93), "right": ((58, 77), (51, 98), (45, 111), 36)},
    {"bob": 1, "left": ((61, 75), (57, 93), (53, 111), 44), "right": ((58, 75), (67, 91), (63, 104), 72)},
    {"bob": 0, "left": ((61, 74), (50, 92), (43, 111), 34), "right": ((58, 74), (72, 91), (82, 110), 94)},
    {"bob": 3, "left": ((61, 77), (51, 98), (45, 111), 36), "right": ((58, 77), (74, 97), (82, 111), 93)},
    {"bob": 1, "left": ((61, 75), (67, 91), (63, 104), 72), "right": ((58, 75), (57, 93), (53, 111), 44)},
)


def _segment(draw: ImageDraw.ImageDraw, points, fill: str, width: int, outline: str = OUTLINE) -> None:
    draw.line(points, fill=outline, width=width + 4, joint="curve")
    draw.line(points, fill=fill, width=width, joint="curve")
    radius = width // 2
    for x, y in points:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill, outline=outline, width=2)


def _leg(layer: Image.Image, pose, front: bool, side: str) -> None:
    hip, knee, ankle, toe = pose
    draw = ImageDraw.Draw(layer)
    tone = "#493329" if side == "left" else "#34251f"
    boot_tone = "#5b3825" if side == "left" else "#3b271d"
    _segment(draw, (hip, knee), tone, 13)
    _segment(draw, (knee, ankle), boot_tone, 12)
    direction = 1 if toe >= ankle[0] else -1
    foot = [(ankle[0] - 6, ankle[1] - 2), (toe, 110), (toe + direction * 2, 116), (ankle[0] - direction * 7, 117)]
    draw.polygon(foot, fill=boot_tone, outline=OUTLINE)
    draw.line((foot[-1], foot[-2]), fill=LEATHER_LIGHT, width=2)


def _arm(layer: Image.Image, root: tuple[int, int], swing: float, front: bool) -> None:
    shoulder = root
    elbow = (round(root[0] + swing * 8), root[1] + 18)
    hand = (round(root[0] + swing * 15), root[1] + 35)
    _segment(ImageDraw.Draw(layer), (shoulder, elbow, hand), SKIN_LIGHT if front else "#292c2e", 11)


def render_frame(index: int) -> Image.Image:
    pose = POSES[index]
    bob = pose["bob"]
    image = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))

    left_front = index < 3
    back_leg, front_leg = (("right", "left") if left_front else ("left", "right"))
    for name, front in ((back_leg, False), (front_leg, True)):
        layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        _leg(layer, pose[name], front, name)
        image.alpha_composite(layer)

    # Both arms exist in every pose and move through continuous opposite phases.
    swing = ARM_SWING[index]
    back_arm = Image.new("RGBA", image.size, (0, 0, 0, 0))
    _arm(back_arm, (51, 48 + bob), -swing, front=False)
    image.alpha_composite(back_arm)

    draw = ImageDraw.Draw(image)
    # Torso and leather armor are canonical layers; appearance can be replaced independently.
    draw.ellipse((40, 38 + bob, 78, 79 + bob), fill=OUTLINE)
    draw.polygon([(43, 40 + bob), (72, 40 + bob), (78, 72 + bob), (40, 72 + bob)], fill=LEATHER, outline=OUTLINE)
    draw.polygon([(45, 43 + bob), (57, 56 + bob), (70, 42 + bob), (73, 50 + bob), (58, 63 + bob)], fill=LEATHER_LIGHT)
    draw.rectangle((41, 67 + bob, 77, 75 + bob), fill=LEATHER, outline=OUTLINE)
    draw.rectangle((56, 68 + bob, 64, 75 + bob), fill=METAL, outline=OUTLINE)

    front_arm = Image.new("RGBA", image.size, (0, 0, 0, 0))
    _arm(front_arm, (70, 47 + bob), swing, front=True)
    image.alpha_composite(front_arm)

    draw = ImageDraw.Draw(image)
    # Side-facing orc head: bald skull, pointed ear, heavy brow, jaw and tusks.
    draw.ellipse((39, 13 + bob, 73, 47 + bob), fill=OUTLINE)
    draw.ellipse((42, 15 + bob, 71, 45 + bob), fill=SKIN)
    draw.polygon([(43, 24 + bob), (29, 29 + bob), (43, 35 + bob)], fill=SKIN, outline=OUTLINE)
    draw.ellipse((61, 29 + bob, 79, 43 + bob), fill=SKIN, outline=OUTLINE)
    draw.rectangle((53, 36 + bob, 75, 47 + bob), fill=SKIN, outline=OUTLINE)
    draw.line((48, 25 + bob, 66, 23 + bob), fill=SKIN_LIGHT, width=4)
    draw.ellipse((62, 25 + bob, 67, 30 + bob), fill="#e5a447", outline=OUTLINE)
    draw.polygon([(66, 40 + bob), (70, 48 + bob), (62, 44 + bob)], fill="#e5d6b0", outline=OUTLINE)
    draw.polygon([(73, 39 + bob), (78, 46 + bob), (70, 44 + bob)], fill="#e5d6b0", outline=OUTLINE)
    draw.line((55, 38 + bob, 76, 40 + bob), fill=OUTLINE, width=2)
    return image


def build(output: Path, fps: int = 8) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    small = [render_frame(i) for i in range(6)]
    frames = [frame.resize((CELL * SCALE, CELL * SCALE), Image.Resampling.NEAREST) for frame in small]
    paths = []
    for index, frame in enumerate(frames, 1):
        path = output / f"walk_{index:02d}.png"
        frame.save(path)
        paths.append(str(path))
    sheet = Image.new("RGBA", (CELL * SCALE * 6, CELL * SCALE), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        sheet.alpha_composite(frame, (index * CELL * SCALE, 0))
    sheet_path = output / "walk6_sheet.png"
    sheet.save(sheet_path)
    gif_path = output / "walk6_preview.gif"
    frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=round(1000 / fps), loop=0, disposal=2)
    qa_frames = []
    for frame in frames:
        background = Image.new("RGBA", frame.size, (220, 222, 218, 255))
        background.alpha_composite(frame)
        qa_frames.append(background)
    qa_sheet = Image.new("RGBA", sheet.size, (220, 222, 218, 255))
    for index, frame in enumerate(qa_frames):
        qa_sheet.alpha_composite(frame, (index * CELL * SCALE, 0))
    qa_sheet_path = output / "walk6_qa_sheet.png"
    qa_sheet.save(qa_sheet_path)
    qa_gif_path = output / "walk6_qa_preview.gif"
    qa_frames[0].save(qa_gif_path, save_all=True, append_images=qa_frames[1:], duration=round(1000 / fps), loop=0, disposal=2)
    manifest = {
        "method": "canonical-part-rig",
        "frames": 6,
        "fps": fps,
        "phase_order": PHASES,
        "frame_paths": paths,
        "sheet": str(sheet_path),
        "preview": str(gif_path),
        "qa_sheet": str(qa_sheet_path),
        "qa_preview": str(qa_gif_path),
    }
    (output / "walk6_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--fps", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.fps), indent=2))


if __name__ == "__main__":
    main()
