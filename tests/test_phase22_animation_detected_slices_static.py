from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_animation_preview_uses_detected_or_grid_slices_not_stale_grid_only():
    assert "function currentAnimationSpriteSlices" in JS
    assert "if (spriteSlices.length) return spriteSlices.slice(0, frameCount);" in JS
    assert "const frames = currentAnimationSpriteSlices(frameCount);" in JS
    assert "currentGridSpriteSlices().slice(0, frameCount)" not in JS


def test_animation_preview_has_empty_frame_guard():
    assert "프레임 조각 없음" in JS
    assert "if (!frames.length) throw new Error" in JS
