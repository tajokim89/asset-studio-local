import io

from PIL import Image, ImageDraw

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from server import build_reference_sprite_prompt, postprocess_pixel_generation_bytes


def _png_bytes(img: Image.Image) -> bytes:
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _sprite_sheet_fixture() -> bytes:
    img = Image.new("RGBA", (96, 12), (0, 255, 0, 255))
    draw = ImageDraw.Draw(img)
    # Old Phase 17 fixture: multiple direction candidates in one row.
    # New contract must NOT crop a target slot from this. It should preserve
    # the whole row so visual QA can reject the model for disobeying one-direction-only.
    for i in range(8):
        x0 = i * 12 + 2
        draw.rectangle([x0, 2, x0 + 7, 9], fill=(20 + i * 20, 10, 10, 255))
    return _png_bytes(img)


def test_single_target_postprocess_does_not_crop_from_internal_direction_sheet_anymore():
    out, qa = postprocess_pixel_generation_bytes(
        _sprite_sheet_fixture(),
        background_mode="chroma_green",
        direction_mode="single",
        target_direction="SW",
        animation_mode="idle",
        chroma_mode="global",
    )

    img = Image.open(io.BytesIO(out)).convert("RGBA")
    pixels = list(img.getdata())
    opaque = [p for p in pixels if p[3] > 0]

    assert qa["direction_qa"]["status"] == "pass"
    assert qa["direction_qa"]["reason"] == "single_direction_trim"
    assert qa["direction_qa"]["target_direction"] == "SW"
    assert "selected_slot" not in qa["direction_qa"]
    assert img.size == (96, 12)
    assert len({p[0] for p in opaque}) == 8
    assert all(not (p[1] > 220 and p[0] < 80 and p[2] < 80 and p[3] > 0) for p in pixels)
    assert qa["green_pixels"] == 0


def test_single_target_single_sprite_is_trimmed_without_slot_selection():
    img = Image.new("RGBA", (48, 24), (0, 255, 0, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 6, 27, 17], fill=(90, 20, 20, 255))

    out, qa = postprocess_pixel_generation_bytes(
        _png_bytes(img),
        background_mode="chroma_green",
        direction_mode="single",
        target_direction="W",
        animation_mode="idle",
        chroma_mode="global",
    )

    result = Image.open(io.BytesIO(out)).convert("RGBA")
    opaque = [p for p in result.getdata() if p[3] > 0]

    assert qa["direction_qa"]["status"] == "pass"
    assert qa["direction_qa"]["reason"] == "single_direction_trim"
    assert "selected_slot" not in qa["direction_qa"]
    assert result.size == (10, 14)
    assert opaque and opaque[0][0] == 90
    assert qa["corner_alpha"] == [0, 0, 0, 0]


def test_generate_endpoints_are_wired_to_pixel_postprocess():
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    js = (ROOT / "src" / "main.js").read_text(encoding="utf-8")

    assert "postprocess_pixel_generation_bytes(" in server
    assert "src.read_bytes()" in server
    assert "postprocess_pixel_generation_bytes(raw" in server
    assert '"qa": qa' in server
    assert "data.qa" in js
    assert "direction_qa" in js


def test_single_direction_prompt_requests_exactly_one_direction_not_extraction_sheet():
    server_prompt = build_reference_sprite_prompt(
        "cleanup worker",
        direction_mode="single",
        reference_direction="S",
        target_direction="W",
        animation_mode="idle",
    )
    js = (ROOT / "src" / "main.js").read_text(encoding="utf-8")

    assert "Generate exactly one target direction" in server_prompt
    assert "target_direction=W" in server_prompt
    assert "Do not generate a direction-candidate sheet" in server_prompt
    assert "Do not output all 8 directions" in server_prompt
    assert "one horizontal row of exactly 4 animation frames" in server_prompt
    assert "not a row/stack" not in server_prompt
    assert "Single target via one-direction generation" in js
    assert "Generate exactly one target direction" in js
    assert "internal extraction sheet" not in server_prompt
