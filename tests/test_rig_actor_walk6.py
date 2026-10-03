import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageDraw

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "rig_actor_walk6.py"
SPEC = importlib.util.spec_from_file_location("rig_actor_walk6", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
FRAME_COUNT = MODULE.FRAME_COUNT
render_walk6 = MODULE.render_walk6
save_package = MODULE.save_package


def actor_fixture() -> Image.Image:
    image = Image.new("RGBA", (128, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((42, 4, 86, 48), fill=(70, 70, 70, 255))
    draw.rectangle((34, 42, 94, 142), fill=(100, 60, 30, 255))
    draw.rectangle((15, 48, 40, 150), fill=(60, 60, 60, 255))
    draw.rectangle((88, 48, 113, 150), fill=(60, 60, 60, 255))
    draw.rectangle((38, 132, 62, 250), fill=(80, 50, 30, 255))
    draw.rectangle((66, 132, 90, 250), fill=(80, 50, 30, 255))
    return image


def test_render_walk6_has_exact_frame_contract():
    frames, rig = render_walk6(actor_fixture(), 192)
    assert len(frames) == FRAME_COUNT == 6
    assert all(frame.size == (192, 192) for frame in frames)
    assert all(frame.getchannel("A").getbbox() for frame in frames)
    assert rig.baseline == round(192 * .97)
    assert frames[0].tobytes() != frames[3].tobytes()


def test_save_package_exports_frames_sheet_gif_and_manifest(tmp_path: Path):
    frames, rig = render_walk6(actor_fixture(), 96)
    manifest = save_package(frames, rig, tmp_path, fps=6)
    assert manifest["frames"] == 6
    assert len(manifest["frame_paths"]) == 6
    assert Image.open(manifest["sheet"]).size == (96 * 6, 96)
    gif = Image.open(manifest["preview"])
    assert getattr(gif, "n_frames", 1) == 6
    assert (tmp_path / "walk6_manifest.json").is_file()
