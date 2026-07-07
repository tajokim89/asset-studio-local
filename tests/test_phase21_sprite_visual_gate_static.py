from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "server.py").read_text()


def test_phase21_pipeline_has_geometry_and_holistic_visual_sprite_set_gates():
    required = [
        "evaluate_sprite_source_geometry_quality",
        "sprite source geometry QA failed",
        "classify_sprite_sheet_consistency_with_codex_vision",
        "Sprite-set production QA contract",
        "SAME character rotated",
        "backpack, weapon, hat, armor, colors, or silhouette change",
        "equipment/backpack is clipped/cropped",
        "sprite-set visual QA failed; fail closed",
        "sprite_set_visual_qa",
    ]
    for token in required:
        assert token in SERVER
