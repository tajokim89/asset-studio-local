from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import math
import os
import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


SCHEMA_VERSION = "asset-studio.evaluation-run/v1"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RFC3339_UTC = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)


class EvaluationRunValidationError(ValueError):
    """Raised when an evaluation run violates its versioned contract."""


class GoldenJobValidationError(ValueError):
    """Raised when a repeatable evaluation job violates its contract."""


class QualityRubricValidationError(ValueError):
    """Raised when a quality rubric can hide or misclassify a failure."""


class EvaluationAggregationError(ValueError):
    """Raised when raw QA observations cannot be aggregated safely."""


class EvaluationLogError(ValueError):
    """Raised when an append-only evaluation log is invalid or unsafe to extend."""


def _fail(path: str, message: str) -> None:
    raise EvaluationRunValidationError(f"{path}: {message}")


def _object(value: Any, path: str, keys: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(path, "must be an object")
    actual = set(value)
    if actual != keys:
        missing = sorted(keys - actual)
        unknown = sorted(actual - keys)
        details = []
        if missing:
            details.append(f"missing {missing}")
        if unknown:
            details.append(f"unknown {unknown}")
        _fail(path, "; ".join(details))
    return value


def _string(value: Any, path: str, *, minimum: int = 1, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not minimum <= len(value) <= maximum:
        _fail(path, f"must be a string with length {minimum}..{maximum}")
    return value


def _identifier(value: Any, path: str) -> str:
    value = _string(value, path, maximum=128)
    if not _IDENTIFIER.fullmatch(value):
        _fail(path, "must be a portable identifier")
    return value


def _digest(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        _fail(path, "must be a lowercase SHA-256 digest")
    return value


def _timestamp(value: Any, path: str) -> datetime:
    if not isinstance(value, str) or not _RFC3339_UTC.fullmatch(value):
        _fail(path, "must be an RFC3339 UTC timestamp ending in Z")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        _fail(path, "contains an invalid calendar date or time")


def _enum(value: Any, path: str, choices: set[str]) -> str:
    if value not in choices:
        _fail(path, f"must be one of {sorted(choices)}")
    return value


def _json_parameters(value: Any, path: str) -> None:
    if not isinstance(value, Mapping):
        _fail(path, "must be an object")
    try:
        encoded = json.dumps(value, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        _fail(path, f"must contain finite JSON values ({exc})")
    if len(encoded.encode("utf-8")) > 65536:
        _fail(path, "must not exceed 65536 encoded bytes")


def _qa_stage(value: Any, path: str) -> str:
    stage = _object(value, path, {"status", "checks"})
    status = _enum(stage["status"], f"{path}.status", {"not_run", "passed", "failed"})
    checks = stage["checks"]
    if not isinstance(checks, list) or len(checks) > 128:
        _fail(f"{path}.checks", "must be an array with at most 128 checks")

    seen = set()
    check_statuses = []
    for index, raw_check in enumerate(checks):
        check_path = f"{path}.checks[{index}]"
        check = _object(
            raw_check, check_path, {"id", "status", "reasons", "observations"}
        )
        check_id = _identifier(check["id"], f"{check_path}.id")
        if check_id in seen:
            _fail(f"{check_path}.id", "must be unique within the QA stage")
        seen.add(check_id)
        check_status = _enum(
            check["status"], f"{check_path}.status", {"passed", "failed"}
        )
        reasons = check["reasons"]
        if not isinstance(reasons, list) or len(reasons) > 32:
            _fail(f"{check_path}.reasons", "must be an array with at most 32 reasons")
        for reason_index, reason in enumerate(reasons):
            _string(reason, f"{check_path}.reasons[{reason_index}]", maximum=1024)
        if check_status == "failed" and not reasons:
            _fail(f"{check_path}.reasons", "must explain a failed check")
        _json_parameters(check["observations"], f"{check_path}.observations")
        check_statuses.append(check_status)

    if status == "not_run" and checks:
        _fail(path, "not_run stages cannot contain checks")
    if status == "passed" and (not checks or set(check_statuses) != {"passed"}):
        _fail(path, "passed stages require one or more passed checks")
    if status == "failed" and "failed" not in check_statuses:
        _fail(path, "failed stages require at least one failed check")
    return status


def _artifact_ref(value: Any, path: str) -> None:
    value = _string(value, path, maximum=512)
    artifact = PurePosixPath(value)
    if artifact.is_absolute() or "\\" in value or ".." in artifact.parts or value.endswith("/"):
        _fail(path, "must be a safe relative POSIX path")


def validate_evaluation_run(manifest: Any) -> dict[str, Any]:
    """Validate one completed evaluation run and return an isolated copy."""

    top_keys = {
        "schema_version",
        "run_id",
        "job_id",
        "recipe_id",
        "output_profile_id",
        "started_at",
        "finished_at",
        "request",
        "generation",
        "candidate",
        "postprocess",
        "local_qa",
        "visual_qa",
        "aggregate",
        "metrics",
        "user_decision",
    }
    run = _object(manifest, "$", top_keys)
    if run["schema_version"] != SCHEMA_VERSION:
        _fail("$.schema_version", f"must equal {SCHEMA_VERSION!r}")
    for key in ("run_id", "job_id", "recipe_id", "output_profile_id"):
        _identifier(run[key], f"$.{key}")
    started = _timestamp(run["started_at"], "$.started_at")
    finished = _timestamp(run["finished_at"], "$.finished_at")
    if finished < started:
        _fail("$.finished_at", "must not precede started_at")

    request = _object(
        run["request"],
        "$.request",
        {"prompt", "prompt_sha256", "reference_sha256s", "parameters"},
    )
    _string(request["prompt"], "$.request.prompt", maximum=12000)
    _digest(request["prompt_sha256"], "$.request.prompt_sha256")
    actual_prompt_digest = hashlib.sha256(request["prompt"].encode("utf-8")).hexdigest()
    if request["prompt_sha256"] != actual_prompt_digest:
        _fail("$.request.prompt_sha256", "does not match the UTF-8 prompt bytes")
    references = request["reference_sha256s"]
    if not isinstance(references, list) or len(references) > 16:
        _fail("$.request.reference_sha256s", "must be an array with at most 16 digests")
    for index, digest in enumerate(references):
        _digest(digest, f"$.request.reference_sha256s[{index}]")
    if len(set(references)) != len(references):
        _fail("$.request.reference_sha256s", "must not contain duplicate digests")
    _json_parameters(request["parameters"], "$.request.parameters")

    generation = _object(
        run["generation"],
        "$.generation",
        {"status", "call_count", "provider", "model", "error"},
    )
    generation_status = _enum(
        generation["status"], "$.generation.status", {"not_called", "succeeded", "failed"}
    )
    if type(generation["call_count"]) is not int or generation["call_count"] not in (0, 1):
        _fail("$.generation.call_count", "must be 0 or 1")
    _identifier(generation["provider"], "$.generation.provider")
    _identifier(generation["model"], "$.generation.model")
    error = generation["error"]
    if error is not None:
        error = _object(error, "$.generation.error", {"code", "message"})
        _identifier(error["code"], "$.generation.error.code")
        _string(error["message"], "$.generation.error.message", maximum=2048)

    candidate = run["candidate"]
    if candidate is not None:
        candidate = _object(
            candidate,
            "$.candidate",
            {"candidate_id", "artifact_ref", "sha256", "media_type"},
        )
        _identifier(candidate["candidate_id"], "$.candidate.candidate_id")
        _artifact_ref(candidate["artifact_ref"], "$.candidate.artifact_ref")
        _digest(candidate["sha256"], "$.candidate.sha256")
        if candidate["media_type"] != "image/png":
            _fail("$.candidate.media_type", "must equal 'image/png'")

    if generation_status == "succeeded":
        if generation["call_count"] != 1 or error is not None or candidate is None:
            _fail("$.generation", "succeeded requires one call, no error, and one candidate")
    elif generation_status == "failed":
        if generation["call_count"] != 1 or error is None or candidate is not None:
            _fail("$.generation", "failed requires one call, an error, and no candidate")
    elif generation["call_count"] != 0 or candidate is not None:
        _fail("$.generation", "not_called requires zero calls and no candidate")

    postprocess = _object(
        run["postprocess"], "$.postprocess", {"pipeline_version", "steps"}
    )
    _identifier(postprocess["pipeline_version"], "$.postprocess.pipeline_version")
    steps = postprocess["steps"]
    if not isinstance(steps, list) or len(steps) > 64:
        _fail("$.postprocess.steps", "must be an array with at most 64 steps")
    for index, raw_step in enumerate(steps):
        step_path = f"$.postprocess.steps[{index}]"
        step = _object(raw_step, step_path, {"id", "version"})
        _identifier(step["id"], f"{step_path}.id")
        _identifier(step["version"], f"{step_path}.version")

    local_status = _qa_stage(run["local_qa"], "$.local_qa")
    visual_status = _qa_stage(run["visual_qa"], "$.visual_qa")
    if generation_status != "succeeded" and (
        local_status != "not_run" or visual_status != "not_run"
    ):
        _fail("$.local_qa", "QA cannot run when generation did not succeed")
    if local_status != "passed" and visual_status != "not_run":
        _fail("$.visual_qa", "cannot run before local QA passes")

    aggregate = _object(run["aggregate"], "$.aggregate", {"status", "reasons"})
    aggregate_status = _enum(
        aggregate["status"], "$.aggregate.status", {"pending", "passed", "failed"}
    )
    aggregate_reasons = aggregate["reasons"]
    if not isinstance(aggregate_reasons, list) or len(aggregate_reasons) > 64:
        _fail("$.aggregate.reasons", "must be an array with at most 64 reasons")
    for index, reason in enumerate(aggregate_reasons):
        _string(reason, f"$.aggregate.reasons[{index}]", maximum=1024)

    detailed_failure = "failed" in {local_status, visual_status}
    detailed_pass = local_status == visual_status == "passed"
    if aggregate_status == "passed" and not detailed_pass:
        _fail("$.aggregate", "cannot pass unless both detailed QA stages pass")
    if detailed_pass and aggregate_status != "passed":
        _fail("$.aggregate", "must pass when both detailed QA stages pass")
    if detailed_failure and aggregate_status != "failed":
        _fail("$.aggregate", "must fail when any detailed QA stage fails")
    if aggregate_status == "failed" and not aggregate_reasons:
        _fail("$.aggregate.reasons", "must explain an aggregate failure")

    metrics = run["metrics"]
    if not isinstance(metrics, list) or not metrics or len(metrics) > 128:
        _fail("$.metrics", "must be a non-empty array with at most 128 metrics")
    metric_values = {}
    for index, raw_metric in enumerate(metrics):
        metric_path = f"$.metrics[{index}]"
        metric = _object(raw_metric, metric_path, {"id", "value"})
        metric_id = _identifier(metric["id"], f"{metric_path}.id")
        if metric_id in metric_values:
            _fail(f"{metric_path}.id", "must be unique")
        metric_value = metric["value"]
        if metric_value is not None and type(metric_value) not in (bool, int, float):
            _fail(f"{metric_path}.value", "must be a boolean, finite number, or null")
        if type(metric_value) in (int, float) and not math.isfinite(metric_value):
            _fail(f"{metric_path}.value", "must be finite")
        if metric_id.endswith("-score") and metric_value is not None:
            if isinstance(metric_value, bool) or not 1 <= metric_value <= 5:
                _fail(f"{metric_path}.value", "score metrics must be from 1 through 5")
        metric_values[metric_id] = metric_value

    decision = _object(
        run["user_decision"],
        "$.user_decision",
        {"status", "decided_at", "reason"},
    )
    decision_status = _enum(
        decision["status"], "$.user_decision.status", {"pending", "approved", "rejected"}
    )
    if decision["reason"] is not None:
        _string(decision["reason"], "$.user_decision.reason", maximum=2048)
    if decision_status == "pending":
        if decision["decided_at"] is not None:
            _fail("$.user_decision.decided_at", "must be null while pending")
    else:
        _timestamp(decision["decided_at"], "$.user_decision.decided_at")
    if decision_status == "approved" and (aggregate_status != "passed" or candidate is None):
        _fail("$.user_decision", "approval requires a candidate and passed aggregate QA")
    if decision_status == "rejected" and not decision["reason"]:
        _fail("$.user_decision.reason", "must explain a rejection")

    expected_boolean_metrics = {
        "provider-response-success": generation_status == "succeeded",
        "local-qa-pass": local_status == "passed",
        "visual-qa-pass": visual_status == "passed",
        "user-approval": decision_status == "approved",
    }
    for metric_id, expected in expected_boolean_metrics.items():
        if metric_values.get(metric_id) is not expected:
            _fail(f"$.metrics.{metric_id}", f"must equal {expected} from detailed state")
    candidate_count = metric_values.get("candidates-to-approval")
    if decision_status == "approved":
        if (
            isinstance(candidate_count, bool)
            or not isinstance(candidate_count, (int, float))
            or candidate_count < 1
        ):
            _fail(
                "$.metrics.candidates-to-approval",
                "approved runs require a positive candidate count",
            )
    elif candidate_count is not None:
        _fail(
            "$.metrics.candidates-to-approval",
            "must be null until a candidate is approved",
        )
    edit_seconds = metric_values.get("manual-edit-seconds")
    if edit_seconds is not None and (
        isinstance(edit_seconds, bool)
        or not isinstance(edit_seconds, (int, float))
        or edit_seconds < 0
    ):
        _fail(
            "$.metrics.manual-edit-seconds",
            "must be a non-negative duration or null",
        )

    return copy.deepcopy(dict(run))


def _identifier_list(value: Any, path: str, *, minimum: int = 0, maximum: int = 128) -> list[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        _fail(path, f"must be an array with {minimum}..{maximum} identifiers")
    output = []
    for index, item in enumerate(value):
        output.append(_identifier(item, f"{path}[{index}]"))
    if len(set(output)) != len(output):
        _fail(path, "must not contain duplicate identifiers")
    return output


def _validate_golden_job(job: Any) -> dict[str, Any]:
    top_keys = {
        "schema_version",
        "job_id",
        "title",
        "family",
        "recipe_id",
        "output_profile_id",
        "quality_rubric_version",
        "prompt",
        "reference",
        "generation",
        "contract",
        "required_local_checks",
        "required_visual_checks",
        "required_metrics",
    }
    value = _object(job, "$", top_keys)
    if value["schema_version"] != "asset-studio.golden-job/v1":
        _fail("$.schema_version", "must equal 'asset-studio.golden-job/v1'")
    _identifier(value["job_id"], "$.job_id")
    _string(value["title"], "$.title", maximum=256)
    family = _enum(value["family"], "$.family", {"object", "actor", "ui", "effect"})
    _identifier(value["recipe_id"], "$.recipe_id")
    _identifier(value["output_profile_id"], "$.output_profile_id")
    _identifier(value["quality_rubric_version"], "$.quality_rubric_version")
    _string(value["prompt"], "$.prompt", maximum=12000)

    reference = _object(
        value["reference"], "$.reference", {"mode", "continuity_group", "max_images"}
    )
    reference_mode = _enum(
        reference["mode"], "$.reference.mode", {"none", "optional", "identity_master"}
    )
    if reference["continuity_group"] is not None:
        _identifier(reference["continuity_group"], "$.reference.continuity_group")
    if type(reference["max_images"]) is not int or not 0 <= reference["max_images"] <= 16:
        _fail("$.reference.max_images", "must be an integer from 0 through 16")
    if reference_mode == "none" and (
        reference["continuity_group"] is not None or reference["max_images"] != 0
    ):
        _fail("$.reference", "none mode requires no continuity group and zero images")
    if reference_mode == "identity_master" and (
        reference["continuity_group"] is None or reference["max_images"] < 1
    ):
        _fail("$.reference", "identity_master requires a continuity group and an image slot")

    generation = _object(
        value["generation"],
        "$.generation",
        {"development_runs", "release_runs", "candidates_per_run"},
    )
    for key, minimum, maximum in (
        ("development_runs", 1, 100),
        ("release_runs", 20, 1000),
        ("candidates_per_run", 1, 4),
    ):
        number = generation[key]
        if type(number) is not int or not minimum <= number <= maximum:
            _fail(f"$.generation.{key}", f"must be an integer from {minimum} through {maximum}")
    if generation["release_runs"] < generation["development_runs"]:
        _fail("$.generation.release_runs", "must not be smaller than development_runs")

    contract = _object(
        value["contract"],
        "$.contract",
        {
            "kind",
            "canvas",
            "transparent_background",
            "frame_count",
            "directions",
            "action",
            "loop",
            "states",
            "beats",
            "pivot",
        },
    )
    kind = _enum(contract["kind"], "$.contract.kind", {"static", "animation", "state_set", "sequence"})
    canvas = _object(contract["canvas"], "$.contract.canvas", {"width", "height"})
    for key in ("width", "height"):
        if type(canvas[key]) is not int or not 1 <= canvas[key] <= 4096:
            _fail(f"$.contract.canvas.{key}", "must be an integer from 1 through 4096")
    if contract["transparent_background"] is not True:
        _fail("$.contract.transparent_background", "must be true for the V1 Golden Job set")
    if type(contract["frame_count"]) is not int or not 1 <= contract["frame_count"] <= 64:
        _fail("$.contract.frame_count", "must be an integer from 1 through 64")
    directions = _identifier_list(contract["directions"], "$.contract.directions", maximum=16)
    if contract["action"] is not None:
        _identifier(contract["action"], "$.contract.action")
    if type(contract["loop"]) is not bool:
        _fail("$.contract.loop", "must be a boolean")
    states = _identifier_list(contract["states"], "$.contract.states", maximum=32)
    beats = contract["beats"]
    if not isinstance(beats, list) or len(beats) > 64:
        _fail("$.contract.beats", "must be an array with at most 64 beats")
    beat_ids = []
    for index, raw_beat in enumerate(beats):
        beat_path = f"$.contract.beats[{index}]"
        beat = _object(raw_beat, beat_path, {"id", "semantic"})
        beat_ids.append(_identifier(beat["id"], f"{beat_path}.id"))
        _string(beat["semantic"], f"{beat_path}.semantic", maximum=256)
    if len(set(beat_ids)) != len(beat_ids):
        _fail("$.contract.beats", "must not contain duplicate beat ids")
    pivot = _object(contract["pivot"], "$.contract.pivot", {"x", "y"})
    for key in ("x", "y"):
        coordinate = pivot[key]
        if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)) or not 0 <= coordinate <= 1:
            _fail(f"$.contract.pivot.{key}", "must be a finite normalized coordinate")

    if kind == "static":
        if family != "object" or contract["frame_count"] != 1 or directions or states or beats:
            _fail("$.contract", "static jobs require one object frame and no sequence fields")
        if contract["action"] is not None or contract["loop"]:
            _fail("$.contract", "static jobs cannot declare an action or loop")
    elif kind == "animation":
        if family != "actor" or contract["frame_count"] < 2 or len(directions) != 1:
            _fail("$.contract", "animation jobs require an actor and one representative direction")
        if contract["action"] is None or states or len(beats) != contract["frame_count"]:
            _fail("$.contract", "animation jobs require one action and one beat per frame")
        if reference_mode != "identity_master":
            _fail("$.reference", "animation jobs require an identity master")
        if contract["action"] in {"idle", "walk"} and not contract["loop"]:
            _fail("$.contract.loop", "idle and walk Golden Jobs must loop")
        if contract["action"] == "attack" and contract["loop"]:
            _fail("$.contract.loop", "attack Golden Jobs must be one-shot")
    elif kind == "state_set":
        if family != "ui" or contract["frame_count"] < 2 or len(states) != contract["frame_count"]:
            _fail("$.contract", "state-set jobs require one named UI state per frame")
        if directions or beats or contract["action"] is not None or contract["loop"]:
            _fail("$.contract", "state-set jobs cannot declare action sequence fields")
    elif kind == "sequence":
        if family != "effect" or contract["frame_count"] < 2 or len(beats) != contract["frame_count"]:
            _fail("$.contract", "sequence jobs require one effect beat per frame")
        if directions or states or contract["action"] is None:
            _fail("$.contract", "sequence jobs require an action and no actor/UI fields")
        if contract["action"] == "impact" and contract["loop"]:
            _fail("$.contract.loop", "impact Golden Jobs must be one-shot")

    _identifier_list(value["required_local_checks"], "$.required_local_checks", minimum=1)
    _identifier_list(value["required_visual_checks"], "$.required_visual_checks", minimum=1)
    _identifier_list(value["required_metrics"], "$.required_metrics", minimum=1)
    return copy.deepcopy(dict(value))


def validate_golden_job(job: Any) -> dict[str, Any]:
    """Validate a provider-neutral repeatable job and return an isolated copy."""

    try:
        return _validate_golden_job(job)
    except EvaluationRunValidationError as exc:
        raise GoldenJobValidationError(str(exc)) from None


def _validate_quality_rubric(rubric: Any) -> dict[str, Any]:
    value = _object(
        rubric,
        "$",
        {
            "schema_version",
            "rubric_id",
            "scale",
            "decision_policy",
            "local_checks",
            "visual_checks",
            "metrics",
        },
    )
    if value["schema_version"] != "asset-studio.quality-rubric/v1":
        _fail("$.schema_version", "must equal 'asset-studio.quality-rubric/v1'")
    if value["rubric_id"] != "quality-rubric-v1":
        _fail("$.rubric_id", "must equal 'quality-rubric-v1'")

    scale = _object(value["scale"], "$.scale", {"minimum", "maximum", "pass_threshold", "anchors"})
    if (scale["minimum"], scale["maximum"], scale["pass_threshold"]) != (1, 5, 4):
        _fail("$.scale", "V1 must use a 1..5 scale with pass threshold 4")
    anchors = _object(scale["anchors"], "$.scale.anchors", {"1", "2", "3", "4", "5"})
    for score, anchor in anchors.items():
        _string(anchor, f"$.scale.anchors.{score}", maximum=512)

    policy = _object(
        value["decision_policy"],
        "$.decision_policy",
        {
            "missing_required_result",
            "any_required_failure",
            "local_failure_blocks_visual_review",
            "aggregate_pass_requires",
            "user_approval_required",
        },
    )
    if policy["missing_required_result"] != "fail":
        _fail("$.decision_policy.missing_required_result", "must fail closed")
    if policy["any_required_failure"] != "fail":
        _fail("$.decision_policy.any_required_failure", "must fail the aggregate")
    if policy["local_failure_blocks_visual_review"] is not True:
        _fail("$.decision_policy.local_failure_blocks_visual_review", "must be true")
    if policy["user_approval_required"] is not True:
        _fail("$.decision_policy.user_approval_required", "must be true")
    required_states = [
        "generation.succeeded",
        "candidate.present",
        "local_qa.passed",
        "visual_qa.passed",
    ]
    if policy["aggregate_pass_requires"] != required_states:
        _fail("$.decision_policy.aggregate_pass_requires", f"must equal {required_states}")

    families = {"object", "actor", "ui", "effect"}
    local_checks = value["local_checks"]
    if not isinstance(local_checks, list) or not local_checks:
        _fail("$.local_checks", "must be a non-empty array")
    local_index = {}
    for index, raw_check in enumerate(local_checks):
        path = f"$.local_checks[{index}]"
        check = _object(
            raw_check,
            path,
            {"id", "families", "blocking", "evaluator", "parameters", "description"},
        )
        check_id = _identifier(check["id"], f"{path}.id")
        if check_id in local_index:
            _fail(f"{path}.id", "must be unique")
        supported = set(_identifier_list(check["families"], f"{path}.families", minimum=1, maximum=4))
        if not supported <= families:
            _fail(f"{path}.families", "contains an unsupported family")
        if check["blocking"] is not True:
            _fail(f"{path}.blocking", "required V1 checks must be blocking")
        _identifier(check["evaluator"], f"{path}.evaluator")
        _json_parameters(check["parameters"], f"{path}.parameters")
        _string(check["description"], f"{path}.description", maximum=1024)
        local_index[check_id] = check

    visual_checks = value["visual_checks"]
    if not isinstance(visual_checks, list) or not visual_checks:
        _fail("$.visual_checks", "must be a non-empty array")
    visual_index = {}
    for index, raw_check in enumerate(visual_checks):
        path = f"$.visual_checks[{index}]"
        check = _object(
            raw_check,
            path,
            {
                "id",
                "families",
                "blocking",
                "minimum_score",
                "question",
                "pass_anchor",
                "fail_anchor",
            },
        )
        check_id = _identifier(check["id"], f"{path}.id")
        if check_id in visual_index:
            _fail(f"{path}.id", "must be unique")
        supported = set(_identifier_list(check["families"], f"{path}.families", minimum=1, maximum=4))
        if not supported <= families:
            _fail(f"{path}.families", "contains an unsupported family")
        if check["blocking"] is not True:
            _fail(f"{path}.blocking", "required V1 checks must be blocking")
        if type(check["minimum_score"]) is not int or check["minimum_score"] < scale["pass_threshold"]:
            _fail(f"{path}.minimum_score", "must meet the global pass threshold")
        for field in ("question", "pass_anchor", "fail_anchor"):
            _string(check[field], f"{path}.{field}", maximum=1024)
        visual_index[check_id] = check

    metrics = value["metrics"]
    if not isinstance(metrics, list) or not metrics:
        _fail("$.metrics", "must be a non-empty array")
    metric_index = {}
    for index, raw_metric in enumerate(metrics):
        path = f"$.metrics[{index}]"
        metric = _object(
            raw_metric,
            path,
            {"id", "unit", "direction", "aggregation", "description"},
        )
        metric_id = _identifier(metric["id"], f"{path}.id")
        if metric_id in metric_index:
            _fail(f"{path}.id", "must be unique")
        _identifier(metric["unit"], f"{path}.unit")
        _enum(
            metric["direction"],
            f"{path}.direction",
            {"higher_is_better", "lower_is_better", "target_is_true"},
        )
        _enum(metric["aggregation"], f"{path}.aggregation", {"rate", "mean", "median"})
        _string(metric["description"], f"{path}.description", maximum=1024)
        metric_index[metric_id] = metric

    for check_id in ("identity-consistency", "action-readability", "loop-naturalness"):
        if check_id not in visual_index or visual_index[check_id]["minimum_score"] < 4:
            _fail("$.visual_checks", f"must define {check_id!r} with minimum score 4")
    pivot = local_index.get("pivot-drift")
    max_pixels = pivot and pivot["parameters"].get("max_pixels")
    if isinstance(max_pixels, bool) or not isinstance(max_pixels, (int, float)) or not 0 <= max_pixels <= 1:
        _fail("$.local_checks", "pivot-drift must cap displacement at one pixel")
    for metric_id in ("manual-edit-seconds", "regenerated-frames"):
        if metric_id not in metric_index or metric_index[metric_id]["direction"] != "lower_is_better":
            _fail("$.metrics", f"{metric_id!r} must be lower_is_better")
    if metric_index["manual-edit-seconds"]["unit"] != "seconds":
        _fail("$.metrics", "manual-edit-seconds must use seconds")

    return copy.deepcopy(dict(value))


def validate_quality_rubric(rubric: Any) -> dict[str, Any]:
    """Validate the fail-closed V1 quality rubric and return an isolated copy."""

    try:
        return _validate_quality_rubric(rubric)
    except EvaluationRunValidationError as exc:
        raise QualityRubricValidationError(str(exc)) from None


def _result_reasons(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or len(value) > 32:
        _fail(path, "must be an array with at most 32 reasons")
    reasons = []
    for index, reason in enumerate(value):
        reasons.append(_string(reason, f"{path}[{index}]", maximum=1024))
    return reasons


def _aggregate_evaluation(
    job: Any,
    rubric: Any,
    *,
    generation_status: str,
    candidate_present: bool,
    local_results: Any,
    visual_results: Any,
) -> dict[str, Any]:
    golden_job = validate_golden_job(job)
    quality_rubric = validate_quality_rubric(rubric)
    if golden_job["quality_rubric_version"] != quality_rubric["rubric_id"]:
        _fail("$.quality_rubric_version", "does not match the supplied rubric")
    _enum(generation_status, "$.generation_status", {"not_called", "succeeded", "failed"})
    if type(candidate_present) is not bool:
        _fail("$.candidate_present", "must be a boolean")
    if not isinstance(local_results, Mapping):
        _fail("$.local_results", "must be an object keyed by check id")
    if not isinstance(visual_results, Mapping):
        _fail("$.visual_results", "must be an object keyed by check id")

    required_local = golden_job["required_local_checks"]
    required_visual = golden_job["required_visual_checks"]
    unknown_local = sorted(set(local_results) - set(required_local))
    unknown_visual = sorted(set(visual_results) - set(required_visual))
    if unknown_local:
        _fail("$.local_results", f"contains non-required check ids {unknown_local}")
    if unknown_visual:
        _fail("$.visual_results", f"contains non-required check ids {unknown_visual}")

    local_definitions = {item["id"]: item for item in quality_rubric["local_checks"]}
    visual_definitions = {item["id"]: item for item in quality_rubric["visual_checks"]}
    for check_id in required_local:
        definition = local_definitions.get(check_id)
        if definition is None or golden_job["family"] not in definition["families"]:
            _fail("$.required_local_checks", f"{check_id!r} is not defined for this family")
    for check_id in required_visual:
        definition = visual_definitions.get(check_id)
        if definition is None or golden_job["family"] not in definition["families"]:
            _fail("$.required_visual_checks", f"{check_id!r} is not defined for this family")

    if generation_status != "succeeded" or not candidate_present:
        reasons = []
        if generation_status != "succeeded":
            reasons.append(f"generation status is {generation_status}")
        if not candidate_present:
            reasons.append("candidate is missing")
        return {
            "local_qa": {"status": "not_run", "checks": []},
            "visual_qa": {"status": "not_run", "checks": []},
            "aggregate": {"status": "failed", "reasons": reasons},
        }

    local_checks = []
    local_failures = []
    for check_id in required_local:
        raw_result = local_results.get(check_id)
        if raw_result is None:
            check = {
                "id": check_id,
                "status": "failed",
                "reasons": ["missing required result"],
                "observations": {},
            }
        else:
            path = f"$.local_results.{check_id}"
            result = _object(raw_result, path, {"passed", "reasons", "observations"})
            if type(result["passed"]) is not bool:
                _fail(f"{path}.passed", "must be a boolean")
            reasons = _result_reasons(result["reasons"], f"{path}.reasons")
            _json_parameters(result["observations"], f"{path}.observations")
            status = "passed" if result["passed"] else "failed"
            if status == "failed" and not reasons:
                reasons = ["check reported failure without a reason"]
            check = {
                "id": check_id,
                "status": status,
                "reasons": reasons,
                "observations": copy.deepcopy(dict(result["observations"])),
            }
        local_checks.append(check)
        if check["status"] == "failed":
            local_failures.append(f"local:{check_id}: {check['reasons'][0]}")

    local_qa = {
        "status": "failed" if local_failures else "passed",
        "checks": local_checks,
    }
    if local_failures:
        return {
            "local_qa": local_qa,
            "visual_qa": {"status": "not_run", "checks": []},
            "aggregate": {"status": "failed", "reasons": local_failures},
        }

    visual_checks = []
    visual_failures = []
    for check_id in required_visual:
        definition = visual_definitions[check_id]
        raw_result = visual_results.get(check_id)
        if raw_result is None:
            check = {
                "id": check_id,
                "status": "failed",
                "reasons": ["missing required result"],
                "observations": {},
            }
        else:
            path = f"$.visual_results.{check_id}"
            result = _object(raw_result, path, {"score", "reasons", "observations"})
            score = result["score"]
            if type(score) is not int or not 1 <= score <= 5:
                _fail(f"{path}.score", "must be an integer from 1 through 5")
            reasons = _result_reasons(result["reasons"], f"{path}.reasons")
            _json_parameters(result["observations"], f"{path}.observations")
            if "score" in result["observations"]:
                _fail(f"{path}.observations", "score is a reserved observation key")
            status = "passed" if score >= definition["minimum_score"] else "failed"
            if status == "failed" and not reasons:
                reasons = [
                    f"score {score} is below required {definition['minimum_score']}"
                ]
            observations = copy.deepcopy(dict(result["observations"]))
            observations["score"] = score
            check = {
                "id": check_id,
                "status": status,
                "reasons": reasons,
                "observations": observations,
            }
        visual_checks.append(check)
        if check["status"] == "failed":
            visual_failures.append(f"visual:{check_id}: {check['reasons'][0]}")

    visual_qa = {
        "status": "failed" if visual_failures else "passed",
        "checks": visual_checks,
    }
    return {
        "local_qa": local_qa,
        "visual_qa": visual_qa,
        "aggregate": {
            "status": "failed" if visual_failures else "passed",
            "reasons": visual_failures,
        },
    }


def aggregate_evaluation(
    job: Any,
    rubric: Any,
    *,
    generation_status: str,
    candidate_present: bool,
    local_results: Any,
    visual_results: Any,
) -> dict[str, Any]:
    """Derive QA and aggregate states solely from required detailed results."""

    try:
        return _aggregate_evaluation(
            job,
            rubric,
            generation_status=generation_status,
            candidate_present=candidate_present,
            local_results=local_results,
            visual_results=visual_results,
        )
    except (
        EvaluationRunValidationError,
        GoldenJobValidationError,
        QualityRubricValidationError,
    ) as exc:
        raise EvaluationAggregationError(str(exc)) from None


_MAX_EVALUATION_LINE_BYTES = 2 * 1024 * 1024


def _canonical_evaluation_line(manifest: Mapping[str, Any]) -> bytes:
    payload = json.dumps(
        manifest,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(payload) > _MAX_EVALUATION_LINE_BYTES:
        raise EvaluationLogError("evaluation record exceeds the 2 MiB JSONL line limit")
    return payload + b"\n"


def _decode_evaluation_log(raw: bytes, source: Path) -> list[dict[str, Any]]:
    if not raw:
        return []
    if not raw.endswith(b"\n"):
        raise EvaluationLogError(f"{source}: truncated JSONL record; final newline is missing")

    records = []
    run_ids = set()
    for line_number, encoded_line in enumerate(raw.splitlines(), start=1):
        if not encoded_line:
            raise EvaluationLogError(f"{source}:{line_number}: blank JSONL records are not allowed")
        if len(encoded_line) > _MAX_EVALUATION_LINE_BYTES:
            raise EvaluationLogError(f"{source}:{line_number}: record exceeds the 2 MiB limit")
        try:
            decoded_line = encoded_line.decode("utf-8")
            manifest = json.loads(decoded_line)
            validated = validate_evaluation_run(manifest)
        except (UnicodeDecodeError, json.JSONDecodeError, EvaluationRunValidationError) as exc:
            raise EvaluationLogError(f"{source}:{line_number}: invalid evaluation record ({exc})") from None
        run_id = validated["run_id"]
        if run_id in run_ids:
            raise EvaluationLogError(f"{source}:{line_number}: duplicate run_id {run_id!r}")
        run_ids.add(run_id)
        records.append(validated)
    return records


def read_evaluation_runs(path: Any) -> list[dict[str, Any]]:
    """Read and validate every record from an append-only evaluation JSONL log."""

    log_path = Path(path)
    if not log_path.exists():
        return []
    try:
        with log_path.open("rb") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            try:
                raw = handle.read()
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError as exc:
        raise EvaluationLogError(f"{log_path}: unable to read evaluation log ({exc})") from None
    return _decode_evaluation_log(raw, log_path)


def append_evaluation_run(path: Any, manifest: Any) -> int:
    """Validate and append one canonical record, returning its one-based line number."""

    log_path = Path(path)
    try:
        validated = validate_evaluation_run(manifest)
        encoded_line = _canonical_evaluation_line(validated)
    except (EvaluationRunValidationError, TypeError, ValueError) as exc:
        if isinstance(exc, EvaluationLogError):
            raise
        raise EvaluationLogError(f"refusing to append invalid evaluation record ({exc})") from None

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                handle.seek(0)
                existing = _decode_evaluation_log(handle.read(), log_path)
                if any(record["run_id"] == validated["run_id"] for record in existing):
                    raise EvaluationLogError(
                        f"{log_path}: duplicate run_id {validated['run_id']!r}"
                    )
                handle.seek(0, os.SEEK_END)
                written = handle.write(encoded_line)
                if written != len(encoded_line):
                    raise EvaluationLogError(f"{log_path}: short append write")
                handle.flush()
                os.fsync(handle.fileno())
                return len(existing) + 1
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except EvaluationLogError:
        raise
    except OSError as exc:
        raise EvaluationLogError(f"{log_path}: unable to append evaluation record ({exc})") from None
