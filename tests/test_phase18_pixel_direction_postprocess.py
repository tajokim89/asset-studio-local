import io

from PIL import Image, ImageDraw

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from server import postprocess_pixel_generation_bytes


def _png_bytes(img: Image.Image) -> bytes:
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _sprite_sheet_fixture() -> bytes:
    img = Image.new("RGBA", (96, 12), (0, 255, 0, 255))
    draw = ImageDraw.Draw(img)
    # Eight separated direction candidates in canonical single-target order:
    # S, SW, W, NW, N, NE, E, SE. Encode each with a distinct red value so
    # tests can prove the selected crop came from the requested direction slot.
    for i in range(8):
        x0 = i * 12 + 2
        draw.rectangle([x0, 2, x0 + 7, 9], fill=(20 + i * 20, 10, 10, 255))
    return _png_bytes(img)


def test_single_target_sw_extracts_only_sw_candidate_and_removes_green():
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
    assert qa["direction_qa"]["target_direction"] == "SW"
    assert qa["direction_qa"]["selected_slot"] == 1
    assert img.size == (10, 10)
    assert all(not (p[1] > 220 and p[0] < 80 and p[2] < 80 and p[3] > 0) for p in pixels)
    assert opaque and opaque[0][0] == 40  # second slot, not the first/front slot
    assert qa["green_pixels"] == 0
    assert qa["corner_alpha"] == [0, 0, 0, 0]


def test_single_target_s_extracts_front_candidate_not_whole_sheet():
    out, qa = postprocess_pixel_generation_bytes(
        _sprite_sheet_fixture(),
        background_mode="chroma_green",
        direction_mode="single",
        target_direction="S",
        animation_mode="idle",
        chroma_mode="global",
    )

    img = Image.open(io.BytesIO(out)).convert("RGBA")
    opaque = [p for p in img.getdata() if p[3] > 0]

    assert qa["direction_qa"]["status"] == "pass"
    assert qa["direction_qa"]["selected_slot"] == 0
    assert img.size == (10, 10)
    assert opaque and opaque[0][0] == 20


def test_non_chroma_single_target_still_crops_to_selected_component():
    img = Image.new("RGBA", (48, 12), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for i in range(4):
        x0 = i * 12 + 2
        draw.rectangle([x0, 2, x0 + 7, 9], fill=(30 + i * 30, 20, 20, 255))

    out, qa = postprocess_pixel_generation_bytes(
        _png_bytes(img),
        background_mode="none",
        direction_mode="single",
        target_direction="W",
        animation_mode="idle",
        chroma_mode="global",
    )

    result = Image.open(io.BytesIO(out)).convert("RGBA")
    opaque = [p for p in result.getdata() if p[3] > 0]

    assert qa["direction_qa"]["status"] == "pass"
    assert qa["direction_qa"]["selected_slot"] == 2
    assert result.size == (10, 10)
    assert opaque and opaque[0][0] == 90


def test_generate_endpoints_are_wired_to_pixel_postprocess():
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    js = (ROOT / "src" / "main.js").read_text(encoding="utf-8")

    assert "postprocess_pixel_generation_bytes(" in server
    assert "src.read_bytes()" in server
    assert "postprocess_pixel_generation_bytes(raw" in server
    assert '"qa": qa' in server
    assert "data.qa" in js
    assert "direction_qa" in js


def test_single_direction_prompt_requests_canonical_extraction_sheet():
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    js = (ROOT / "src" / "main.js").read_text(encoding="utf-8")

    assert "internal extraction sheet" in js
    assert "S, SW, W, NW, N, NE, E, SE" in js
    assert "internal extraction sheet" in server
    assert "The app will crop and return only the requested target direction" in server
    assert "one horizontal row" in server
    assert "screen-left" in server
