"""Build a front-facing idle atlas directly from an approved character reference."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from asset_studio.local_3d_pipeline import (  # noqa: E402
    _preview_gif_bytes,
    build_reference_idle_sheet,
    pixelize_action_sheet,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("identity", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--resolution", type=int, choices=(48, 64, 96), default=96)
    parser.add_argument("--palette", type=int, choices=(16, 24, 32), default=32)
    args = parser.parse_args()

    with Image.open(args.identity.resolve()) as source:
        master = build_reference_idle_sheet(source.convert("RGBA"))
    atlas, frames, qa = pixelize_action_sheet(
        master,
        cell_width=args.resolution,
        palette_colors=args.palette,
    )

    output = args.output.resolve()
    frames_output = output / "frames"
    frames_output.mkdir(parents=True, exist_ok=True)
    master.save(output / "idle_source_4x2.png")
    atlas_path = output / f"idle_{args.resolution}x{args.resolution * 2}_atlas.png"
    preview_path = output / "idle_preview.gif"
    atlas.save(atlas_path)
    preview_path.write_bytes(_preview_gif_bytes(frames, "idle"))
    for index, frame in enumerate(frames):
        frame.save(frames_output / f"idle_{index:02d}.png")
    metadata = {
        "success": True,
        "method": "approved-reference+bottom-anchored-breathing+shared-palette-pixelization",
        "action": "idle",
        "direction": "S",
        "frame_count": 8,
        "frame_width": args.resolution,
        "frame_height": args.resolution * 2,
        "identity_locked": True,
        "feet_locked": True,
        "qa": qa,
        "atlas": str(atlas_path),
        "preview": str(preview_path),
    }
    (output / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
