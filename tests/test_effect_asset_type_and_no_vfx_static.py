from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")

from server import build_prompt, build_reference_sprite_prompt  # noqa: E402


def test_effect_asset_type_exists_in_ui_and_frontend_contracts():
    assert '<option value="effect">Effect</option>' in INDEX
    assert "PIXEL_EFFECT_ASSET_TYPES" in JS
    assert "isPixelEffectAssetType" in JS
    assert "선택 이미지에 맞는 이펙트 생성" in JS
    assert "effect-only game VFX asset" in JS
    assert "No baked VFX" in JS
    assert "asset_type: type" in JS
    assert "preset: type === 'effect' ? 'effect' : 'pixel'" in JS


def test_non_effect_generation_prompts_exclude_baked_vfx():
    prompt = build_prompt("small cleanup knight", "pixel", "chroma_green")
    for token in ["No baked VFX rule", "slash arcs", "hit sparks", "magic glows", "effects are generated separately"]:
        assert token in prompt
    assert "Effect-only contract" not in prompt


def test_effect_generation_prompts_are_effect_only_and_allow_vfx():
    prompt = build_prompt("purple hit spark", "effect", "chroma_green")
    assert "Effect-only contract" in prompt
    assert "No baked VFX rule" not in prompt
    for token in ["slash", "impact spark", "magic burst", "No character", "No character".lower()]:
        assert token.lower() in prompt.lower()


def test_reference_effect_prompt_uses_selected_layer_as_context_not_identity_copy():
    prompt = build_reference_sprite_prompt(
        "small poison puff matching this slime",
        asset_type="effect",
    )
    assert "effect-only" in prompt
    assert "fit/context" in prompt
    assert "Do not redraw, include, copy, cover, or modify" in prompt
    assert "No caster, no target" in prompt
    assert "Frame count" not in prompt
