from __future__ import annotations

import json
import re
from pathlib import Path

import server


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
PROFILE = json.loads((ROOT / "profiles" / "generic-pixel-actor-v1.json").read_text(encoding="utf-8"))


def _actor_payload() -> dict:
    return {
        "asset_family": "sprite",
        "asset_type": "character",
        "prompt": "one standing dungeon worker",
        "sprite": {
            "output_profile_id": "generic-pixel-actor-v1",
            "animation_mode": "static",
            "direction_mode": "single",
            "target_direction": "S",
            "reference_direction": "AUTO",
            "frame_count": 99,
            "walk_frames": 99,
            "chroma_mode": "global",
        },
    }


def test_actor_profile_exposes_a_true_one_frame_static_recipe():
    static = next(action for action in PROFILE["actions"] if action["id"] == "static")
    assert static["frame_count"] == 1
    assert static["beats"] == ["single-pose"]
    assert static["sheet_layout"]["columns"] == 1
    assert static["sheet_layout"]["frame_order"] == [0]


def test_server_normalizes_static_actor_to_exactly_one_frame():
    normalized = server.normalize_asset_generation_payload(_actor_payload())["sprite"]
    assert normalized["animation_mode"] == "static"
    assert normalized["direction_mode"] == "single"
    assert normalized["frame_count"] == 1
    assert normalized["walk_frames"] == 1


def test_server_preserves_8dir_for_one_static_pose_per_direction():
    payload = _actor_payload()
    payload["sprite"]["direction_mode"] = "8dir"
    normalized = server.normalize_asset_generation_payload(payload)["sprite"]
    assert normalized["animation_mode"] == "static"
    assert normalized["direction_mode"] == "8dir"
    assert normalized["frame_count"] == 1
    assert normalized["walk_frames"] == 1


def test_ui_names_single_image_modes_explicitly_for_actor_and_effect():
    assert "단일 이미지 (1장)" in HTML
    assert re.search(r"value=\"static\"[^>]*>단일 이미지 \(1장\)", HTML)
    assert "action.id === 'static' ? '단일 이미지 (1장)'" in JS


def test_single_frame_ui_keeps_direction_mode_but_hides_frame_controls():
    assert "function syncSingleFrameSpriteUi" in JS
    body = JS.split("function syncSingleFrameSpriteUi", 1)[1].split("\n}", 1)[0]
    assert "$('pixelDirectionMode').hidden = actorStatic" not in body
    assert "$('pixelDirectionMode').value = 'single'" not in body
    assert "pixelFrameControls" in body
    for control_id in ("effectLoop", "effectFrameCount", "effectFps", "effectRows", "effectColumns", "effectGap"):
        assert control_id in body


def test_static_actor_prompt_supports_one_pose_in_each_8dir_row():
    for token in (
        "8-direction static character sheet",
        "one pose per direction",
        "N, NE, E, SE, S, SW, W, NW",
        "5-source+mirror",
    ):
        assert token in JS or token in Path(server.__file__).read_text(encoding="utf-8")


def test_reference_route_uses_mirror_pipeline_for_static_8dir():
    source = Path(server.__file__).read_text(encoding="utf-8")
    assert 'animation_mode in {"idle", "static"}' in source
    assert "animation_mode=animation_mode" in source


def test_new_static_8dir_generation_reuses_base_s_as_a_seed_then_builds_mirrors():
    source = Path(server.__file__).read_text(encoding="utf-8")
    assert 'direction_mode == "8dir" and animation_mode == "static"' in source
    assert 'initial_sources={"S": base_static}' in source
    assert "initial_sources=initial_sources" in source
