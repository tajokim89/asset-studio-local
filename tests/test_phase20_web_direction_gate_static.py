from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "server.py").read_text()


def test_phase20_web_pipeline_has_visual_direction_gate_and_retry_loop():
    required = [
        "def classify_direction_candidate_with_codex_vision",
        "Direction QA contract",
        "max_source_attempts",
        "select_valid_direction_candidate",
        "No direction-valid candidate",
        "visual_direction_qa",
        "fail closed",
    ]
    for token in required:
        assert token in SERVER
