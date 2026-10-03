from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "generated" / "3d-actions" / "chairman-chibi-stomp-8dir-v2"
DIRECTIONS = ("S", "SW", "W", "NW", "N", "NE", "E", "SE")


def frames(direction: str):
    paths = sorted((OUTPUT / direction / "frames").glob("walk_*.png"))
    return [Image.open(path).convert("RGBA") for path in paths]


def test_v2_has_eight_96px_directions_with_four_frames():
    for direction in DIRECTIONS:
        images = frames(direction)
        assert len(images) == 4
        assert all(image.size == (96, 96) for image in images)
        assert all(image.getchannel("A").getextrema() == (0, 255) for image in images)
        assert ImageChops.difference(images[1], images[3]).getbbox() is None
        assert ImageChops.difference(images[0], images[2]).getbbox() is not None
        assert (OUTPUT / direction / "walk_96x96_atlas.png").is_file()
        assert (OUTPUT / direction / "walk_preview.gif").is_file()


def test_v2_east_views_are_exact_mirrors():
    for east, west in (("NE", "NW"), ("E", "W"), ("SE", "SW")):
        for east_frame, west_frame in zip(frames(east), frames(west), strict=True):
            expected = west_frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            assert ImageChops.difference(east_frame, expected).getbbox() is None


def test_v2_uses_one_shared_64_color_palette():
    atlas = Image.open(OUTPUT / "walk_8dir_96x96_atlas.png").convert("RGBA")
    assert atlas.size == (384, 768)
    colors = {pixel[:3] for pixel in atlas.get_flattened_data() if pixel[3]}
    assert len(colors) <= 64


def test_v2_preview_and_user_identity_anchor_exist():
    assert (OUTPUT / "direction_masters.png").is_file()
    assert (OUTPUT / "walk_8dir_preview.gif").is_file()
    assert (OUTPUT / "source_masters" / "S_reference_green.png").is_file()


def test_asset_studio_loads_v2_sample():
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    ui = (ROOT / "src" / "pixel-pipeline.js").read_text(encoding="utf-8")
    assert "96×96" in index
    assert "chairman-chibi-stomp-8dir-v2" in ui
    assert "walk_96x96_atlas.png" in ui
    assert "paletteColors: 64" in ui
