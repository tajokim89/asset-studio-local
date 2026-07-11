"""I3 optional visual QA provider guard and merge tests."""
import copy
from PIL import Image
import pytest
import server
from test_family_qa_router import requests


def actor_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    request = requests()["actor_motion"]
    path = tmp_path / request["artifact_refs"][0]
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (16, 4), (0, 0, 0, 0))
    for index in range(4):
        image.putpixel((index * 4 + index % 3, index % 4), (20 + index, 30, 40, 255))
    image.save(path)
    return request


def approval():
    return {"approved": True, "scope": "actor_motion", "max_calls": 1}


def visual(verdict="PASS"):
    return {
        "status": "COMPLETE",
        "verdict": verdict,
        "reasons": [] if verdict == "PASS" else ["motion_rubric_failed"],
        "metrics": {"rubric_score": 0.9 if verdict == "PASS" else 0.2},
        "warnings": [],
    }


def test_visual_provider_requires_explicit_route_scoped_one_call_approval(tmp_path, monkeypatch):
    request = actor_artifact(tmp_path, monkeypatch)
    calls = []
    def provider(payload): calls.append(payload); return visual()
    out = server.route_family_qa(request, visual_provider=provider)
    assert calls == [] and out["visual"]["status"] == "NOT_RUN" and out["verdict"] == "PARTIAL"
    for bad in ({"approved": True, "scope": "effect_sequence", "max_calls": 1},
                {"approved": True, "scope": "actor_motion", "max_calls": 2}):
        with pytest.raises(ValueError):
            server.route_family_qa(request, visual_provider=provider, visual_approval=bad, visual_call_budget=1)
    assert calls == []


def test_approved_visual_provider_called_exactly_once_with_isolated_family_rubric(tmp_path, monkeypatch):
    request = actor_artifact(tmp_path, monkeypatch); calls = []
    def provider(payload): calls.append(copy.deepcopy(payload)); return visual()
    out = server.route_family_qa(request, visual_provider=provider, visual_approval=approval(), visual_call_budget=1)
    assert len(calls) == 1 and out["visual"]["verdict"] == "PASS" and out["verdict"] == "PASS"
    payload = calls[0]
    assert set(payload) == {"schema_version", "route", "family", "subtype", "rubric", "contract", "deterministic_metrics", "artifact_refs"}
    assert payload["route"] == "actor_motion"
    assert "actual opposite-limb alternation" in payload["rubric"]["criteria"]
    assert "labels alone are not evidence" in payload["rubric"]["criteria"]
    assert "tile_size" not in repr(payload) and "slice_margins" not in repr(payload)


def test_visual_fail_merges_and_deterministic_fail_cannot_be_overwritten(tmp_path, monkeypatch):
    request = actor_artifact(tmp_path, monkeypatch)
    failed = server.route_family_qa(request, visual_provider=lambda p: visual("FAIL"), visual_approval=approval(), visual_call_budget=1)
    assert failed["verdict"] == "FAIL" and "motion_rubric_failed" in failed["reasons"]
    path = tmp_path / request["artifact_refs"][0]
    Image.new("RGBA", (16, 4), (1, 1, 1, 255)).save(path)
    deterministic_fail = server.route_family_qa(request, visual_provider=lambda p: visual("PASS"), visual_approval=approval(), visual_call_budget=1)
    assert deterministic_fail["deterministic"]["verdict"] == "FAIL" and deterministic_fail["verdict"] == "FAIL"


@pytest.mark.parametrize("response", [
    {"status": "COMPLETE", "verdict": "PASS", "reasons": [], "metrics": {}, "warnings": [], "extra": 1},
    {"status": "COMPLETE", "verdict": "PASS", "reasons": [], "metrics": {"score": True}, "warnings": []},
])
def test_malformed_visual_response_becomes_unavailable_without_losing_deterministic(tmp_path, monkeypatch, response):
    request = actor_artifact(tmp_path, monkeypatch)
    out = server.route_family_qa(request, visual_provider=lambda p: response, visual_approval=approval(), visual_call_budget=1)
    assert out["deterministic"]["verdict"] == "PASS"
    assert out["visual"]["status"] == "UNAVAILABLE" and out["visual"]["verdict"] == "PARTIAL"
    assert out["verdict"] == "PARTIAL"


def test_provider_exception_is_single_call_unavailable(tmp_path, monkeypatch):
    request = actor_artifact(tmp_path, monkeypatch); calls = 0
    def provider(payload):
        nonlocal calls; calls += 1; raise TimeoutError("nope")
    out = server.route_family_qa(request, visual_provider=provider, visual_approval=approval(), visual_call_budget=1)
    assert calls == 1 and out["visual"]["status"] == "UNAVAILABLE" and out["deterministic"]["verdict"] == "PASS"
