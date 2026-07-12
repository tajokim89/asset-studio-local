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
    expected = {
        "idle", "walk", "run", "attack", "ranged_attack", "cast", "block",
        "dodge", "jump", "hurt", "death", "interact", "pickup",
    }
    assert set(SPRITE_ACTION_MATRIX) == expected
    assert "hit" not in SPRITE_ACTION_MATRIX
    assert SPRITE_ACTION_MATRIX["idle"]["frames"] == 4
    assert SPRITE_ACTION_MATRIX["hurt"]["columns"] == ["neutral", "impact", "recoil", "recovery"]
    assert SPRITE_ACTION_MATRIX["jump"]["columns"] == ["ready", "crouch", "takeoff", "apex", "descent", "landing"]
    assert SPRITE_ACTION_MATRIX["cast"]["columns"] == ["ready", "gather", "charge", "release", "follow-through", "recovery"]
    assert SPRITE_ACTION_MATRIX["death"]["columns"][-1] == "dead-still"
    for action in expected:
        spec = SPRITE_ACTION_MATRIX[action]
        assert spec["frames"] == len(spec["columns"])
        assert spec["contract"]
        assert spec["acceptance"]


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
    assert "Column order must be exactly: ready, anticipation, wind-up, strike, impact, recovery" in attack
    assert "cell" in attack.lower()
    assert "chroma-key background" in attack
    for token in ["No VFX", "slash arcs", "hit sparks", "separate game assets"]:
        assert token in attack

    cast = build_reference_sprite_prompt("cleanup mage", animation_mode="cast4", frame_count=4)
    for token in ["ready", "charge", "release", "recovery", "Whitelist visual acceptance gate for cast", "PASS only if", "clearly communicates casting", "green spill", "halo", "fringe"]:
        assert token in cast
    assert "contained effect" not in cast
    assert "VFX must stay inside" not in cast

    hurt = build_reference_sprite_prompt("cleanup goblin", animation_mode="hit", frame_count=4)
    assert "Hurt action contract" in hurt
    assert "impact" in hurt and "recoil" in hurt and "recovery" in hurt


def test_phase25_action_visual_qa_uses_whitelist_acceptance_for_every_actor_action():
    actions = list(SPRITE_ACTION_MATRIX)
    for action in actions:
        gate = sprite_action_acceptance_contract(action)
        assert f"Whitelist visual acceptance gate for {action}" in gate
        assert "PASS only if" in gate
        assert "mark FAIL" in gate
        assert SPRITE_ACTION_MATRIX[action]["acceptance"] in gate

    expectations = {
        "idle4": ["stable actor breathing in place", "closing frame returns cleanly"],
        "walk6": ["continuous walking", "left and right support phases", "no skating"],
        "attack4": ["complete attack", "weapon, hands, body"],
        "jump4": ["real vertical pose change", "contained landing"],
        "cast4": ["clearly communicates casting", "baked particles"],
        "hurt4": ["hit reaction", "through the recoil"],
        "death4": ["continuous death", "final frame never returns to standing"],
        "dodge": ["Reads as a dodge", "without camera motion"],
        "pickup": ["picking up an item", "coherent crouch and rise"],
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
        "Frame count: exactly 6",
        "left-contact, left-down, left-passing, right-contact, right-down, right-passing",
        "alternating support feet",
        "fixed root and contact baseline",
        "continuous walking",
        "no skating, hopping, repeated same-side step, or root drift",
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
        "complete full-frame pose",
        "cutting, pasting, sliding, warping",
        "left-contact, left-down, left-passing, right-contact, right-down, right-passing",
        "Six-phase in-place walk cycle",
        "alternating support feet",
    ]:
        assert token in sprite_prompt


def test_phase25_frontend_locks_preset_default_frames_and_payload_keys():
    for token in [
        "actorOutputProfileState",
        "loadActorOutputProfile",
        "validateActorOutputProfile",
        "actorActionRecipe",
        "output_profile_id: actorOutputProfileState.profile.id",
        "frame_count: action.frame_count",
        "fps: action.fps",
        "loop: action.loop",
        "beats: [...action.beats]",
    ]:
        assert token in JS


def test_selected_reference_request_uses_the_same_profile_contract_as_new_generation():
    selected_reference_block = JS.split("async function generateFrontIdleFromSelected()", 1)[1].split("async function runPixelWorkflow()", 1)[0]
    assert "const requestPayload = buildAssetGenerationPayload" in selected_reference_block
    assert "animation_mode: spec.key" not in selected_reference_block
    assert "frame_count: spec.frames" not in selected_reference_block
    assert "asset_type: type" not in selected_reference_block


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
