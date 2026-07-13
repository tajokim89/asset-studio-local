"""Deterministic normalization and horizontal assembly for actor frames."""

from __future__ import annotations

import io
import math
from collections.abc import Sequence
from fractions import Fraction
from numbers import Real
from typing import Any

from PIL import Image, UnidentifiedImageError


class ActorAssemblyError(ValueError):
    """Raised when actor frames cannot be assembled without hiding a defect."""


def _png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _zero_transparent_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    cleaned = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    source_pixels = (
        rgba.get_flattened_data()
        if hasattr(rgba, "get_flattened_data")
        else rgba.getdata()
    )
    cleaned.putdata(
        [
            (red, green, blue, alpha) if alpha else (0, 0, 0, 0)
            for red, green, blue, alpha in source_pixels
        ]
    )
    return cleaned


def _decode_frame(raw: object, index: int) -> tuple[Image.Image, tuple[int, int, int, int]]:
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise TypeError(f"frame {index} must be PNG bytes")
    try:
        with Image.open(io.BytesIO(bytes(raw))) as source:
            if source.format != "PNG":
                raise ActorAssemblyError(f"frame {index} is not a valid PNG")
            source.load()
            image = _zero_transparent_rgb(source)
    except ActorAssemblyError:
        raise
    except (OSError, UnidentifiedImageError, ValueError) as error:
        raise ActorAssemblyError(f"frame {index} is not a valid PNG") from error

    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ActorAssemblyError(f"frame {index} is empty")
    left, top, right, bottom = bbox
    if left == 0 or top == 0 or right == image.width or bottom == image.height:
        raise ActorAssemblyError(f"frame {index} alpha touches source edge")
    return image, bbox


def _validate_options(
    cell_size: object,
    padding: object,
    min_scale: object,
) -> tuple[int, int, Fraction]:
    if type(cell_size) is not int or cell_size < 1:
        raise ActorAssemblyError("cell_size must be a positive integer")
    if type(padding) is not int or padding < 1 or padding * 2 >= cell_size:
        raise ActorAssemblyError("padding must leave a positive cell interior")
    if (
        isinstance(min_scale, bool)
        or not isinstance(min_scale, Real)
        or not math.isfinite(float(min_scale))
        or not 0 < float(min_scale) <= 1
    ):
        raise ActorAssemblyError("min_scale must be a number in 0..1")
    return cell_size, padding, Fraction(str(min_scale))


def _scaled_dimension(value: int, scale: Fraction) -> int:
    numerator = value * scale.numerator
    return max(1, (numerator * 2 + scale.denominator) // (scale.denominator * 2))


def _opaque_count(values: object) -> int:
    return sum(1 for value in values if value)


def _detect_head_and_ground_anchor(
    image: Image.Image,
) -> tuple[int, int, int]:
    """Find a stable central head top/x and ground row while ignoring side equipment."""
    alpha = image.getchannel("A")
    width, height = image.size
    center_left = round(width * 0.30)
    center_right = round(width * 0.70)
    window_width = center_right - center_left
    threshold = max(1, round(window_width * 0.02))
    run_length = min(5, max(2, height // 64))
    row_counts = [
        _opaque_count(alpha.crop((center_left, y, center_right, y + 1)).getdata())
        for y in range(height)
    ]

    head_y = next(
        (
            y
            for y in range(0, height - run_length + 1)
            if all(count >= threshold for count in row_counts[y : y + run_length])
        ),
        None,
    )
    ground_start = next(
        (
            y
            for y in range(height - run_length, -1, -1)
            if all(count >= threshold for count in row_counts[y : y + run_length])
        ),
        None,
    )
    if head_y is None or ground_start is None:
        raise ActorAssemblyError("could not detect a dense central actor anchor")
    ground_y = ground_start + run_length - 1
    if ground_y <= head_y:
        raise ActorAssemblyError("detected actor head/ground anchors are invalid")

    head_band_bottom = min(
        height,
        head_y + max(run_length, round((ground_y - head_y) * 0.20)),
    )
    column_counts = []
    for x in range(center_left, center_right):
        column_counts.append(
            _opaque_count(alpha.crop((x, head_y, x + 1, head_band_bottom)).getdata())
        )
    total = sum(column_counts)
    if total == 0:
        raise ActorAssemblyError("could not detect actor head center")
    midpoint = (total + 1) // 2
    cumulative = 0
    head_x = center_left
    for offset, count in enumerate(column_counts):
        cumulative += count
        if cumulative >= midpoint:
            head_x = center_left + offset
            break
    return head_x, head_y, ground_y


def _align_head_and_ground(
    image: Image.Image,
    source_anchor: tuple[int, int, int],
    target_anchor: tuple[int, int, int],
) -> tuple[Image.Image, dict[str, Any]]:
    source_head_x, source_head_y, source_ground_y = source_anchor
    target_head_x, target_head_y, target_ground_y = target_anchor
    source_height = source_ground_y - source_head_y
    target_height = target_ground_y - target_head_y
    scale = Fraction(target_height, source_height)
    resized_size = (
        _scaled_dimension(image.width, scale),
        _scaled_dimension(image.height, scale),
    )
    resized = _zero_transparent_rgb(
        image.resize(resized_size, Image.Resampling.NEAREST)
    )
    scaled_head_x = _scaled_dimension(source_head_x, scale)
    scaled_head_y = _scaled_dimension(source_head_y, scale)
    offset = (
        target_head_x - scaled_head_x,
        target_head_y - scaled_head_y,
    )
    resized_bbox = resized.getchannel("A").getbbox()
    if resized_bbox is None:
        raise ActorAssemblyError("actor became empty during head/root normalization")
    placed_bbox = (
        resized_bbox[0] + offset[0],
        resized_bbox[1] + offset[1],
        resized_bbox[2] + offset[0],
        resized_bbox[3] + offset[1],
    )
    if (
        placed_bbox[0] <= 0
        or placed_bbox[1] <= 0
        or placed_bbox[2] >= image.width
        or placed_bbox[3] >= image.height
    ):
        raise ActorAssemblyError("head/root normalization would clip the actor")

    aligned = Image.new("RGBA", image.size, (0, 0, 0, 0))
    aligned.alpha_composite(resized, offset)
    aligned = _zero_transparent_rgb(aligned)
    detected = _detect_head_and_ground_anchor(aligned)
    return aligned, {
        "source_head_anchor": [source_head_x, source_head_y],
        "source_ground_y": source_ground_y,
        "scale": {
            "numerator": scale.numerator,
            "denominator": scale.denominator,
            "value": float(scale),
        },
        "resized_source_size": list(resized_size),
        "offset": list(offset),
        "aligned_head_anchor": [detected[0], detected[1]],
        "aligned_ground_y": detected[2],
    }


def assemble_actor_frames(
    frame_pngs: Sequence[bytes],
    *,
    cell_size: int = 512,
    padding: int = 16,
    min_scale: float = 0.25,
) -> dict[str, Any]:
    """Normalize transparent PNG frames and assemble one horizontal sheet.

    A single scale derived from the largest alpha bounds is applied to every
    frame. Each normalized frame uses the same bottom-center root and padding.
    """

    cell_size, padding, minimum = _validate_options(cell_size, padding, min_scale)
    if isinstance(frame_pngs, (bytes, bytearray, memoryview)) or not isinstance(
        frame_pngs, Sequence
    ):
        raise TypeError("frame_pngs must be a sequence of PNG byte strings")
    if not frame_pngs:
        raise ActorAssemblyError("at least one actor frame is required")

    decoded = []
    for index, raw in enumerate(frame_pngs):
        image, bbox = _decode_frame(raw, index)
        decoded.append(
            {
                "image": image,
                "source_size": image.size,
                "bbox": bbox,
                "crop": image.crop(bbox),
            }
        )

    drawable = cell_size - padding * 2
    max_width = max(item["crop"].width for item in decoded)
    max_height = max(item["crop"].height for item in decoded)
    common_scale = min(
        Fraction(drawable, max_width),
        Fraction(drawable, max_height),
    )
    if common_scale < minimum:
        raise ActorAssemblyError(
            "common scale is below the configured minimum "
            f"({float(common_scale):.6g} < {float(minimum):.6g})"
        )

    root_bottom = cell_size - padding
    root_pixel = [cell_size // 2, root_bottom - 1]
    normalized_images = []
    frame_geometry = []

    for index, item in enumerate(decoded):
        crop = item["crop"]
        resized_size = (
            _scaled_dimension(crop.width, common_scale),
            _scaled_dimension(crop.height, common_scale),
        )
        resized = crop.resize(resized_size, Image.Resampling.NEAREST)
        resized = _zero_transparent_rgb(resized)
        resized_bbox = resized.getchannel("A").getbbox()
        if resized_bbox is None:
            raise ActorAssemblyError(f"frame {index} became empty while resizing")
        sprite = resized.crop(resized_bbox)
        sprite = _zero_transparent_rgb(sprite)

        left = (cell_size - sprite.width) // 2
        top = root_bottom - sprite.height
        if (
            left < padding
            or top < padding
            or left + sprite.width > cell_size - padding
            or top + sprite.height > root_bottom
        ):
            raise ActorAssemblyError(f"frame {index} does not fit the padded cell")

        normalized = Image.new("RGBA", (cell_size, cell_size), (0, 0, 0, 0))
        normalized.alpha_composite(sprite, (left, top))
        normalized = _zero_transparent_rgb(normalized)
        normalized_bbox = normalized.getchannel("A").getbbox()
        if normalized_bbox is None:
            raise ActorAssemblyError(f"frame {index} became empty after placement")
        if (
            normalized_bbox[0] == 0
            or normalized_bbox[1] == 0
            or normalized_bbox[2] == cell_size
            or normalized_bbox[3] == cell_size
        ):
            raise ActorAssemblyError(f"frame {index} alpha touches normalized edge")

        normalized_images.append(normalized)
        source_bbox = item["bbox"]
        frame_geometry.append(
            {
                "index": index,
                "source_size": list(item["source_size"]),
                "source_alpha_bbox": list(source_bbox),
                "source_bbox_size": [
                    source_bbox[2] - source_bbox[0],
                    source_bbox[3] - source_bbox[1],
                ],
                "resized_size": list(resized_size),
                "placed_size": [sprite.width, sprite.height],
                "offset": [left, top],
                "normalized_alpha_bbox": list(normalized_bbox),
                "root_pixel": list(root_pixel),
                "root_proxy": [
                    (normalized_bbox[0] + normalized_bbox[2]) / 2,
                    normalized_bbox[3] - 1,
                ],
                "margins": [
                    normalized_bbox[0],
                    normalized_bbox[1],
                    cell_size - normalized_bbox[2],
                    cell_size - normalized_bbox[3],
                ],
                "touches_edge": False,
            }
        )

    sheet = Image.new(
        "RGBA",
        (cell_size * len(normalized_images), cell_size),
        (0, 0, 0, 0),
    )
    for index, frame in enumerate(normalized_images):
        sheet.alpha_composite(frame, (index * cell_size, 0))
    sheet = _zero_transparent_rgb(sheet)

    scale_metadata = {
        "numerator": common_scale.numerator,
        "denominator": common_scale.denominator,
        "value": float(common_scale),
    }
    geometry = {
        "schema_version": "asset-studio.actor-assembly/v1",
        "layout": "horizontal",
        "frame_count": len(normalized_images),
        "cell_size": [cell_size, cell_size],
        "sheet_size": [sheet.width, sheet.height],
        "padding": padding,
        "root_preset": "bottom-center",
        "root_pixel": root_pixel,
        "resampling": "nearest-neighbor",
        "common_scale": scale_metadata,
        "frames": frame_geometry,
    }
    return {
        "sheet_png": _png_bytes(sheet),
        "normalized_frame_pngs": tuple(_png_bytes(frame) for frame in normalized_images),
        "geometry": geometry,
    }


def assemble_actor_canvas_frames(
    frame_pngs: Sequence[bytes],
    *,
    cell_size: int = 512,
    padding: int = 16,
    min_scale: float = 0.25,
) -> dict[str, Any]:
    """Apply one transform to complete source canvases, preserving authored drift."""
    cell_size, padding, minimum = _validate_options(cell_size, padding, min_scale)
    if isinstance(frame_pngs, (bytes, bytearray, memoryview)) or not isinstance(
        frame_pngs, Sequence
    ):
        raise TypeError("frame_pngs must be a sequence of PNG byte strings")
    if not frame_pngs:
        raise ActorAssemblyError("at least one actor frame is required")

    decoded = [_decode_frame(raw, index) for index, raw in enumerate(frame_pngs)]
    source_size = decoded[0][0].size
    if any(image.size != source_size for image, _bbox in decoded[1:]):
        raise ActorAssemblyError("source canvas size mismatch")

    drawable = cell_size - padding * 2
    common_scale = min(
        Fraction(drawable, source_size[0]),
        Fraction(drawable, source_size[1]),
    )
    if common_scale < minimum:
        raise ActorAssemblyError(
            "common scale is below the configured minimum "
            f"({float(common_scale):.6g} < {float(minimum):.6g})"
        )
    resized_source_size = (
        _scaled_dimension(source_size[0], common_scale),
        _scaled_dimension(source_size[1], common_scale),
    )
    offset = (
        (cell_size - resized_source_size[0]) // 2,
        cell_size - padding - resized_source_size[1],
    )

    normalized_images = []
    frame_geometry = []
    for index, (image, source_bbox) in enumerate(decoded):
        resized = _zero_transparent_rgb(
            image.resize(resized_source_size, Image.Resampling.NEAREST)
        )
        normalized = Image.new("RGBA", (cell_size, cell_size), (0, 0, 0, 0))
        normalized.alpha_composite(resized, offset)
        normalized = _zero_transparent_rgb(normalized)
        bbox = normalized.getchannel("A").getbbox()
        if bbox is None:
            raise ActorAssemblyError(f"frame {index} became empty after placement")
        normalized_images.append(normalized)
        frame_geometry.append({
            "index": index,
            "source_alpha_bbox": list(source_bbox),
            "normalized_alpha_bbox": list(bbox),
            "root_proxy": [(bbox[0] + bbox[2]) / 2, bbox[3] - 1],
            "touches_edge": False,
        })

    sheet = Image.new(
        "RGBA", (cell_size * len(normalized_images), cell_size), (0, 0, 0, 0)
    )
    for index, frame in enumerate(normalized_images):
        sheet.alpha_composite(frame, (index * cell_size, 0))
    sheet = _zero_transparent_rgb(sheet)
    scale = {
        "numerator": common_scale.numerator,
        "denominator": common_scale.denominator,
        "value": float(common_scale),
    }
    geometry = {
        "schema_version": "asset-studio.actor-assembly/v1",
        "layout": "horizontal",
        "alignment": "preserve-source-canvas",
        "drift_preserved": True,
        "frame_count": len(normalized_images),
        "cell_size": [cell_size, cell_size],
        "sheet_size": [sheet.width, sheet.height],
        "padding": padding,
        "source_size": list(source_size),
        "common_transform": {
            "scale": scale,
            "resized_source_size": list(resized_source_size),
            "offset": list(offset),
            "resampling": "nearest-neighbor",
        },
        "frames": frame_geometry,
    }
    return {
        "sheet_png": _png_bytes(sheet),
        "normalized_frame_pngs": tuple(_png_bytes(frame) for frame in normalized_images),
        "geometry": geometry,
    }


def assemble_actor_head_locked_frames(
    frame_pngs: Sequence[bytes],
    *,
    cell_size: int = 512,
    padding: int = 16,
    min_scale: float = 0.25,
) -> dict[str, Any]:
    """Normalize a walk sequence to frame one's head center/top and ground row."""
    if isinstance(frame_pngs, (bytes, bytearray, memoryview)) or not isinstance(
        frame_pngs, Sequence
    ):
        raise TypeError("frame_pngs must be a sequence of PNG byte strings")
    if not frame_pngs:
        raise ActorAssemblyError("at least one actor frame is required")

    decoded = [_decode_frame(raw, index) for index, raw in enumerate(frame_pngs)]
    source_size = decoded[0][0].size
    if any(image.size != source_size for image, _bbox in decoded[1:]):
        raise ActorAssemblyError("source canvas size mismatch")

    source_anchors = [
        _detect_head_and_ground_anchor(image) for image, _bbox in decoded
    ]
    target_anchor = source_anchors[0]
    aligned_pngs = []
    normalization = []
    for (image, source_bbox), source_anchor in zip(decoded, source_anchors):
        aligned, metadata = _align_head_and_ground(
            image,
            source_anchor,
            target_anchor,
        )
        metadata["original_source_alpha_bbox"] = list(source_bbox)
        aligned_pngs.append(_png_bytes(aligned))
        normalization.append(metadata)

    result = assemble_actor_canvas_frames(
        tuple(aligned_pngs),
        cell_size=cell_size,
        padding=padding,
        min_scale=min_scale,
    )
    normalized_anchors = []
    for index, raw in enumerate(result["normalized_frame_pngs"]):
        image, _bbox = _decode_frame(raw, index)
        normalized_anchors.append(_detect_head_and_ground_anchor(image))
    target_normalized = normalized_anchors[0]
    if any(
        abs(anchor[0] - target_normalized[0]) > 2
        or abs(anchor[1] - target_normalized[1]) > 2
        or abs(anchor[2] - target_normalized[2]) > 2
        for anchor in normalized_anchors[1:]
    ):
        raise ActorAssemblyError("head/root normalization did not converge")

    geometry = result["geometry"]
    geometry.update({
        "alignment": "head-and-ground-lock",
        "drift_preserved": False,
        "head_lock": {
            "detector": "dense-central-alpha-v1",
            "target_source_head_anchor": [target_anchor[0], target_anchor[1]],
            "target_source_ground_y": target_anchor[2],
            "target_normalized_head_anchor": [
                target_normalized[0],
                target_normalized[1],
            ],
            "target_normalized_ground_y": target_normalized[2],
        },
    })
    for frame, metadata, normalized_anchor in zip(
        geometry["frames"], normalization, normalized_anchors
    ):
        frame["head_root_normalization"] = metadata
        frame["normalized_head_anchor"] = [
            normalized_anchor[0],
            normalized_anchor[1],
        ]
        frame["normalized_ground_y"] = normalized_anchor[2]
    return result


def assemble_canonical_walk_frames(
    neutral_png: bytes,
    left_png: bytes,
    right_png: bytes,
) -> dict[str, Any]:
    """Build N/L/N/R on the uploaded neutral frame's exact RGBA canvas."""
    try:
        with Image.open(io.BytesIO(bytes(neutral_png))) as source:
            if source.format != "PNG":
                raise ActorAssemblyError("walk neutral frame is not a valid PNG")
            source.load()
            neutral = source.convert("RGBA")
    except ActorAssemblyError:
        raise
    except (OSError, UnidentifiedImageError, ValueError, TypeError) as error:
        raise ActorAssemblyError("walk neutral frame is not a valid PNG") from error

    neutral_bbox = neutral.getchannel("A").getbbox()
    if neutral_bbox is None:
        raise ActorAssemblyError("walk neutral frame is empty")
    width, height = neutral.size
    if neutral_bbox[0] == 0 or neutral_bbox[1] == 0 or neutral_bbox[2] == width or neutral_bbox[3] == height:
        raise ActorAssemblyError("walk neutral frame alpha touches source edge")

    generated_frames = []
    generated_geometry = []
    for output_index, raw in ((1, left_png), (3, right_png)):
        generated, source_bbox = _decode_frame(raw, output_index)
        crop = generated.crop(source_bbox)
        drawable_width = width - 2
        drawable_height = neutral_bbox[3] - neutral_bbox[1]
        scale = min(
            Fraction(1, 1),
            Fraction(drawable_width, crop.width),
            Fraction(drawable_height, crop.height),
        )
        resized_size = (_scaled_dimension(crop.width, scale), _scaled_dimension(crop.height, scale))
        if resized_size[0] > drawable_width or resized_size[1] > drawable_height:
            raise ActorAssemblyError(f"generated walk frame {output_index + 1} cannot fit neutral canvas")
        resized = _zero_transparent_rgb(crop.resize(resized_size, Image.Resampling.NEAREST))
        left = (width - resized.width) // 2
        bottom = min(height - 1, neutral_bbox[3])
        top = bottom - resized.height
        if left < 1 or top < 1 or left + resized.width >= width or top + resized.height >= height:
            raise ActorAssemblyError(f"generated walk frame {output_index + 1} cannot fit neutral canvas")
        normalized = Image.new("RGBA", neutral.size, (0, 0, 0, 0))
        normalized.alpha_composite(resized, (left, top))
        generated_frames.append(_zero_transparent_rgb(normalized))
        generated_geometry.append({
            "index": output_index,
            "source_size": list(generated.size),
            "source_alpha_bbox": list(source_bbox),
            "resized_size": list(resized_size),
            "offset": [left, top],
            "scale": {"numerator": scale.numerator, "denominator": scale.denominator, "value": float(scale)},
        })

    frames = (neutral, generated_frames[0], neutral.copy(), generated_frames[1])
    sheet = Image.new("RGBA", (width * 4, height), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        sheet.paste(frame, (index * width, 0))
    return {
        "sheet_png": _png_bytes(sheet),
        "normalized_frame_pngs": tuple(_png_bytes(frame) for frame in frames),
        "geometry": {
            "schema_version": "asset-studio.actor-walk-assembly/v1",
            "layout": "horizontal",
            "alignment": "uploaded-neutral-canvas",
            "frame_count": 4,
            "cell_size": [width, height],
            "sheet_size": [width * 4, height],
            "source_size": [width, height],
            "resampling": "nearest-neighbor-generated-frames-only",
            "neutral_preservation": "exact-rgba-pixels-and-dimensions",
            "generated_frames": generated_geometry,
        },
    }


__all__ = [
    "ActorAssemblyError",
    "assemble_actor_canvas_frames",
    "assemble_actor_frames",
    "assemble_actor_head_locked_frames",
    "assemble_canonical_walk_frames",
]
