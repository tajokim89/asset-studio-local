from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import select_valid_direction_candidate


def test_phase20_retries_until_direction_validator_accepts_candidate():
    generated = []

    def generate(direction, attempt):
        value = f"{direction}-candidate-{attempt}".encode()
        generated.append((direction, attempt))
        return value, {"attempt": attempt}

    def validate(raw, direction):
        attempt = int(raw.decode().rsplit("-", 1)[1])
        return {"pass": attempt == 3, "observed": direction if attempt == 3 else "E", "reason": "test"}

    raw, qa = select_valid_direction_candidate("W", 3, generate, validate)

    assert raw == b"W-candidate-3"
    assert generated == [("W", 1), ("W", 2), ("W", 3)]
    assert qa["accepted_attempt"] == 3
    assert qa["visual_direction_qa"]["pass"] is True
    assert len(qa["attempts"]) == 3


def test_phase20_fails_closed_when_no_candidate_passes_direction_validation():
    def generate(direction, attempt):
        return f"{direction}-bad-{attempt}".encode(), {"attempt": attempt}

    def validate(raw, direction):
        return {"pass": False, "observed": "E", "reason": "wrong side"}

    try:
        select_valid_direction_candidate("SW", 2, generate, validate)
    except RuntimeError as exc:
        assert "No direction-valid candidate" in str(exc)
    else:
        raise AssertionError("direction-invalid source candidates must not be accepted")
