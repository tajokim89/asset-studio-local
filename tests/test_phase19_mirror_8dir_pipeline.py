from io import BytesIO
from pathlib import Path

from PIL import Image

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import build_8dir_mirror_sheet_from_source_pngs


def _png(color, size=(24, 32)):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    for y in range(4, size[1] - 4):
        for x in range(4, size[0] - 4):
            img.putpixel((x, y), color)
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _image(raw):
    return Image.open(BytesIO(raw)).convert("RGBA")


def test_phase19_builds_8dir_from_five_left_sources_and_exact_flips():
    sources = {
        "S": _png((255, 0, 0, 255)),
        "N": _png((0, 255, 0, 255)),
        "W": _png((0, 0, 255, 255), size=(30, 32)),
        "SW": _png((255, 255, 0, 255), size=(28, 32)),
        "NW": _png((255, 0, 255, 255), size=(26, 32)),
    }

    out, qa = build_8dir_mirror_sheet_from_source_pngs(sources, cell_size=48, layout="row")
    sheet = _image(out)

    assert qa["method"] == "5-source+mirror"
    assert qa["source_directions"] == ["S", "N", "W", "SW", "NW"]
    assert qa["order"] == ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    assert qa["mirrored_pairs"] == {"NW": "NE", "W": "E", "SW": "SE"}
    assert sheet.size == (48 * 8, 48)
    assert qa["corner_alpha"] == [0, 0, 0, 0]

    cells = [sheet.crop((i * 48, 0, (i + 1) * 48, 48)) for i in range(8)]
    # NE/E/SE must be exact horizontal flips of NW/W/SW source cells.
    assert list(iter(cells[1].getdata())) == list(iter(cells[7].transpose(Image.Transpose.FLIP_LEFT_RIGHT).getdata()))
    assert list(iter(cells[2].getdata())) == list(iter(cells[6].transpose(Image.Transpose.FLIP_LEFT_RIGHT).getdata()))
    assert list(iter(cells[3].getdata())) == list(iter(cells[5].transpose(Image.Transpose.FLIP_LEFT_RIGHT).getdata()))


def test_phase19_requires_no_right_facing_source_keys():
    sources = {
        "S": _png((255, 0, 0, 255)),
        "N": _png((0, 255, 0, 255)),
        "W": _png((0, 0, 255, 255)),
        "E": _png((0, 0, 0, 255)),
        "SW": _png((255, 255, 0, 255)),
        "NW": _png((255, 0, 255, 255)),
    }

    try:
        build_8dir_mirror_sheet_from_source_pngs(sources, cell_size=48, layout="row")
    except ValueError as exc:
        assert "right-facing source" in str(exc)
    else:
        raise AssertionError("E/SE/NE source directions must be rejected")
