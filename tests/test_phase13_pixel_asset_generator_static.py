from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_phase13_pixel_asset_generator_ui_exists():
    required = [
        "pixel-workflow-panel",
        "도트 에셋 생성",
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
        "walk",
        "Effect",
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
        "idle animation",
        "walk cycle",
        "UI game asset",
        "background_mode: 'chroma_green'",
    ]
    for token in required:
        assert token in JS


def test_phase13_generation_routes_through_real_generate_button():
    assert "$('generatePixelAsset').onclick" in JS
    assert "syncPixelAssetPrompt()" in JS
    assert "generateAiAsset().catch(err =>" in JS
    assert "const result = createAssetResult({ family:payload.asset_family, type:payload.asset_type, status:'succeeded'" in JS
    assert "assetResultStore.add(result)" in JS
    assert "assetResultStore.select(result.id)" in JS
