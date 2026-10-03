from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "generated" / "3d-actions" / "chairman-chibi-stomp-8dir-v1"
DIRECTIONS = ("S", "SW", "W", "NW", "N", "NE", "E", "SE")


def load_frames(direction: str):
    paths = sorted((OUTPUT / direction / "frames").glob("walk_*.png"))
    return [Image.open(path).convert("RGBA") for path in paths]


def test_chibi_stomp_has_eight_directions_and_four_frames_each():
    for direction in DIRECTIONS:
        frames = load_frames(direction)
        assert len(frames) == 4
        assert all(frame.size == (64, 64) for frame in frames)
        assert all(frame.getchannel("A").getextrema() == (0, 255) for frame in frames)
        assert ImageChops.difference(frames[1], frames[3]).getbbox() is None
        assert ImageChops.difference(frames[0], frames[2]).getbbox() is not None
        assert (OUTPUT / direction / "walk_64x64_atlas.png").is_file()
        assert (OUTPUT / direction / "walk_preview.gif").is_file()


def test_chibi_stomp_east_directions_are_exact_mirrors():
    for east, west in (("NE", "NW"), ("E", "W"), ("SE", "SW")):
        for east_frame, west_frame in zip(load_frames(east), load_frames(west), strict=True):
            mirrored = west_frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            assert ImageChops.difference(east_frame, mirrored).getbbox() is None


def test_chibi_stomp_uses_one_shared_32_color_palette():
    atlas = Image.open(OUTPUT / "walk_8dir_64x64_atlas.png").convert("RGBA")
    assert atlas.size == (256, 512)
    colors = {pixel[:3] for pixel in atlas.get_flattened_data() if pixel[3]}
    assert len(colors) <= 32


def test_chibi_stomp_preview_assets_exist():
    assert (OUTPUT / "walk_8dir_preview.gif").is_file()
    assert (OUTPUT / "direction_masters.png").is_file()


def test_asset_studio_exposes_chibi_stomp_sample():
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    ui = (ROOT / "src" / "pixel-pipeline.js").read_text(encoding="utf-8")
    assert "청년 2등신 발 구르기 8방향 열기" in index
    assert "chairman-chibi-stomp-8dir-v2" in ui
    assert "useChibiStomp8DirSample" in ui
    assert "artifact.frameCount || 8" in ui
