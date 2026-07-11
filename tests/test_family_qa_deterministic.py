"""I2 adversarial deterministic family-QA acceptance tests."""
import copy
from datetime import datetime, timezone

import pytest
from PIL import Image

import server
from test_family_qa_router import requests, valid_envelope


def _png(root, ref, size, alpha=255):
    path = root / ref
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (40, 80, 120, alpha)).save(path)


def test_missing_and_remote_artifacts_never_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    missing = server.route_family_qa(requests()["actor_motion"])
    assert missing["deterministic"]["verdict"] == missing["verdict"] == "FAIL"
    assert any("artifact_missing" in reason for reason in missing["deterministic"]["reasons"])
    remote = requests()["actor_motion"]
    remote["artifact_refs"] = ["https://example.invalid/walk.png"]
    out = server.route_family_qa(remote)
    assert out["deterministic"]["status"] == "UNAVAILABLE"
    assert out["deterministic"]["verdict"] == out["verdict"] == "PARTIAL"


@pytest.mark.parametrize("route,key,bad", [
    ("actor_motion", "frame_count", 0),
    ("actor_motion", "direction_mode", "12dir"),
    ("effect_sequence", "fps", -1),
    ("effect_sequence", "frame_count", 5),
    ("tile_topology_repeat", "rows", 0),
    ("tile_topology_repeat", "topology", "unknown"),
    ("ui_nine_slice_state", "states", "normal"),
    ("ui_nine_slice_state", "sizing_mode", "fluid"),
    ("object_placement_state", "states", {}),
])
def test_malformed_family_contracts_are_strictly_rejected(route, key, bad):
    req = requests()[route]
    req["contract"][key] = bad
    with pytest.raises((TypeError, ValueError)):
        server.route_family_qa(req)


def test_effect_capacity_and_ui_bounds_and_object_normalized_points_rejected():
    effect = requests()["effect_sequence"]
    effect["contract"]["frame_count"] = 5
    with pytest.raises(ValueError): server.route_family_qa(effect)
    ui = requests()["ui_nine_slice_state"]
    ui["contract"]["slice_margins"]["left"] = 90
    with pytest.raises(ValueError): server.route_family_qa(ui)
    obj = requests()["object_placement_state"]
    obj["contract"]["placement"]["pivot"]["x"] = 1.1
    with pytest.raises(ValueError): server.route_family_qa(obj)


def test_png_geometry_alpha_and_adjacent_metadata_are_inspected(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    req = requests()["ui_nine_slice_state"]
    _png(tmp_path, req["artifact_refs"][0], (95, 32))
    out = server.route_family_qa(req)
    assert out["deterministic"]["verdict"] == "FAIL"
    assert "ui_source_geometry_mismatch" in out["deterministic"]["reasons"]
    _png(tmp_path, req["artifact_refs"][0], (96, 32), alpha=0)
    out = server.route_family_qa(req)
    assert out["deterministic"]["metrics"]["alpha_coverage"] == 0
    assert any(reason.startswith("alpha_empty") for reason in out["deterministic"]["reasons"])


def test_result_digest_covers_contract_refs_provider_and_timestamp_is_real(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    first_req = requests()["actor_motion"]
    _png(tmp_path, first_req["artifact_refs"][0], (16, 4))
    first = server.route_family_qa(first_req)
    second_req = copy.deepcopy(first_req); second_req["contract"]["equipment"] = {"weapon": "sword"}
    second = server.route_family_qa(second_req)
    assert first["result_id"] != second["result_id"]
    stamp = datetime.fromisoformat(first["timestamp"].replace("Z", "+00:00"))
    assert abs((datetime.now(timezone.utc) - stamp).total_seconds()) < 10


def test_percent_decoded_traversal_and_inconsistent_envelopes_rejected():
    value = valid_envelope(); value["artifact_refs"] = ["artifacts/%2e%2e/secret.png"]
    with pytest.raises(ValueError): server.normalize_family_qa_verdict(value)
    value = valid_envelope(); value["verdict"] = "PASS"
    with pytest.raises(ValueError): server.normalize_family_qa_verdict(value)
    value = valid_envelope(); value["visual"]["verdict"] = "PASS"
    with pytest.raises(ValueError): server.normalize_family_qa_verdict(value)
    value = valid_envelope(); value["route"] = "effect_sequence"
    with pytest.raises(ValueError): server.normalize_family_qa_verdict(value)
