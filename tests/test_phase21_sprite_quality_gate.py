from pathlib import Path
import io
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import evaluate_sprite_source_geometry_quality


def _sprite_png(width, height, canvas=420):
    im = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    x0 = (canvas - width) // 2
    y0 = canvas - height - 8
    ImageDraw.Draw(im).rectangle([x0, y0, x0 + width - 1, y0 + height - 1], fill=(80, 120, 60, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_phase21_rejects_direction_set_when_one_source_is_much_smaller():
    sources = {
        "S": _sprite_png(364, 404),
        "N": _sprite_png(341, 404),
        "E": _sprite_png(404, 372),
        "SE": _sprite_png(234, 250),
        "NE": _sprite_png(404, 368),
    }

    qa = evaluate_sprite_source_geometry_quality(sources, min_height_ratio=0.82, min_area_ratio=0.55)

    assert qa["pass"] is False
    assert qa["reason"] == "inconsistent_source_geometry"
    assert "SE" in qa["failed_directions"]
    assert qa["stats"]["SE"]["height_ratio"] < 0.82


def test_phase21_accepts_direction_set_with_consistent_sprite_sizes():
    sources = {
        "S": _sprite_png(364, 404),
        "N": _sprite_png(350, 398),
        "E": _sprite_png(390, 382),
        "SE": _sprite_png(360, 386),
        "NE": _sprite_png(386, 380),
    }

    qa = evaluate_sprite_source_geometry_quality(sources, min_height_ratio=0.82, min_area_ratio=0.55)

    assert qa["pass"] is True
    assert qa["failed_directions"] == []
