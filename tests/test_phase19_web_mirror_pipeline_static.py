from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "server.py").read_text()
MAIN = (ROOT / "src" / "main.js").read_text()


def test_phase19_reference_8dir_route_uses_mirror_pipeline():
    required = [
        'direction_mode = str(data.get("direction_mode", "single"))',
        'if direction_mode == "8dir" and animation_mode == "idle"',
        'generate_reference_8dir_mirror_sheet',
        'build_8dir_mirror_sheet_from_source_pngs',
        '"method": f"reference-image-8dir-mirror+{qa.get(\'method\', \'postprocess\')}"',
    ]
    for token in required:
        assert token in SERVER


def test_phase19_frontend_keeps_8dir_request_on_reference_generate():
    required = [
        "direction_mode: directionMode",
        "reference_direction: referenceDirection",
        "target_direction: targetDirection",
        "'/api/generate-reference'",
    ]
    for token in required:
        assert token in MAIN
