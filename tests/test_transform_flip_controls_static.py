from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_transform_panel_exposes_horizontal_and_vertical_flip_buttons():
    assert 'id="flipHorizontal"' in INDEX
    assert '>좌우 반전</button>' in INDEX
    assert 'id="flipVertical"' in INDEX
    assert '>상하 반전</button>' in INDEX


def test_selected_layer_flip_toggles_fabric_flags_and_records_history():
    for token in [
        "function flipSelected(axis)",
        "const obj = selectedLayerObject();",
        "const prop = axis === 'horizontal' ? 'flipX' : 'flipY';",
        "obj.set(prop, !obj[prop]);",
        "obj.setCoords?.();",
        "saveHistory(axis === 'horizontal' ? 'Flip horizontal' : 'Flip vertical');",
        "$('flipHorizontal').onclick = () => flipSelected('horizontal');",
        "$('flipVertical').onclick = () => flipSelected('vertical');",
    ]:
        assert token in JS


def test_flip_controls_use_new_cache_busted_script():
    assert "src/main.js?v=20260710.8" in INDEX
