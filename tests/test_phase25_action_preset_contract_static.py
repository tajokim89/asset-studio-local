from pathlib import Path
import io
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

JS = (ROOT / "src" / "main.js").read_text()
SERVER_TEXT = (ROOT / "server.py").read_text()

from server import (  # noqa: E402
    SPRITE_ACTION_MATRIX,
    SPRITE_ANIMATION_CORE_LOCKS,
    build_reference_sprite_prompt,
    build_sprite_action_prompt,
    chroma_green_report,
    normalize_animation_action,
    postprocess_pixel_generation_bytes,
    sprite_action_acceptance_contract,
    sprite_action_matrix_for_ui,
    sprite_animation_core_lock_contract,
)


def _png_bytes(img: Image.Image) -> bytes:
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def test_phase25_server_action_matrix_has_full_canonical_action_contracts():
    assert set(SPRITE_ACTION_MATRIX) >= {"idle", "walk", "attack", "jump", "cast", "hurt", "death"}
    assert "hit" not in SPRITE_ACTION_MATRIX
    assert SPRITE_ACTION_MATRIX["idle"]["frames"] == 4
    assert SPRITE_ACTION_MATRIX["hurt"]["columns"] == ["normal", "impact", "recoil", "recovery"]
    assert SPRITE_ACTION_MATRIX["jump"]["columns"] == ["crouch", "takeoff", "airborne", "landing"]
    assert SPRITE_ACTION_MATRIX["cast"]["columns"] == ["ready", "gather", "release", "recover"]
    assert SPRITE_ACTION_MATRIX["death"]["columns"][-1] in {"dead", "dead/still"}
    for action in ["idle", "walk", "attack", "jump", "cast", "hurt", "death"]:
        spec = SPRITE_ACTION_MATRIX[action]
        assert spec["frames"] == len(spec["columns"])
        assert spec["contract"]


def test_phase25_animation_action_normalization_aliases_payload_keys():
    expected = {
        "idle4": "idle",
        "walk4": "walk",
        "walk6": "walk",
        "attack4": "attack",
        "jump4": "jump",
        "cast4": "cast",
        "hurt4": "hurt",
        "hit": "hurt",
        "hit2": "hurt",
        "death4": "death",
        "death6": "death",
        "static1": "ui_static",
        "ui_static": "ui_static",
    }
    for raw, canonical in expected.items():
        assert normalize_animation_action(raw) == canonical


def test_phase25_core_animation_locks_are_non_negotiable_for_all_actor_actions():
    lock_names = [name for name, _rule in SPRITE_ANIMATION_CORE_LOCKS]
    assert lock_names == [
        "Reference Identity Lock",
        "Full-Frame Pose Lock",
        "Equipment Lock",
        "Direction Lock",
        "Root Lock",
        "Motion Read",
        "Loop Read",
        "Production Clean",
    ]
    core = sprite_animation_core_lock_contract()
    for token in [
        "Core animation locks",
        "one accepted reference identity globally",
        "real full-frame action poses",
        "stable root",
        "If any lock fails",
        "mark FAIL",
    ]:
        assert token in core

    ui = sprite_action_matrix_for_ui()
    assert [item["name"] for item in ui["core_locks"]] == lock_names
    assert ui["core_lock_contract"] == core

    for action in ["idle", "walk", "attack", "jump", "cast", "hurt", "death"]:
        gate = sprite_action_acceptance_contract(action)
        for lock in lock_names:
            assert lock in gate
        assert gate.index("Core animation locks") < gate.index(f"Whitelist visual acceptance gate for {action}")


def test_phase25_action_prompts_include_beat_sheets_and_cell_cleanup_contract():
    attack = build_sprite_action_prompt("cleanup knight", action="attack4", direction="SW")
    assert "ACTION attack" in attack
    assert "Column order must be exactly: ready, windup, strike, recover" in attack
    assert "cell" in attack.lower()
    assert "chroma-key background" in attack
    for token in ["No VFX", "slash arcs", "hit sparks", "separate game assets"]:
        assert token in attack

    cast = build_reference_sprite_prompt("cleanup mage", animation_mode="cast4", frame_count=4)
    for token in ["ready", "release", "recover", "Whitelist visual acceptance gate for cast", "PASS only if", "dominant readable action is not casting", "green spill", "halo", "fringe"]:
        assert token in cast
    assert "contained effect" not in cast
    assert "VFX must stay inside" not in cast

    hurt = build_reference_sprite_prompt("cleanup goblin", animation_mode="hit", frame_count=4)
    assert "Hurt action contract" in hurt
    assert "impact" in hurt and "recoil" in hurt and "recovery" in hurt


def test_phase25_action_visual_qa_uses_whitelist_acceptance_for_every_actor_action():
    actions = ["idle", "walk", "attack", "jump", "cast", "hurt", "death"]
    for action in actions:
        gate = sprite_action_acceptance_contract(action)
        assert f"Whitelist visual acceptance gate for {action}" in gate
        assert "PASS only if" in gate
        assert "dominant readable action is not" in gate
        assert "mark FAIL" in gate
        assert SPRITE_ACTION_MATRIX[action]["acceptance"] in gate

    expectations = {
        "idle4": ["idle/breathing loop", "planted feet", "not idle breathing"],
        "walk6": ["in-place crossover walk cycle for the referenced actor", "planted as stance/support", "root/pivot anchor", "only one limb/contact point moves", "legs never pass/cross through each other"],
        "attack4": ["ready stance", "wind-up", "not an attack"],
        "jump4": ["crouch anticipation", "airborne peak", "not jumping"],
        "cast4": ["release gesture", "not casting"],
        "hurt4": ["impact flinch", "recoil", "not a hurt reaction"],
        "death4": ["death/collapse", "dead/still", "not death/collapse"],
    }
    for mode, tokens in expectations.items():
        prompt = build_reference_sprite_prompt("cleanup worker", animation_mode=mode, frame_count=6 if mode == "walk6" else 4)
        for token in tokens:
            assert token in prompt

    for token in [
        "Core animation locks",
        "Reference Identity Lock",
        "Full-Frame Pose Lock",
        "Equipment Lock",
        "Direction Lock",
        "Root Lock",
        "Motion Read",
        "Loop Read",
        "Production Clean",
        "one accepted reference identity globally",
        "real full-frame action poses",
        "If any lock fails",
        "Whitelist visual acceptance gate for idle",
        "Whitelist visual acceptance gate for walk",
        "root/pivot anchor",
        "only one limb/contact point moves",
        "Whitelist visual acceptance gate for attack",
        "Whitelist visual acceptance gate for jump",
        "Whitelist visual acceptance gate for cast",
        "Whitelist visual acceptance gate for hurt",
        "Whitelist visual acceptance gate for death",
        "PASS only if",
        "mark FAIL",
    ]:
        assert token in JS


def test_phase25_action_prompts_include_generic_reference_identity_and_full_frame_pose_rules():
    walk = build_reference_sprite_prompt("generic actor", animation_mode="walk4", frame_count=4)
    for token in [
        "one accepted reference identity is the standard for the whole action set",
        "complete coherent full-frame poses",
        "do not merely upscale, crop, copy, cut/paste, or move isolated parts",
        "stance/support and swing roles",
        "Frame 1 and frame 3 must be visually near-identical neutral frames",
        "Frame 2: LEFT leg is the lifted swing leg",
        "RIGHT leg is the planted stance/support leg",
        "Frame 4: RIGHT leg is the lifted swing leg",
        "LEFT leg is the planted stance/support leg",
        "passes beside and visibly overlaps/crosses the planted support leg beneath the pelvis",
        "front/back depth ordering of the legs must reverse between frames 2 and 4",
        "For S/front-facing: character LEFT = screen-right and character RIGHT = screen-left",
        "frame 2 lifted swing boot must be on screen-right; frame 4 lifted swing boot must be on screen-left",
        "pelvis/root center at exactly 50% of each cell width",
        "do not move only one limb/contact point",
    ]:
        assert token in walk
    assert "left/support foot step" not in walk
    assert "right/opposite-support foot step" not in walk
    for forbidden in [
        "same hooded cleaner",
        "brass round goggles",
        "dark robe",
        "broom/tool",
        "SE / screen-right-down",
    ]:
        assert forbidden not in walk

    sprite_prompt = build_sprite_action_prompt("generic actor", action="walk4", direction="SW")
    for token in [
        "Global reference identity rule",
        "whole action set",
        "complete full-frame poses",
        "cutting, pasting, sliding, warping",
        "frame 1 neutral transition stance",
        "frame 3 the same neutral transition stance again",
        "Frame 2: LEFT leg is the lifted swing leg",
        "Frame 4: RIGHT leg is the lifted swing leg",
        "opposite stance/support legs",
        "one limb/contact point",
    ]:
        assert token in sprite_prompt


def test_phase25_frontend_locks_preset_default_frames_and_payload_keys():
    assert "const PIXEL_ANIMATION_PRESET_DEFAULT_FRAMES" in JS
    for token in ["walk6: 6", "idle: 4", "attack: 4", "jump: 4", "cast: 4", "hurt: 4", "death: 4"]:
        assert token in JS
    assert "const frames = pixelPresetFrameCount(preset);" in JS
    assert "key: preset === 'walk6' ? 'walk6'" in JS
    assert "actionFrameBeats" in JS
    assert "neutral crossover/passing stance reused" in JS
    assert "neutral-left-cross-neutral-right-cross" in JS
    assert "LEFT leg swing-cross" in JS
    assert "RIGHT leg swing-cross" in JS
    assert "character LEFT = screen-right" in JS
    assert "frame 2 swing boot on screen-right" in JS
    assert "frame 4 swing boot on screen-left" in JS
    assert "pelvis/root center at exactly 50% of each cell width" in JS
    for token in ["ready pose", "wind-up", "clean body/weapon strike pose", "airborne peak", "release gesture", "impact flinch", "dead/still"]:
        assert token in JS


def test_walk4_selected_reference_prompt_has_explicit_cross_through_roles_without_full_gait_conflicts():
    walk4_block = JS.split("walk4: {", 1)[1].split("walk6: {", 1)[0]
    assert "neutral crossover -> LEFT leg swing-cross -> same neutral crossover -> RIGHT leg swing-cross" in walk4_block
    assert "swing foot travels from behind the planted support leg, passes beside/overlaps it beneath the pelvis, and emerges ahead" in walk4_block
    assert "left/support step" not in walk4_block
    assert "right/opposite-support step" not in walk4_block
    assert "connected passing beats" not in walk4_block

    selected_reference_block = JS.split("async function generateFrontIdleFromSelected()", 1)[1].split("async function runPixelWorkflow()", 1)[0]
    assert "duplicate frames" not in selected_reference_block
    assert "same swing foot repeated in both crossing frames" in selected_reference_block
    assert "same side boot enlarged/lifted in both crossing frames" in selected_reference_block
    assert "legs never pass/cross through each other" in selected_reference_block
    assert "progressive left/right root drift" in selected_reference_block
    assert "four unrelated walk poses" in selected_reference_block


def test_phase25_cleanup_removes_dark_cell_borders_and_reports_residue():
    img = Image.new("RGBA", (24, 8), (0, 255, 0, 255))
    px = img.load()
    # Simulate bad generated sheet residue: dark green/black-ish cell boxes/gutters.
    for x in range(24):
        px[x, 0] = (0, 21, 10, 255)
        px[x, 7] = (0, 21, 10, 255)
    for y in range(8):
        px[0, y] = (0, 21, 10, 255)
        px[7, y] = (0, 21, 10, 255)
        px[8, y] = (0, 21, 10, 255)
        px[15, y] = (0, 21, 10, 255)
        px[16, y] = (0, 21, 10, 255)
        px[23, y] = (0, 21, 10, 255)
    # Sprite pixels with dark outline and colored core must survive.
    for x in range(2, 6):
        for y in range(2, 6):
            px[x, y] = (80, 60, 45, 255)
    px[2, 2] = (12, 10, 8, 255)
    px[5, 5] = (12, 10, 8, 255)

    out, qa = postprocess_pixel_generation_bytes(
        _png_bytes(img),
        background_mode="chroma_green",
        direction_mode="single",
        target_direction="S",
        animation_mode="walk4",
        chroma_mode="global",
    )
    cleaned = Image.open(io.BytesIO(out)).convert("RGBA")
    cleaned_px = cleaned.load()
    assert cleaned_px[0, 0][3] == 0
    assert cleaned_px[8, 4][3] == 0
    assert cleaned_px[16, 4][3] == 0
    assert cleaned_px[3, 3][3] == 255
    report = chroma_green_report(out)
    assert report["green_pixels"] == 0
    assert qa["cleanup_qa"]["pass"] is True
    assert qa["cleanup_qa"]["residual_dark_border_pixels"] == 0
