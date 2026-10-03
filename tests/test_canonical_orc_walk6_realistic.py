import importlib.util
import sys
from pathlib import Path

from PIL import Image


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "canonical_orc_walk6_realistic.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("canonical_orc_walk6_realistic", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_realistic_texture_rig_exports_six_frames(tmp_path: Path):
    source = Image.new("RGBA", (1024, 1536), (60, 50, 40, 255))
    source_path = tmp_path / "source.png"
    source.save(source_path)
    result = MODULE.build(source_path, tmp_path / "out", fps=6)
    assert result["method"] == "canonical-texture-part-rig"
    assert len(result["frame_paths"]) == 6
    assert Image.open(result["sheet"]).size == (384 * 6, 384)
    assert Image.open(result["qa_preview"]).n_frames == 6
