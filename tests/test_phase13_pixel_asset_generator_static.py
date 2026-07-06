from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_phase13_pixel_asset_generator_ui_exists():
    required = [
        "phase13-pixel-generator",
        "Pixel Asset Generator",
        "pixelAssetType",
        "pixelAnimationPreset",
        "pixelStylePreset",
        "pixelDirection",
        "pixelPalette",
        "pixelSubject",
        "buildPixelPrompt",
        "generatePixelAsset",
        "pixelResultSlots",
        "idle",
        "walking",
        "UI Panel",
    ]
    for token in required:
        assert token in INDEX


def test_phase13_pixel_prompt_builder_logic_exists():
    required = [
        "function buildPixelAssetPrompt",
        "function syncPixelAssetPrompt",
        "function recordPixelAssetResult",
        "pixel-art sprite sheet",
        "transparent background",
        "no text, no watermark",
        "idle animation frames",
        "walk cycle frames",
        "UI game asset",
        "background_mode: 'chroma_green'",
    ]
    for token in required:
        assert token in JS


def test_phase13_generation_routes_through_real_generate_button():
    assert "$('generatePixelAsset').onclick" in JS
    assert "$('generateBtn')?.click()" in JS
    assert "syncPixelAssetPrompt()" in JS
    assert "recordPixelAssetResult(url, data.model || 'generated')" in JS
