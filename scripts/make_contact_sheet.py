"""Build a compact labeled PNG contact sheet from rendered frames."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--columns", default=4, type=int)
    parser.add_argument("--width", default=192, type=int)
    parser.add_argument("--no-labels", action="store_true")
    parser.add_argument("--fit-subject", action="store_true")
    return parser.parse_args()


def fitted_frame(source: Image.Image, frame_size: tuple[int, int]) -> Image.Image:
    rgba = source.convert("RGBA")
    bounds = rgba.getchannel("A").getbbox()
    if bounds is None:
        return Image.new("RGB", frame_size, (243, 245, 247))
    subject = rgba.crop(bounds)
    padding_x = max(4, round(frame_size[0] * 0.08))
    padding_y = max(4, round(frame_size[1] * 0.05))
    scale = min(
        (frame_size[0] - padding_x * 2) / max(1, subject.width),
        (frame_size[1] - padding_y * 2) / max(1, subject.height),
    )
    subject = subject.resize(
        (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
        Image.Resampling.LANCZOS,
    )
    frame = Image.new("RGB", frame_size, (243, 245, 247))
    x = (frame_size[0] - subject.width) // 2
    y = frame_size[1] - padding_y - subject.height
    frame.paste(subject.convert("RGB"), (x, y), subject.getchannel("A"))
    return frame


def main() -> None:
    args = arguments()
    files = sorted(args.input.glob(args.pattern))
    if not files:
        raise SystemExit(f"No frames matched {args.pattern!r}")
    with Image.open(files[0]) as first:
        ratio = first.height / first.width
    frame_size = (args.width, round(args.width * ratio))
    label_height = 0 if args.no_labels else 24
    rows = (len(files) + args.columns - 1) // args.columns
    sheet = Image.new(
        "RGB",
        (args.columns * frame_size[0], rows * (frame_size[1] + label_height)),
        (19, 23, 31),
    )
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(files):
        with Image.open(path) as source:
            frame = fitted_frame(source, frame_size) if args.fit_subject else source.convert("RGB").resize(frame_size, Image.Resampling.LANCZOS)
        x = (index % args.columns) * frame_size[0]
        y = (index // args.columns) * (frame_size[1] + label_height)
        sheet.paste(frame, (x, y))
        if not args.no_labels:
            draw.text((x + 7, y + frame_size[1] + 4), f"{index + 1:02d}", fill=(225, 231, 240))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
