from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "generated" / "3d-actions" / "chairman-chibi-stomp-3trials"


def test_chibi_stomp_outputs_three_four_frame_variants():
    variants = sorted(OUTPUT.glob("trial_*"))
    assert [variant.name for variant in variants] == [
        "trial_1_soft",
        "trial_2_clear",
        "trial_3_bouncy",
    ]

    for variant in variants:
        frame_paths = sorted((variant / "frames").glob("walk_*.png"))
        assert len(frame_paths) == 4
        frames = [Image.open(path).convert("RGBA") for path in frame_paths]
        assert all(frame.size == (64, 64) for frame in frames)
        assert all(frame.getchannel("A").getextrema() == (0, 255) for frame in frames)
        assert ImageChops.difference(frames[1], frames[3]).getbbox() is None
        assert ImageChops.difference(frames[0], frames[2]).getbbox() is not None
        assert (variant / "walk_64x64_atlas.png").is_file()
        assert (variant / "walk_preview.gif").is_file()


def test_chibi_stomp_frames_share_a_small_palette():
    colors = set()
    for frame_path in OUTPUT.glob("trial_*/frames/walk_*.png"):
        image = Image.open(frame_path).convert("RGBA")
        colors.update(pixel[:3] for pixel in image.get_flattened_data() if pixel[3])
    assert len(colors) <= 32


def test_chibi_master_and_comparison_are_available():
    master = Image.open(OUTPUT / "chibi_master_64x64.png").convert("RGBA")
    assert master.size == (64, 64)
    assert master.getchannel("A").getbbox()
    assert (OUTPUT / "comparison_preview.gif").is_file()
    assert (OUTPUT / "comparison_sheet.png").is_file()
