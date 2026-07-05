from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
CSS = (ROOT / "styles" / "app.css").read_text(encoding="utf-8")


def test_phase6a_crop_and_resize_controls_exist():
    for token in [
        'id="cropX"', 'id="cropY"', 'id="cropW"', 'id="cropH"',
        'id="applyCanvasCrop"', 'id="cropSelectedImage"', 'id="resizeFitObjects"',
    ]:
        assert token in INDEX
    for fn in ['function applyCanvasCrop', 'function cropSelectedImage', 'function resizeCanvasFitObjects']:
        assert fn in JS


def test_phase6b_alpha_eraser_restore_controls_exist():
    for token in ['id="eraseSelectedByMask"', 'id="restoreSelectedByMask"', 'id="restoreSelectedOriginal"']:
        assert token in INDEX
    for fn in ['function eraseSelectedByMask', 'function restoreSelectedByMask', 'function restoreSelectedOriginal']:
        assert fn in JS
    assert 'buildMaskDataUrl' in JS


def test_phase6c_layer_controls_exist():
    for token in ['id="layerOpacity"', 'id="groupSelection"', 'id="ungroupSelection"', 'id="exportLayer"']:
        assert token in INDEX
    for fn in ['function applyLayerOpacity', 'function groupSelection', 'function ungroupSelection', 'function exportActiveLayer']:
        assert fn in JS
    assert 'layer-control-grid' in CSS


def test_phase6_actions_are_history_labeled():
    for label in ['Canvas crop', 'Selected image crop', 'Alpha erase by mask', 'Restore by mask', 'Group selection', 'Ungroup selection']:
        assert f"saveHistory('{label}')" in JS
