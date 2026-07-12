from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageChops


REQUIRED_VISUAL_CHECKS = (
    "hand_integrity",
    "foot_integrity",
    "joint_coherence",
    "limb_scale_consistency",
    "equipment_contact",
    "temporal_limb_continuity",
)

DEFAULT_THRESHOLDS = {
    "max_root_drift_pixels": 1.0,
    "max_baseline_drift_pixels": 1.0,
    "max_bbox_area_ratio_delta": 0.15,
    "min_adjacent_alpha_change_ratio": 0.01,
    "max_adjacent_alpha_change_ratio": 0.70,
    "max_loop_alpha_change_ratio": 0.25,
}


class ActorQAError(ValueError):
    """Raised when an actor sheet or its manual annotations are invalid."""


def split_horizontal_frames(image: Image.Image, frame_count: int) -> list[Image.Image]:
    """Split an image into exact, equal-width cells without trimming or recentering."""

    if type(frame_count) is not int or frame_count < 1:
        raise ActorQAError("frame_count must be a positive integer")
    if image.width % frame_count:
        raise ActorQAError(
            f"sheet width {image.width} is not divisible by frame_count {frame_count}"
        )

    rgba = image.convert("RGBA")
    frame_width = rgba.width // frame_count
    return [
        rgba.crop((index * frame_width, 0, (index + 1) * frame_width, rgba.height))
        for index in range(frame_count)
    ]


def _binary_alpha(frame: Image.Image) -> Image.Image:
    return frame.getchannel("A").point(lambda value: 255 if value else 0)


def _opaque_pixels(binary_alpha: Image.Image) -> int:
    return binary_alpha.histogram()[255]


def _alpha_change_ratio(left: Image.Image, right: Image.Image) -> float:
    left_alpha = _binary_alpha(left)
    right_alpha = _binary_alpha(right)
    union_pixels = _opaque_pixels(ImageChops.lighter(left_alpha, right_alpha))
    if union_pixels == 0:
        return 0.0
    changed_pixels = _opaque_pixels(ImageChops.difference(left_alpha, right_alpha))
    return changed_pixels / union_pixels


def measure_actor_sheet(
    image_path: str | Path, *, frame_count: int = 6
) -> dict[str, Any]:
    """Measure geometry and alpha-shape continuity; this does not recognize anatomy."""

    path = Path(image_path)
    with Image.open(path) as source:
        frames = split_horizontal_frames(source, frame_count)

    frame_metrics = []
    for index, frame in enumerate(frames):
        alpha = frame.getchannel("A")
        bbox = alpha.getbbox()
        opaque_pixels = _opaque_pixels(_binary_alpha(frame))
        if bbox is None:
            frame_metrics.append(
                {
                    "index": index,
                    "nonempty": False,
                    "opaque_pixels": 0,
                    "bbox": None,
                    "bbox_center": None,
                    "root_proxy": None,
                    "baseline_y": None,
                    "bbox_width": 0,
                    "bbox_height": 0,
                    "bbox_area": 0,
                }
            )
            continue

        left, top, right, bottom = bbox
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        frame_metrics.append(
            {
                "index": index,
                "nonempty": True,
                "opaque_pixels": opaque_pixels,
                "bbox": [left, top, right, bottom],
                "bbox_center": [center_x, center_y],
                # This is only a bottom-center geometry proxy, not a detected foot joint.
                "root_proxy": [center_x, bottom - 1],
                "baseline_y": bottom - 1,
                "bbox_width": right - left,
                "bbox_height": bottom - top,
                "bbox_area": (right - left) * (bottom - top),
            }
        )

    nonempty = [frame for frame in frame_metrics if frame["nonempty"]]
    if nonempty:
        root_origin = nonempty[0]["root_proxy"]
        root_drift = max(
            math.hypot(
                frame["root_proxy"][0] - root_origin[0],
                frame["root_proxy"][1] - root_origin[1],
            )
            for frame in nonempty
        )
        baselines = [frame["baseline_y"] for frame in nonempty]
        areas = [frame["bbox_area"] for frame in nonempty]
        area_delta = (max(areas) / min(areas)) - 1 if min(areas) else math.inf
    else:
        root_drift = math.inf
        baselines = []
        area_delta = math.inf

    adjacent_changes = [
        _alpha_change_ratio(frames[index], frames[index + 1])
        for index in range(len(frames) - 1)
    ]
    loop_change = _alpha_change_ratio(frames[-1], frames[0]) if len(frames) > 1 else 0.0

    return {
        "sheet": {
            "width": sum(frame.width for frame in frames),
            "height": frames[0].height,
            "frame_count": len(frames),
            "frame_width": frames[0].width,
        },
        "frames": frame_metrics,
        "summary": {
            "nonempty_frames": len(nonempty),
            "root_proxy_drift_pixels": root_drift,
            "baseline_drift_pixels": max(baselines) - min(baselines) if baselines else math.inf,
            "bbox_area_ratio_delta": area_delta,
            "adjacent_alpha_change_ratios": adjacent_changes,
            "loop_alpha_change_ratio": loop_change,
        },
    }


def evaluate_visual_annotations(
    annotations: Mapping[str, Any], *, minimum_score: int = 4
) -> dict[str, Any]:
    """Fail closed on missing, low-scored, or explicitly defective manual review."""

    checks = []
    reasons = []
    for check_id in REQUIRED_VISUAL_CHECKS:
        annotation = annotations.get(check_id)
        if not isinstance(annotation, Mapping):
            checks.append({"id": check_id, "pass": False, "score": None, "defects": []})
            reasons.append(
                {
                    "code": "missing-visual-annotation",
                    "check": check_id,
                    "message": f"required visual annotation {check_id!r} is missing",
                }
            )
            continue

        score = annotation.get("score")
        defects = annotation.get("defects", [])
        if type(score) not in (int, float) or isinstance(score, bool) or not 1 <= score <= 5:
            raise ActorQAError(f"{check_id}.score must be a number from 1 to 5")
        if not isinstance(defects, list) or not all(
            isinstance(defect, str) and defect.strip() for defect in defects
        ):
            raise ActorQAError(f"{check_id}.defects must be a list of non-empty strings")

        passed = score >= minimum_score and not defects
        checks.append(
            {"id": check_id, "pass": passed, "score": score, "defects": list(defects)}
        )
        if score < minimum_score:
            reasons.append(
                {
                    "code": "visual-score-below-minimum",
                    "check": check_id,
                    "message": f"{check_id} scored {score}; minimum is {minimum_score}",
                }
            )
        for defect in defects:
            reasons.append(
                {
                    "code": "explicit-visual-defect",
                    "check": check_id,
                    "message": defect,
                }
            )

    return {"pass": not reasons, "checks": checks, "reasons": reasons}


def evaluate_actor_qa(
    image_path: str | Path,
    visual_annotations: Mapping[str, Any],
    *,
    frame_count: int = 6,
    thresholds: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Combine deterministic geometry proxies with required manual anatomy review."""

    limits = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        unknown = set(thresholds) - set(limits)
        if unknown:
            raise ActorQAError(f"unknown thresholds: {sorted(unknown)}")
        limits.update(thresholds)

    metrics = measure_actor_sheet(image_path, frame_count=frame_count)
    summary = metrics["summary"]
    local_checks = [
        {
            "id": "nonempty-frames",
            "pass": summary["nonempty_frames"] == frame_count,
            "value": summary["nonempty_frames"],
            "limit": frame_count,
        },
        {
            "id": "root-proxy-drift",
            "pass": summary["root_proxy_drift_pixels"] <= limits["max_root_drift_pixels"],
            "value": summary["root_proxy_drift_pixels"],
            "limit": limits["max_root_drift_pixels"],
        },
        {
            "id": "contact-baseline-drift",
            "pass": summary["baseline_drift_pixels"] <= limits["max_baseline_drift_pixels"],
            "value": summary["baseline_drift_pixels"],
            "limit": limits["max_baseline_drift_pixels"],
        },
        {
            "id": "bbox-scale-drift",
            "pass": summary["bbox_area_ratio_delta"] <= limits["max_bbox_area_ratio_delta"],
            "value": summary["bbox_area_ratio_delta"],
            "limit": limits["max_bbox_area_ratio_delta"],
        },
        {
            "id": "adjacent-alpha-change",
            "pass": all(
                limits["min_adjacent_alpha_change_ratio"] <= value
                <= limits["max_adjacent_alpha_change_ratio"]
                for value in summary["adjacent_alpha_change_ratios"]
            ),
            "value": summary["adjacent_alpha_change_ratios"],
            "limit": [
                limits["min_adjacent_alpha_change_ratio"],
                limits["max_adjacent_alpha_change_ratio"],
            ],
        },
        {
            "id": "loop-alpha-change",
            "pass": summary["loop_alpha_change_ratio"] <= limits["max_loop_alpha_change_ratio"],
            "value": summary["loop_alpha_change_ratio"],
            "limit": limits["max_loop_alpha_change_ratio"],
        },
    ]
    local_reasons = [
        {
            "code": "local-check-failed",
            "check": check["id"],
            "message": f"{check['id']} measured {check['value']!r}; limit {check['limit']!r}",
        }
        for check in local_checks
        if not check["pass"]
    ]
    local_qa = {
        "pass": not local_reasons,
        "checks": local_checks,
        "reasons": local_reasons,
    }
    visual_qa = evaluate_visual_annotations(visual_annotations)

    return {
        "pass": local_qa["pass"] and visual_qa["pass"],
        "local_qa": local_qa,
        "visual_qa": visual_qa,
        "metrics": metrics,
        "reasons": local_qa["reasons"] + visual_qa["reasons"],
    }
