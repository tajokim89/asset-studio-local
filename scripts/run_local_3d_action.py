"""Run the Asset Studio local 3D action pipeline without opening the browser."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from asset_studio.local_3d_pipeline import generate_local_action_sheet  # noqa: E402


def image_data_url(path: Path) -> str:
    extension = path.suffix.lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(extension)
    if mime is None:
        raise ValueError(f"지원하지 않는 이미지 형식입니다: {extension}")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description="3D 렌더 가이드 시트를 로컬 ComfyUI 픽셀 애니메이션으로 변환합니다.")
    parser.add_argument("guide", type=Path, help="4x2 배열의 8프레임 3D 렌더 시트")
    parser.add_argument("output", type=Path, help="결과를 저장할 폴더")
    parser.add_argument("--identity", type=Path, help="캐릭터 원본 2D 기준 이미지")
    parser.add_argument("--action", choices=("idle", "walk", "run"), default="walk")
    parser.add_argument("--direction", default="S")
    parser.add_argument("--resolution", type=int, choices=(48, 64, 96), default=64)
    parser.add_argument("--palette", type=int, choices=(16, 24, 32), default=24)
    parser.add_argument("--style", default="32-bit refined RPG")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    guide_url = image_data_url(args.guide.resolve())
    result = generate_local_action_sheet({
        "guide_sheet": guide_url,
        "identity_image": image_data_url(args.identity.resolve()) if args.identity else guide_url,
        "action": args.action,
        "direction": args.direction,
        "resolution": args.resolution,
        "palette_colors": args.palette,
        "style": args.style,
        "seed": args.seed,
    })

    output = args.output.resolve()
    frames = output / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    metadata = result["metadata"]
    atlas_name = f"{args.action}_{metadata['frame_width']}x{metadata['frame_height']}_atlas.png"
    (output / atlas_name).write_bytes(result["atlas"])
    (output / f"{args.action}_preview.gif").write_bytes(result["preview"])
    for index, frame in enumerate(result["frames"]):
        (frames / f"{args.action}_{index:02d}.png").write_bytes(frame)
    (output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"success": True, "output": str(output), **metadata}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
