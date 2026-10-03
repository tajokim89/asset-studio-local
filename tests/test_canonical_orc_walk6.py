import importlib.util
import sys
from pathlib import Path

from PIL import Image


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "canonical_orc_walk6.py"
SPEC = importlib.util.spec_from_file_location("canonical_orc_walk6", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_contact_and_passing_pose_contract():
    assert len(MODULE.POSES) == len(MODULE.PHASES) == 6
    left_contact, _, left_pass, right_contact, _, right_pass = MODULE.POSES
    assert left_contact["left"][3] > left_contact["right"][3]
    assert right_contact["right"][3] > right_contact["left"][3]
    assert left_pass["right"][2][1] < left_pass["left"][2][1]
    assert right_pass["left"][2][1] < right_pass["right"][2][1]


def test_build_exports_exact_six_frames(tmp_path: Path):
    result = MODULE.build(tmp_path, fps=6)
    assert result["frames"] == 6
    assert len(result["frame_paths"]) == 6
    assert Image.open(result["sheet"]).size == (384 * 6, 384)
    assert Image.open(result["preview"]).n_frames == 6
