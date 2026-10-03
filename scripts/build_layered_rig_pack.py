"""Split one side-walk character pose into full-canvas paper-doll rig layers.

This is deterministic pixel masking, not generative inpainting. Pixels hidden in
the reference stay absent; the output never invents a second limb or texture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


PART_POLYGONS = {
    "near_lower_arm": [(724, 565), (810, 588), (855, 742), (770, 770), (742, 644)],
    "near_upper_arm": [(620, 337), (704, 365), (794, 584), (746, 654), (672, 493)],
    "near_foot": [(250, 1010), (505, 1010), (505, 1175), (250, 1175)],
    "near_shin": [(377, 828), (579, 850), (536, 1075), (373, 1090)],
    "near_thigh": [(460, 684), (633, 690), (620, 807), (560, 918), (424, 920)],
    "far_lower_arm": [(349, 570), (486, 566), (493, 637), (455, 690), (446, 727), (365, 731), (345, 665)],
    "far_upper_arm": [(512, 376), (611, 392), (553, 526), (479, 624), (407, 599), (457, 510)],
    "far_foot": [(750, 985), (935, 985), (935, 1170), (750, 1170)],
    "far_shin": [(650, 817), (807, 842), (884, 1044), (796, 1091), (701, 1010)],
    "far_thigh": [(570, 687), (704, 693), (775, 851), (689, 927), (566, 806)],
}

PART_ORDER = [
    "near_lower_arm",
    "near_upper_arm",
    "near_foot",
    "near_shin",
    "near_thigh",
    "far_lower_arm",
    "far_upper_arm",
    "far_foot",
    "far_shin",
    "far_thigh",
]

JOINTS = {
    "root": [620, 710],
    "shoulder_far": [594, 386],
    "elbow_far": [466, 578],
    "hip_far": [627, 728],
    "knee_far": [748, 903],
    "ankle_far": [837, 1035],
    "hip_near": [604, 728],
    "knee_near": [493, 920],
    "ankle_near": [402, 1052],
    "shoulder_near": [653, 386],
    "elbow_near": [762, 600],
}

CAPS = {
    "body": [
        ("shoulder_far", 38, (20, 18, 35, 255), (51, 47, 92, 255)),
        ("shoulder_near", 38, (20, 18, 35, 255), (51, 47, 92, 255)),
        ("hip_far", 45, (31, 24, 28, 255), (72, 55, 56, 255)),
        ("hip_near", 45, (31, 24, 28, 255), (72, 55, 56, 255)),
    ],
    "far_upper_arm": [("elbow_far", 30, (20, 18, 35, 255), (51, 47, 92, 255))],
    "near_upper_arm": [("elbow_near", 30, (20, 18, 35, 255), (51, 47, 92, 255))],
    "far_thigh": [("knee_far", 38, (31, 24, 28, 255), (72, 55, 56, 255))],
    "near_thigh": [("knee_near", 38, (31, 24, 28, 255), (72, 55, 56, 255))],
    "far_shin": [("ankle_far", 25, (77, 37, 27, 255), (231, 139, 82, 255))],
    "near_shin": [("ankle_near", 25, (77, 37, 27, 255), (231, 139, 82, 255))],
}

BODY_UNDERPAINT_POLYGONS = [
    [(468, 315), (730, 315), (738, 718), (472, 718)],
    [(442, 674), (728, 674), (736, 824), (438, 824)],
]

SEAM_LINES = {
    "near_upper_arm": [[(650, 385), (678, 500), (747, 648)]],
    "far_upper_arm": [[(594, 386), (536, 504), (470, 610)]],
    "near_thigh": [[(604, 728), (579, 810), (553, 914)]],
    "far_thigh": [[(627, 728), (655, 810), (690, 923)]],
}


def is_chroma_green(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, _ = pixel
    return green >= 75 and green > red * 1.28 and green > blue * 1.28 and green - max(red, blue) >= 38


def foreground_mask(image: Image.Image) -> Image.Image:
    mask = Image.new("L", image.size)
    pixels = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
    mask.putdata([0 if is_chroma_green(pixel) else 255 for pixel in pixels])
    return mask


def polygon_mask(size: tuple[int, int], points: list[tuple[int, int]]) -> Image.Image:
    mask = Image.new("L", size)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return mask


def apply_alpha(source: Image.Image, mask: Image.Image) -> Image.Image:
    layer = source.copy()
    layer.putalpha(mask)
    return layer


def octagon(center: list[int], radius: int) -> list[tuple[int, int]]:
    x, y = center
    inset = round(radius * 0.42)
    return [
        (x - inset, y - radius),
        (x + inset, y - radius),
        (x + radius, y - inset),
        (x + radius, y + inset),
        (x + inset, y + radius),
        (x - inset, y + radius),
        (x - radius, y + inset),
        (x - radius, y - inset),
    ]


def rig_ready_layer(source: Image.Image, mask: Image.Image, part: str, foreground: Image.Image) -> Image.Image:
    underpaint = Image.new("RGBA", source.size)
    draw = ImageDraw.Draw(underpaint)
    for joint, radius, outline, fill in CAPS.get(part, []):
        draw.polygon(octagon(JOINTS[joint], radius), fill=outline)
        draw.polygon(octagon(JOINTS[joint], max(1, radius - 7)), fill=fill)
    if part == "body":
        overlap = Image.new("L", source.size)
        overlap_draw = ImageDraw.Draw(overlap)
        for polygon in BODY_UNDERPAINT_POLYGONS:
            overlap_draw.polygon(polygon, fill=255)
        underpaint.alpha_composite(apply_alpha(source, ImageChops.multiply(overlap, foreground)))
    underpaint.alpha_composite(apply_alpha(source, mask))
    if SEAM_LINES.get(part):
        seam_overlay = Image.new("RGBA", source.size)
        seam_draw = ImageDraw.Draw(seam_overlay)
        for points in SEAM_LINES[part]:
            seam_draw.line(points, fill=(15, 14, 22, 255), width=7, joint="curve")
        expanded_part = mask.filter(ImageFilter.MaxFilter(15))
        seam_overlay.putalpha(ImageChops.multiply(seam_overlay.getchannel("A"), expanded_part))
        underpaint.alpha_composite(seam_overlay)
    return underpaint


def build_pack(source_path: Path, output_dir: Path) -> dict:
    source = Image.open(source_path).convert("RGBA")
    if source.size != (1254, 1254):
        raise ValueError(f"Expected 1254x1254 source, got {source.size[0]}x{source.size[1]}")
    output_dir.mkdir(parents=True, exist_ok=True)

    foreground = foreground_mask(source)
    remaining = foreground.copy()
    masks: dict[str, Image.Image] = {}
    for part in PART_ORDER:
        candidate = ImageChops.multiply(polygon_mask(source.size, PART_POLYGONS[part]), remaining)
        masks[part] = candidate
        remaining = ImageChops.subtract(remaining, candidate)
    masks["body"] = remaining

    layer_order = ["far_upper_arm", "far_lower_arm", "far_thigh", "far_shin", "far_foot", "body", "near_thigh", "near_shin", "near_foot", "near_upper_arm", "near_lower_arm"]
    files: dict[str, str] = {}
    raw_dir = output_dir / "source-locked"
    raw_dir.mkdir(exist_ok=True)
    for part in layer_order:
        filename = f"{part}.png"
        apply_alpha(source, masks[part]).save(raw_dir / filename, optimize=True)
        rig_ready_layer(source, masks[part], part, foreground).save(output_dir / filename, optimize=True)
        files[part] = filename

    keyed_source = apply_alpha(source, foreground)
    source_locked_composite = Image.new("RGBA", source.size)
    composite = Image.new("RGBA", source.size)
    for part in layer_order:
        source_locked_composite.alpha_composite(apply_alpha(source, masks[part]))
        composite.alpha_composite(rig_ready_layer(source, masks[part], part, foreground))
    source_locked_composite.save(output_dir / "neutral-composite-source-locked.png", optimize=True)
    composite.save(output_dir / "neutral-composite.png", optimize=True)

    difference = ImageChops.difference(keyed_source, source_locked_composite)
    if difference.getbbox() is not None:
        raise RuntimeError("Layer composite does not reconstruct the keyed source")
    added_alpha = ImageChops.subtract(composite.getchannel("A"), keyed_source.getchannel("A"))
    added_values = added_alpha.get_flattened_data() if hasattr(added_alpha, "get_flattened_data") else added_alpha.getdata()
    added_underpaint = sum(1 for value in added_values if value)

    thumb_size = (256, 256)
    overview = Image.new("RGBA", (thumb_size[0] * 4, thumb_size[1] * 3), (20, 25, 35, 255))
    resampling = getattr(Image.Resampling, "NEAREST", Image.NEAREST)
    for index, part in enumerate(files):
        thumb = rig_ready_layer(source, masks[part], part, foreground).resize(thumb_size, resampling)
        overview.alpha_composite(thumb, ((index % 4) * thumb_size[0], (index // 4) * thumb_size[1]))
    overview.save(output_dir / "parts-overview.png", optimize=True)

    manifest = {
        "format": "asset-studio.layered-rig-pack/v1",
        "source": str(source_path),
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "canvas": {"width": source.width, "height": source.height},
        "background_rule": "green>=75 and green>red*1.28 and green>blue*1.28 and green-max(red,blue)>=38",
        "parts": files,
        "joints": JOINTS,
        "validation": {"source_locked_reconstruction_exact": True, "rig_ready_underpaint_pixels": added_underpaint, "part_count": len(files)},
        "identity_ledger": {
            "preserved": ["all visible source pixels", "palette", "pixel clusters", "full-canvas alignment"],
            "changed": ["green background to transparency", "visible pixels assigned to 11 non-overlapping layers", "flat palette joint caps under moving seams"],
            "not_invented": ["occluded limb textures", "new clothing detail", "new anatomy"],
        },
    }
    (output_dir / "rig-pack.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest = build_pack(args.source.resolve(), args.output.resolve())
    print(json.dumps({"output": str(args.output.resolve()), "parts": len(manifest["parts"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
