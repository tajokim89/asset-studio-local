from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import (
    CANONICAL_8DIR_ORDER,
    MIRRORED_8DIR_SOURCE_DIRECTIONS,
    SPRITE_ACTION_MATRIX,
    build_static_direction_reference_prompt,
    build_sprite_action_prompt,
    sprite_action_matrix_for_ui,
)


def test_phase21_locks_source_direction_generation_to_left_side_plus_flips():
    assert CANONICAL_8DIR_ORDER == ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    assert MIRRORED_8DIR_SOURCE_DIRECTIONS == ["S", "N", "W", "SW", "NW"]
    prompt = build_static_direction_reference_prompt("armored cleanup worker", "W")
    assert "SOURCE DIRECTION W only" in prompt
    assert "Generate exactly one direction in this request" in prompt
    assert "true side profile facing screen-left" in prompt
    assert "Do not generate E, SE, or NE" in prompt
    assert "right-facing views are created by app-side horizontal flip" in prompt
    assert "Do not output an 8-direction sheet" in prompt


def test_phase21_action_matrix_defines_idle_walk_attack_hurt_death_contracts():
    assert list(SPRITE_ACTION_MATRIX) == [
        "idle", "walk", "run", "attack", "ranged_attack", "cast", "block",
        "dodge", "jump", "hurt", "death", "interact", "pickup",
    ]
    assert SPRITE_ACTION_MATRIX["idle"]["frames"] == 4
    assert SPRITE_ACTION_MATRIX["walk"]["frames"] == 4
    assert SPRITE_ACTION_MATRIX["attack"]["frames"] == 6
    assert SPRITE_ACTION_MATRIX["jump"]["frames"] == 6
    assert SPRITE_ACTION_MATRIX["cast"]["frames"] == 6
    assert SPRITE_ACTION_MATRIX["hurt"]["frames"] == 4
    assert SPRITE_ACTION_MATRIX["death"]["frames"] == 6
    assert SPRITE_ACTION_MATRIX["walk"]["columns"] == ["N", "L", "N", "R"]
    assert "opposite-foot steps" in SPRITE_ACTION_MATRIX["walk"]["acceptance"]
    assert "exact pixel copy of frame 1" in SPRITE_ACTION_MATRIX["walk"]["acceptance"]
    assert SPRITE_ACTION_MATRIX["dodge"]["fps"] == 14
    assert SPRITE_ACTION_MATRIX["death"]["terminal"] is True


def test_phase21_action_prompt_is_one_direction_action_strip_not_all_directions():
    prompt = build_sprite_action_prompt(
        "rusty sanitation knight",
        action="attack",
        direction="SW",
        source_reference_note="use the accepted SW static reference as frame 1 identity anchor",
    )
    assert "ACTION attack" in prompt
    assert "DIRECTION SW" in prompt
    assert "Generate exactly one direction in this request" in prompt
    assert "Do not output all 8 directions" in prompt
    assert "front-left three-quarter" in prompt
    assert "use the accepted SW static reference as frame 1 identity anchor" in prompt
    assert "Column order must be exactly: ready, anticipation, wind-up, strike, impact, recovery" in prompt
    assert "Keep all frames in evenly spaced cells on one horizontal row for this direction" in prompt
    assert "Global reference identity rule" in prompt
    assert "complete full-frame poses" in prompt
    assert "flat exact RGB(0,255,0) / #00FF00 chroma-key background" in prompt


def test_phase21_action_matrix_ui_payload_is_serializable_and_complete():
    payload = sprite_action_matrix_for_ui()
    assert payload["output_profile_id"] == "generic-pixel-actor-v1"
    assert payload["directions"] == CANONICAL_8DIR_ORDER
    assert payload["source_directions"] == MIRRORED_8DIR_SOURCE_DIRECTIONS
    assert payload["mirror_map"] == {"E": "W", "SE": "SW", "NE": "NW"}
    assert set(payload["actions"]) == set(SPRITE_ACTION_MATRIX)
