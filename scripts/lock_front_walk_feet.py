"""Lock a front-view walk to canonical shoe sprites with a small foot-stomp cycle."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def is_green(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, _alpha = pixel
    return green >= 100 and green - max(red, blue) >= 35


def foreground_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    rgba = image.convert("RGBA")
    xs: list[int] = []
    ys: list[int] = []
    for y in range(rgba.height):
        for x in range(rgba.width):
            if not is_green(rgba.getpixel((x, y))):
                xs.append(x)
                ys.append(y)
    if not xs:
        raise ValueError("source frame has no foreground")
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def keyed_crop(
    image: Image.Image,
    box: tuple[int, int, int, int],
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    crop = image.convert("RGBA").crop(box)
    data = []
    pixels = crop.get_flattened_data() if hasattr(crop, "get_flattened_data") else crop.getdata()
    for pixel in pixels:
        data.append((*pixel[:3], 0 if is_green(pixel) else 255))
    crop.putdata(data)
    alpha_box = crop.getchannel("A").getbbox()
    if alpha_box is None:
        raise ValueError(f"empty canonical foot crop: {box}")
    global_box = (
        box[0] + alpha_box[0],
        box[1] + alpha_box[1],
        box[0] + alpha_box[2],
        box[1] + alpha_box[3],
    )
    return crop.crop(alpha_box), global_box


def paste_keyed(canvas: Image.Image, sprite: Image.Image, center_x: int, bottom_y: int) -> None:
    x = round(center_x - sprite.width / 2)
    y = bottom_y - sprite.height
    canvas.alpha_composite(sprite, (x, y))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--pattern", default="frame_*.png")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fps", type=float, default=16.0)
    args = parser.parse_args()

    sources = sorted(args.input.glob(args.pattern))
    if len(sources) != 17:
        raise SystemExit(f"Expected exactly 17 input frames, found {len(sources)}")

    with Image.open(sources[0]) as opened:
        canonical = opened.convert("RGBA")
    left, top, right, bottom = foreground_bbox(canonical)
    center = (left + right) // 2
    foot_top = bottom - max(46, round((bottom - top) * 0.13))
    left_sprite, left_box = keyed_crop(canonical, (left, foot_top, center, bottom))
    right_sprite, right_box = keyed_crop(canonical, (center, foot_top, right, bottom))

    left_center = round((left_box[0] + left_box[2]) / 2)
    right_center = round((right_box[0] + right_box[2]) / 2)
    erase_top = bottom - 44
    erase_left = left - 10
    erase_right = right + 10

    left_lift = [0, 3, 6, 10, 6, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    right_lift = [0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 6, 10, 6, 3, 0, 0, 0]

    args.output.mkdir(parents=True, exist_ok=True)
    rendered: list[Image.Image] = []
    for index, source in enumerate(sources):
        with Image.open(source) as opened:
            frame = opened.convert("RGBA")
        green = frame.getpixel((0, 0))[:3]
        erase = Image.new(
            "RGBA",
            (erase_right - erase_left, frame.height - erase_top),
            (*green, 255),
        )
        frame.alpha_composite(erase, (erase_left, erase_top))
        paste_keyed(frame, left_sprite, left_center, bottom - left_lift[index])
        paste_keyed(frame, right_sprite, right_center, bottom - right_lift[index])
        normalized = []
        frame_pixels = frame.get_flattened_data() if hasattr(frame, "get_flattened_data") else frame.getdata()
        for pixel in frame_pixels:
            normalized.append((0, 255, 0, 255) if is_green(pixel) else pixel)
        frame.putdata(normalized)
        output = args.output / f"frame_{index + 1:05d}_.png"
        frame.convert("RGB").save(output)
        rendered.append(frame.convert("RGB"))

    rendered[0].save(
        args.output / "preview.gif",
        save_all=True,
        append_images=rendered[1:],
        duration=max(10, round(1000 / args.fps)),
        loop=0,
        disposal=2,
        optimize=False,
    )
    print(
        {
            "frames": len(rendered),
            "left_sprite": left_sprite.size,
            "right_sprite": right_sprite.size,
            "foot_top": foot_top,
            "baseline": bottom,
            "preview": str((args.output / "preview.gif").resolve()),
        }
    )


if __name__ == "__main__":
    main()
