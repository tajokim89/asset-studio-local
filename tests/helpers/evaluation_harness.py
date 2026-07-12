from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image

from asset_studio.evaluation import (
    aggregate_evaluation,
    append_evaluation_run,
    validate_evaluation_run,
    validate_golden_job,
    validate_quality_rubric,
)


def _aspect(width: int, height: int) -> str:
    if width > height:
        return "landscape"
    if height > width:
        return "portrait"
    return "square"


def _object_contract(width: int, height: int) -> dict:
    return {
        "usage": "world",
        "identity": {"subtype": "item", "form": "potion"},
        "view": "three-quarter",
        "scale": {"basis": "pixel"},
        "source": {
            "canvas": {"width": width, "height": height},
            "padding": {"top": 1, "right": 1, "bottom": 1, "left": 1},
        },
        "placement": {
            "pivot": {"x": 0.5, "y": 1},
            "ground_point": {"x": 0.5, "y": 1},
            "y_sort_point": {"x": 0.5, "y": 1},
            "snap_points": [],
        },
        "shadow": {"mode": "none", "baked": False},
        "states": [],
        "variants": [],
        "collision": {},
        "interaction": {},
        "custom_properties": {},
    }


def _ui_contract(width: int, height: int, states: list[str]) -> dict:
    margin = max(1, min(width, height) // 8)
    padding = max(1, margin // 2)
    return {
        "purpose": "reusable text-free button",
        "information_structure": ["content"],
        "source_size": {"width": width, "height": height},
        "sizing_mode": "nine-slice",
        "slice_margins": {"top": margin, "right": margin, "bottom": margin, "left": margin},
        "content_safe_area": {"top": margin, "right": margin, "bottom": margin, "left": margin},
        "padding": {"top": padding, "right": padding, "bottom": padding, "left": padding},
        "border": {"style": "solid", "width": 1},
        "corner": {"style": "square", "radius": 0},
        "decor_density": "low",
        "edge_mode": "stretch",
        "center_mode": "stretch",
        "opacity": 1.0,
        "states": states,
        "target_resolution": {"width": 1920, "height": 1080},
        "device_safe_area": {"top": 0, "right": 0, "bottom": 0, "left": 0},
        "text_free": True,
        "animation_mode": "ui_static",
        "frame_count": 1,
        "direction_mode": "none",
    }


def golden_job_http_payload(job: dict) -> dict:
    contract = job["contract"]
    width = contract["canvas"]["width"]
    height = contract["canvas"]["height"]
    common = {
        "prompt": job["prompt"],
        "aspect_ratio": _aspect(width, height),
        "output": {"width": width, "height": height, "background": "transparent"},
    }
    if job["family"] == "object":
        return {
            **common,
            "asset_family": "object",
            "asset_type": "item",
            "object": _object_contract(width, height),
        }
    if job["family"] == "actor":
        return {
            **common,
            "asset_family": "sprite",
            "asset_type": "character",
            "background_mode": "none",
            "sprite": {
                "animation_mode": contract["action"],
                "direction_mode": "single",
                "target_direction": "S",
                "reference_direction": "S",
                "frame_count": contract["frame_count"],
                "walk_frames": contract["frame_count"],
                "chroma_mode": "global",
            },
        }
    if job["family"] == "ui":
        return {
            **common,
            "asset_family": "ui",
            "asset_type": "button",
            "ui": _ui_contract(width, height, contract["states"]),
        }
    return {
        **common,
        "asset_family": "sprite",
        "asset_type": "effect",
        "background_mode": "none",
        "sprite": {
            "sequence_mode": "sequence",
            "effect_category": "impact",
            "loop": "one-shot",
            "frame_count": contract["frame_count"],
            "rows": 1,
            "columns": contract["frame_count"],
            "envelope_width": width,
            "envelope_height": height,
            "pivot": {
                "preset": "source",
                "x": contract["pivot"]["x"],
                "y": contract["pivot"]["y"],
            },
        },
    }


def _observable_local_results(job: dict, artifact_path: Path) -> dict:
    with Image.open(artifact_path) as source:
        image = source.convert("RGBA")
    expected = job["contract"]["canvas"]
    width, height = image.size
    pixels = list(image.getdata())
    corners = [
        image.getpixel((0, 0))[3],
        image.getpixel((width - 1, 0))[3],
        image.getpixel((0, height - 1))[3],
        image.getpixel((width - 1, height - 1))[3],
    ]
    opaque_pixels = sum(1 for pixel in pixels if pixel[3] > 0)
    required = set(job["required_local_checks"])
    results = {}

    def include(check_id: str, passed: bool, reason: str, observations: dict) -> None:
        if check_id in required:
            results[check_id] = {
                "passed": passed,
                "reasons": [] if passed else [reason],
                "observations": observations,
            }

    include(
        "canvas-size",
        (width, height) == (expected["width"], expected["height"]),
        "HTTP artifact dimensions do not match the Golden Job canvas",
        {"actual": {"width": width, "height": height}, "expected": expected},
    )
    include(
        "transparent-background",
        all(alpha == 0 for alpha in corners),
        "one or more artifact corners are opaque",
        {"corner_alpha": corners},
    )
    include(
        "non-empty-content",
        opaque_pixels > 0,
        "artifact has no visible pixels",
        {"opaque_pixels": opaque_pixels},
    )
    include(
        "required-reference-present",
        False,
        "current /api/generate path did not forward the identity master reference",
        {"sent_reference_count": 0},
    )
    if "border-clearance" in required:
        bbox = image.getbbox()
        clearance = 0 if bbox is None else min(bbox[0], bbox[1], width - bbox[2], height - bbox[3])
        include(
            "border-clearance",
            bbox is not None and clearance >= 1,
            "visible pixels touch the artifact border",
            {"minimum_clearance_pixels": clearance},
        )
    if "palette-budget" in required:
        visible_colors = len({pixel for pixel in pixels if pixel[3] > 0})
        include(
            "palette-budget",
            visible_colors <= 32,
            "artifact exceeds the 32-color Golden Job palette budget",
            {"visible_colors": visible_colors, "maximum_colors": 32},
        )
    return results


def _evaluation_metrics(job: dict, *, local_pass: bool, visual_pass: bool) -> list[dict]:
    values = {metric_id: None for metric_id in job["required_metrics"]}
    values.update(
        {
            "provider-response-success": True,
            "local-qa-pass": local_pass,
            "visual-qa-pass": visual_pass,
            "user-approval": False,
            "candidates-to-approval": None,
            "manual-edit-seconds": None,
            "export-contract-match": False,
        }
    )
    if "regenerated-frames" in values:
        values["regenerated-frames"] = 0
    return [{"id": metric_id, "value": values[metric_id]} for metric_id in job["required_metrics"]]


def evaluate_golden_job_over_http(
    job: dict,
    rubric: dict,
    harness,
    log_path: Path,
    *,
    run_number: int,
) -> dict:
    job = validate_golden_job(job)
    rubric = validate_quality_rubric(rubric)
    payload = golden_job_http_payload(job)
    previous_calls = len(harness.provider.calls)
    response = harness.post_json("/api/generate", payload)
    body = response.json()
    if response.status != 200 or not body.get("success"):
        raise AssertionError(f"Golden Job HTTP generation failed: {response.status} {body}")
    if len(harness.provider.calls) != previous_calls + 1:
        raise AssertionError("Golden Job must invoke the Fake Provider exactly once")

    artifact_path = Path(body["path"])
    artifact_bytes = artifact_path.read_bytes()
    local_results = _observable_local_results(job, artifact_path)
    aggregated = aggregate_evaluation(
        job,
        rubric,
        generation_status="succeeded",
        candidate_present=True,
        local_results=local_results,
        visual_results={},
    )
    actual_prompt = harness.provider.calls[-1]["prompt"]
    timestamp = f"2026-07-12T03:{run_number:02d}:00Z"
    finished = f"2026-07-12T03:{run_number:02d}:01Z"
    candidate_id = f"fake-{job['job_id']}-{run_number:03d}"
    record = {
        "schema_version": "asset-studio.evaluation-run/v1",
        "run_id": f"run-{candidate_id}",
        "job_id": job["job_id"],
        "recipe_id": job["recipe_id"],
        "output_profile_id": job["output_profile_id"],
        "started_at": timestamp,
        "finished_at": finished,
        "request": {
            "prompt": actual_prompt,
            "prompt_sha256": hashlib.sha256(actual_prompt.encode("utf-8")).hexdigest(),
            "reference_sha256s": [],
            "parameters": {
                "transport": "in-memory-http-handler",
                "asset_family": payload["asset_family"],
                "asset_type": payload["asset_type"],
                "aspect_ratio": payload["aspect_ratio"],
            },
        },
        "generation": {
            "status": "succeeded",
            "call_count": 1,
            "provider": body["provider"],
            "model": body["model"],
            "error": None,
        },
        "candidate": {
            "candidate_id": candidate_id,
            "artifact_ref": f"generated/{artifact_path.name}",
            "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
            "media_type": "image/png",
        },
        "postprocess": {
            "pipeline_version": "server-postprocess-v1",
            "steps": [{"id": "server-postprocess", "version": "v1"}],
        },
        "local_qa": aggregated["local_qa"],
        "visual_qa": aggregated["visual_qa"],
        "aggregate": aggregated["aggregate"],
        "metrics": _evaluation_metrics(
            job,
            local_pass=aggregated["local_qa"]["status"] == "passed",
            visual_pass=aggregated["visual_qa"]["status"] == "passed",
        ),
        "user_decision": {"status": "pending", "decided_at": None, "reason": None},
    }
    validated = validate_evaluation_run(record)
    append_evaluation_run(log_path, validated)
    return validated
