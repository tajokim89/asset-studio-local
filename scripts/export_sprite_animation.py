"""Export real source frames with independent game and review playback speeds."""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image


def read_frames(source):
    source = Path(source)
    frames = []
    if source.is_dir():
        paths = sorted(source.glob('*.png'))
        for path in paths:
            with Image.open(path) as image:
                frames.append(image.convert('RGBA'))
    else:
        with Image.open(source) as image:
            for index in range(getattr(image, 'n_frames', 1)):
                image.seek(index)
                frames.append(image.convert('RGBA'))
    if not frames or len({frame.size for frame in frames}) != 1:
        raise ValueError('Input must contain same-sized frames; PNG names must be zero-padded.')
    return frames


def select_indices(total, count=None, indices=None):
    if indices is not None:
        selected = list(indices)
    elif count is not None:
        if not 2 <= count <= total:
            raise ValueError('count must be between 2 and the number of input frames')
        selected = [round(i * (total - 1) / (count - 1)) for i in range(count)]
    else:
        selected = list(range(total))
    if len(selected) < 2 or len(set(selected)) != len(selected):
        raise ValueError('Choose at least two distinct source frame indices')
    if selected != sorted(selected) or min(selected) < 0 or max(selected) >= total:
        raise ValueError('Frame indices must be ascending and within the input')
    return selected


def remove_green(image):
    """For non-green subjects only: remove green matte and unmix green spill."""
    rgba = np.array(image.convert('RGBA'))
    rgb = rgba[:, :, :3].astype(np.float32)
    excess = rgb[:, :, 1] - np.maximum(rgb[:, :, 0], rgb[:, :, 2])
    clear = (excess > 12) & (excess > rgb[:, :, 1] * .25)
    spill = (excess > 0) & ~clear
    matte = np.clip(excess / 255, 0, 1)
    alpha = np.maximum(1 - matte, .001)
    recovered = rgb.copy()
    recovered[:, :, 1] -= matte * 255
    recovered = np.clip(recovered / alpha[:, :, None], 0, 255)
    rgba[spill, :3] = np.rint(recovered[spill]).astype('uint8')
    rgba[spill, 3] = np.rint(rgba[spill, 3] * alpha[spill]).astype('uint8')
    rgba[clear] = 0
    rgba[rgba[:, :, 3] == 0, :3] = 0
    return Image.fromarray(rgba)


def frame_durations(count, fps):
    if not math.isfinite(fps) or not 1 <= fps <= 60:
        raise ValueError('fps must be between 1 and 60')
    # GIF uses 10ms units. Distribute rounding, rather than rounding each frame.
    boundaries = [round(i * 100 / fps) * 10 for i in range(count + 1)]
    return [b - a for a, b in zip(boundaries, boundaries[1:])]


def write_gif(frames, path, durations):
    paletted = []
    for frame in frames:
        image = frame.convert('RGB').quantize(colors=255, dither=Image.Dither.NONE)
        image.paste(255, mask=frame.getchannel('A').point(lambda a: 255 if a < 128 else 0))
        image.info['transparency'] = 255
        paletted.append(image)
    paletted[0].save(path, save_all=True, append_images=paletted[1:], duration=durations,
                     loop=0, disposal=2, transparency=255, optimize=False)


def export(source, output, *, count=None, indices=None, fps=12, preview_ms=150, green=False):
    original = read_frames(source)
    selected = select_indices(len(original), count, indices)
    durations = frame_durations(len(selected), fps)
    if preview_ms < 20 or preview_ms % 10:
        raise ValueError('preview-ms must be a multiple of 10, at least 20')
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Choose an empty output directory; source files are never overwritten')
    output.mkdir(parents=True, exist_ok=True)
    frames = [remove_green(original[i]) if green else original[i] for i in selected]
    width, height = frames[0].size
    columns = math.ceil(math.sqrt(len(frames)))
    rows = math.ceil(len(frames) / columns)
    sheet = Image.new('RGBA', (width * columns, height * rows))
    for n, frame in enumerate(frames):
        frame.save(output / f'frame_{n:03}.png')
        sheet.paste(frame, ((n % columns) * width, (n // columns) * height))
    sheet.save(output / 'sheet.png')
    write_gif(frames, output / 'animation.gif', durations)
    write_gif(frames, output / 'review-slow.gif', [preview_ms] * len(frames))
    with Image.open(output / 'animation.gif') as gif:
        encoded_count = gif.n_frames
    metadata = dict(source_frame_count=len(original), sample_indices=selected,
                    frame_count=len(frames), gif_frame_count=encoded_count, fps=fps,
                    frame_durations_ms=durations, duration_ms=sum(durations),
                    preview_frame_ms=preview_ms, preview_duration_ms=preview_ms * len(frames),
                    columns=columns, rows=rows, cell_width=width, cell_height=height,
                    green_removed=green)
    if encoded_count != len(frames):
        metadata['warning'] = 'GIF encoder merged visually identical frames; PNG frames retain every selection.'
    (output / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--count', type=int)
    group.add_argument('--indices', help='Ascending comma-separated real source indices')
    parser.add_argument('--fps', type=float, default=12)
    parser.add_argument('--preview-ms', type=int, default=150)
    parser.add_argument('--remove-green', action='store_true', help='Only for subjects with no green material')
    args = parser.parse_args()
    indices = [int(n) for n in args.indices.split(',')] if args.indices else None
    print(json.dumps(export(args.input, args.output, count=args.count, indices=indices,
                            fps=args.fps, preview_ms=args.preview_ms, green=args.remove_green)))


if __name__ == '__main__':
    main()
