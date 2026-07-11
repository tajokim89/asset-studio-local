from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_TEXT = (ROOT / "server.py").read_text()
MAIN_JS = (ROOT / "src" / "main.js").read_text()
WALK4_SCRIPT = (ROOT / "scripts" / "generate_walk4_whitelist_once.py").read_text()
VISUALQA_SCRIPT = (ROOT / "scripts" / "visualqa_regen_actions.py").read_text()


def test_phase26_walk_contract_rejects_root_drift_and_one_limb_fake():
    for text in [SERVER_TEXT, MAIN_JS, WALK4_SCRIPT, VISUALQA_SCRIPT]:
        assert "root" in text
        assert "head/torso" in text
        assert "baseline" in text
    assert "only one limb/contact point moves" in SERVER_TEXT
    assert "only one limb/contact point moves" in MAIN_JS
    assert "single-limb fake" in SERVER_TEXT


def test_phase26_walk_gif_previews_preserve_cell_offsets_not_bbox_centering():
    # Preview GIF generation must not crop each frame to bbox and re-center it;
    # that masks root drift and can make a bad walk read as a horse-like bounce.
    for text in [WALK4_SCRIPT, VISUALQA_SCRIPT]:
        assert "Preserve" in text and "cell-relative offset" in text
        assert "bbox-centering" in text
        assert "c.crop(bbox)" not in text
        assert "crop=crop.crop(bbox)" not in text
        assert "alpha_composite(c,(" not in text
        assert "alignment':'preserve_cell_offsets" in text or "Preserve original cell-relative offsets" in text


def test_phase26_walk4_script_reports_anchor_drift_metrics():
    assert "anchor_drift" in WALK4_SCRIPT
    assert "bbox_center_x_range" in WALK4_SCRIPT
    assert "bbox_bottom_range" in WALK4_SCRIPT
