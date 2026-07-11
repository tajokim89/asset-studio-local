"""I1 strict RED contracts for the family-QA envelope and provider router.

Expected public API (implemented later in ``server.py``):

``normalize_family_qa_verdict(value) -> dict``
    Strictly validates and returns a detached canonical envelope.

``route_family_qa(request, providers=None) -> dict``
    Strictly validates a family request, chooses exactly one family route/provider,
    and returns the canonical envelope. ``providers`` is an optional mapping of
    local test doubles keyed by provider id; no network/provider is used here.

These tests deliberately fail until I2/I3 production code exists.  They must not
start the HTTP server, invoke generation, or contact a paid/external provider.
"""

import copy
import json
import math
from datetime import datetime

import pytest

import server


SCHEMA_VERSION = "asset-studio.family-qa/v1"
ENVELOPE_KEYS = {
    "schema_version", "request_id", "result_id", "timestamp", "family", "subtype",
    "route", "verdict", "reasons", "metrics", "warnings", "artifact_refs", "provider",
    "deterministic", "visual",
}
RESULT_KEYS = {"status", "verdict", "reasons", "metrics", "warnings"}
PROVIDER_KEYS = {"id", "method", "version"}


def _normalizer():
    fn = getattr(server, "normalize_family_qa_verdict", None)
    assert callable(fn), "server.normalize_family_qa_verdict(value) public API is absent"
    return fn


def _router():
    fn = getattr(server, "route_family_qa", None)
    assert callable(fn), "server.route_family_qa(request, providers=None) public API is absent"
    return fn


def valid_envelope():
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": "qa-req_01",
        "result_id": "qa-res_01",
        "timestamp": "2026-07-11T12:34:56.789Z",
        "family": "sprite",
        "subtype": "character",
        "route": "actor_motion",
        "verdict": "PARTIAL",
        "reasons": ["visual_provider_not_run"],
        "metrics": {"frame_count": 4, "alpha_coverage": 0.625},
        "warnings": ["deterministic_only"],
        "artifact_refs": ["artifacts/qa/walk-01.png", "https://example.invalid/qa/walk-01.json"],
        "provider": {"id": "builtin-deterministic", "method": "geometry", "version": "1.0.0"},
        "deterministic": {
            "status": "COMPLETE", "verdict": "PASS", "reasons": [],
            "metrics": {"frame_count": 4, "alpha_coverage": 0.625}, "warnings": [],
        },
        "visual": {
            "status": "NOT_RUN", "verdict": "PARTIAL",
            "reasons": ["provider_not_requested"], "metrics": {}, "warnings": [],
        },
    }


def actor_contract():
    return {
        "animation_mode": "walk", "direction_mode": "8dir", "target_direction": "S",
        "reference_direction": "S", "frame_count": 4, "walk_frames": 4,
        "chroma_mode": "outer", "preservation": {}, "equipment": {}, "gait": {},
        "no_baked_vfx": True,
    }


def requests():
    return {
        "actor_motion": {
            "request_id": "req-actor-1", "family": "sprite", "subtype": "character",
            "contract": actor_contract(), "artifact_refs": ["artifacts/actor/walk.png"],
            "provider": {"id": "builtin-deterministic", "method": "geometry", "version": "1.0.0"},
        },
        "effect_sequence": {
            "request_id": "req-effect-1", "family": "effect", "subtype": "sequence",
            "contract": {"sequence_mode": "sheet", "effect_category": "Smoke", "frame_count": 4,
                         "rows": 1, "columns": 4, "gap": 0, "loop": "loop", "fps": 12,
                         "pivot": {"x": .5, "y": .5}, "size_basis": "actor-relative",
                         "trim_policy": "full-cell"},
            "artifact_refs": ["artifacts/effect/smoke.png"],
            "provider": {"id": "builtin-deterministic", "method": "sequence", "version": "1.0.0"},
        },
        "tile_topology_repeat": {
            "request_id": "req-tile-1", "family": "tile", "subtype": "autotile",
            "contract": {"tile_size": {"width": 32, "height": 32}, "mode": "autotile",
                         "rows": 8, "columns": 8, "margin": 0, "spacing": 0,
                         "seamless": True, "topology": "blob", "inner_corners": True,
                         "outer_corners": True, "transitions": [], "terrain_types": ["stone"],
                         "variants": [], "metadata": {}},
            "artifact_refs": ["artifacts/tile/crypt.png"],
            "provider": {"id": "builtin-deterministic", "method": "topology-repeat", "version": "1.0.0"},
        },
        "ui_nine_slice_state": {
            "request_id": "req-ui-1", "family": "ui", "subtype": "button",
            "contract": {"source_size": {"width": 96, "height": 32}, "sizing_mode": "nine-slice",
                         "slice_margins": {"top": 8, "right": 8, "bottom": 8, "left": 8},
                         "content_safe_area": {"top": 8, "right": 8, "bottom": 8, "left": 8},
                         "states": ["normal", "hover", "pressed", "disabled"], "text_free": True},
            "artifact_refs": ["artifacts/ui/button.png"],
            "provider": {"id": "builtin-deterministic", "method": "nine-slice-state", "version": "1.0.0"},
        },
        "object_placement_state": {
            "request_id": "req-object-1", "family": "object", "subtype": "interactable",
            "contract": {"usage": "world", "view": "three-quarter",
                         "placement": {"pivot": {"x": .5, "y": 1},
                                       "ground_point": {"x": .5, "y": 1},
                                       "y_sort_point": {"x": .5, "y": 1}, "snap_points": []},
                         "states": ["closed", "open"], "variants": [],
                         "collision": {}, "interaction": {}, "custom_properties": {}},
            "artifact_refs": ["artifacts/object/chest.png"],
            "provider": {"id": "builtin-deterministic", "method": "placement-state", "version": "1.0.0"},
        },
    }


def test_canonical_envelope_exact_schema_and_json_roundtrip():
    out = _normalizer()(valid_envelope())
    assert set(out) == ENVELOPE_KEYS
    assert out["schema_version"] == SCHEMA_VERSION
    assert out["family"] in {"sprite", "effect", "tile", "ui", "object"}
    assert out["verdict"] in {"PASS", "FAIL", "PARTIAL"}
    assert set(out["provider"]) == PROVIDER_KEYS
    assert set(out["deterministic"]) == set(out["visual"]) == RESULT_KEYS
    assert json.loads(json.dumps(out, allow_nan=False)) == out
    assert datetime.fromisoformat(out["timestamp"].replace("Z", "+00:00")).tzinfo is not None


def test_normalization_is_detached_deterministic_and_does_not_mutate_input():
    source = valid_envelope()
    before = copy.deepcopy(source)
    first = _normalizer()(source)
    second = _normalizer()(copy.deepcopy(source))
    assert source == before and first == second
    assert first is not source and first["metrics"] is not source["metrics"]
    source["metrics"]["frame_count"] = 999
    source["artifact_refs"].append("artifacts/poison.png")
    assert first["metrics"]["frame_count"] == 4
    assert "artifacts/poison.png" not in first["artifact_refs"]
    assert list(first) == [
        "schema_version", "request_id", "result_id", "timestamp", "family", "subtype", "route",
        "verdict", "reasons", "metrics", "warnings", "artifact_refs", "provider",
        "deterministic", "visual",
    ]
    assert json.dumps(first, separators=(",", ":"), allow_nan=False) == json.dumps(
        second, separators=(",", ":"), allow_nan=False
    )


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(extra=True),
    lambda x: x.pop("metrics"),
    lambda x: x["provider"].update(extra=True),
    lambda x: x["visual"].pop("status"),
    lambda x: x.update(schema_version="asset-studio.family-qa/v2"),
    lambda x: x.update(family="actor"),
    lambda x: x.update(verdict="pass"),
])
def test_unknown_missing_or_invalid_discriminator_keys_rejected(mutation):
    value = valid_envelope(); mutation(value)
    with pytest.raises((TypeError, ValueError)):
        _normalizer()(value)


@pytest.mark.parametrize("bad_metric", [True, False, math.nan, math.inf, -math.inf])
def test_booleans_as_numbers_and_nonfinite_metrics_rejected(bad_metric):
    value = valid_envelope(); value["metrics"]["score"] = bad_metric
    with pytest.raises((TypeError, ValueError)):
        _normalizer()(value)


@pytest.mark.parametrize("field,bad", [
    ("request_id", "../escape"), ("result_id", "bad id"), ("request_id", "qa\x00id"),
    ("timestamp", "2026-07-11 12:34:56"), ("timestamp", "2026-07-11T12:34:56"),
])
def test_unsafe_ids_controls_and_malformed_timestamps_rejected(field, bad):
    value = valid_envelope(); value[field] = bad
    with pytest.raises((TypeError, ValueError)):
        _normalizer()(value)


@pytest.mark.parametrize("bad_ref", [
    "../secret.png", "/etc/passwd", "file:///etc/passwd", "javascript:alert(1)",
    "https://user:password@example.com/a", "https://example.com/a\nInjected: yes",
])
def test_invalid_artifact_paths_urls_and_control_chars_rejected(bad_ref):
    value = valid_envelope(); value["artifact_refs"] = [bad_ref]
    with pytest.raises((TypeError, ValueError)):
        _normalizer()(value)


def test_duplicate_artifact_refs_rejected():
    value = valid_envelope(); value["artifact_refs"] = ["artifacts/a.png", "artifacts/a.png"]
    with pytest.raises((TypeError, ValueError)):
        _normalizer()(value)


@pytest.mark.parametrize("provider", [
    {"id": "bad id", "method": "geometry", "version": "1.0.0"},
    {"id": "builtin-deterministic", "method": "geo\x00metry", "version": "1.0.0"},
    {"id": "builtin-deterministic", "method": "geometry", "version": "latest"},
    {"id": "builtin-deterministic", "method": "geometry", "version": True},
])
def test_malformed_provider_identity_method_or_version_rejected(provider):
    value = valid_envelope(); value["provider"] = provider
    with pytest.raises((TypeError, ValueError)):
        _normalizer()(value)


def test_deep_cyclic_and_oversized_inputs_rejected_without_recursion_leak():
    normalize = _normalizer()
    deep = valid_envelope(); cursor = deep["metrics"]
    for _ in range(80): cursor["nested"] = {}; cursor = cursor["nested"]
    cyclic = valid_envelope(); cyclic["metrics"]["cycle"] = cyclic
    oversized = valid_envelope(); oversized["reasons"] = ["x" * 200_000]
    for value in (deep, cyclic, oversized):
        with pytest.raises((TypeError, ValueError)):
            normalize(value)


@pytest.mark.parametrize("expected_route", list(requests()))
def test_router_selects_exact_family_contract_route(expected_route):
    result = _router()(requests()[expected_route])
    assert result["route"] == expected_route
    assert result["family"] == requests()[expected_route]["family"]
    assert set(result) == ENVELOPE_KEYS


@pytest.mark.parametrize("route,foreign_key", [
    ("actor_motion", "tile_size"), ("effect_sequence", "gait"),
    ("tile_topology_repeat", "slice_margins"), ("ui_nine_slice_state", "placement"),
    ("object_placement_state", "effect_category"),
])
def test_router_rejects_cross_family_contract_pollution(route, foreign_key):
    request = requests()[route]; request["contract"][foreign_key] = {}
    with pytest.raises((TypeError, ValueError)):
        _router()(request)


@pytest.mark.parametrize("change", [
    {"family": "sprite", "subtype": "vehicle"},
    {"family": "effect", "subtype": "character"},
    {"family": "audio", "subtype": "sequence"},
    {"route": "generic_visual"},
])
def test_router_rejects_unsupported_subtype_family_or_caller_selected_route(change):
    request = requests()["actor_motion"]; request.update(change)
    with pytest.raises((TypeError, ValueError)):
        _router()(request)


@pytest.mark.parametrize("provider", [
    {"id": "unknown-provider", "method": "geometry", "version": "1.0.0"},
    {"id": "builtin-deterministic", "method": "nine-slice-state", "version": "1.0.0"},
    {"id": "builtin-deterministic", "method": "geometry", "version": "2.0.0"},
])
def test_router_rejects_unknown_or_route_mismatched_provider(provider):
    request = requests()["actor_motion"]; request["provider"] = provider
    with pytest.raises((TypeError, ValueError)):
        _router()(request)


def test_deterministic_pass_never_becomes_production_visual_pass_silently(tmp_path, monkeypatch):
    from PIL import Image
    artifact = tmp_path / "artifacts/actor/walk.png"
    artifact.parent.mkdir(parents=True)
    image = Image.new("RGBA", (16, 4), (255, 0, 0, 255))
    image.putpixel((4, 0), (0, 255, 0, 255))
    image.save(artifact)
    monkeypatch.setattr(server, "ROOT", tmp_path)
    result = _router()(requests()["actor_motion"])
    assert result["deterministic"]["status"] == "COMPLETE"
    assert result["deterministic"]["verdict"] == "PASS"
    assert result["visual"]["status"] in {"NOT_RUN", "UNAVAILABLE"}
    assert result["visual"]["verdict"] == "PARTIAL"
    assert result["verdict"] == "PARTIAL"
    assert "deterministic_only" in result["warnings"]
