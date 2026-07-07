from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import select_geometry_consistent_source_set


def test_phase21_regenerates_only_geometry_failed_directions_until_set_passes():
    calls = []

    def generate(direction, round_index):
        calls.append((direction, round_index))
        return f"{direction}-round-{round_index}".encode(), {"round": round_index}

    def validate(sources):
        # First full set fails only W. After W is regenerated in round 2, pass.
        if sources["W"] == b"W-round-1":
            return {"pass": False, "reason": "inconsistent_source_geometry", "failed_directions": ["W"]}
        return {"pass": True, "reason": "pass", "failed_directions": []}

    sources, qa = select_geometry_consistent_source_set(["S", "N", "W", "SW", "NW"], 3, generate, validate)

    assert sources["W"] == b"W-round-2"
    assert sources["S"] == b"S-round-1"
    assert calls == [("S", 1), ("N", 1), ("W", 1), ("SW", 1), ("NW", 1), ("W", 2)]
    assert qa["geometry_qa"]["pass"] is True
    assert qa["geometry_rounds"][0]["failed_directions"] == ["W"]


def test_phase21_fails_closed_when_geometry_never_passes():
    def generate(direction, round_index):
        return f"{direction}-round-{round_index}".encode(), {"round": round_index}

    def validate(sources):
        return {"pass": False, "reason": "inconsistent_source_geometry", "failed_directions": ["SW"]}

    try:
        select_geometry_consistent_source_set(["S", "N", "W", "SW", "NW"], 2, generate, validate)
    except RuntimeError as exc:
        assert "No geometry-consistent source set" in str(exc)
    else:
        raise AssertionError("geometry-invalid source sets must fail closed")
