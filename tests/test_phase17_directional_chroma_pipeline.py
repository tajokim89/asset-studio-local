import base64
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
SERVER = (ROOT / "server.py").read_text(encoding="utf-8")


def test_phase17_directional_character_controls_exist():
    for token in [
        'id="pixelDirectionMode"',
        'value="single" selected',
        'value="8dir"',
        'id="pixelTargetDirection"',
        'Target W/left',
        '8방향 Idle 생성',
        '8방향 Walk 생성',
        'id="pixelReferenceDirection"',
        'value="S"',
        'value="NW"',
        'id="pixelWalkFrames"',
        'id="pixelChromaMode"',
        'value="global"',
        'id="pixelQaSummary"',
    ]:
        assert token in INDEX


def test_phase17_directional_prompt_and_payload_are_explicit():
    for token in [
        "function directionLabelsForMode",
        "function directionLabel",
        "function buildDirectionalSpriteSheetContract",
        "Single target via one-direction generation",
        "Generate exactly one target direction",
        "target_direction",
        "W/left true side profile",
        "8-direction",
        "N, NE, E, SE, S, SW, W, NW",
        "idle -> stepA -> idle -> stepB",
        "reference_direction",
        "direction_mode",
        "animation_mode",
        "walk_frames",
        "chroma_mode",
        "runDirectionalPixelWorkflow",
        "runDirectionalPixelPack",
    ]:
        assert token in JS


def test_phase17_pixel_generate_button_calls_generation_without_legacy_hidden_button():
    handler = JS.split("if ($('generatePixelAsset'))", 1)[1].split("if ($('runPixelWorkflow'))", 1)[0]
    assert "generateAiAsset().catch" in handler
    assert "$('generateBtn')?.click()" not in handler
    assert "if ($('generateBtn')) $('generateBtn').onclick" in JS
    assert "let prompt = ($('aiPrompt')?.value || '').trim();" in JS
    assert "if (!prompt) prompt = buildPixelAssetPrompt().trim();" in JS
    assert "const generateBtn = $('generateBtn') || $('generatePixelAsset');" in JS


def test_phase17_server_reference_prompt_includes_direction_contract():
    for token in [
        "direction_mode",
        "target_direction",
        "Generate exactly one target direction",
        "Do not generate a direction-candidate sheet",
        "screen-left",
        "reference_direction",
        "animation_mode",
        "walk_frames",
        "N, NE, E, SE, S, SW, W, NW",
        "row order must be",
        "column order must be",
    ]:
        assert token in SERVER


def test_global_chroma_key_removes_internal_green_holes(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("asset_server", ROOT / "server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    img = Image.new("RGBA", (7, 7), (0, 255, 0, 255))
    px = img.load()
    # Red ring with green hole at center. The hole is not connected to the border.
    for y in range(1, 6):
        for x in range(1, 6):
            px[x, y] = (180, 20, 20, 255)
    px[3, 3] = (0, 255, 0, 255)
    raw = io.BytesIO()
    img.save(raw, format="PNG")

    out = mod.remove_chroma_green_bytes(raw.getvalue(), tolerance=18, mode="global")
    cleaned = Image.open(io.BytesIO(out)).convert("RGBA")
    assert cleaned.getpixel((0, 0))[3] == 0
    assert cleaned.getpixel((3, 3))[3] == 0
    assert cleaned.getpixel((2, 2))[3] == 255
    assert mod.chroma_green_report(out)["green_pixels"] == 0
