from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def remove_bg_selected_body() -> str:
    start = JS.index("async function removeBgSelected")
    end = JS.index("function resetImage", start)
    return JS[start:end]


def test_remove_bg_uses_selected_image_source_not_canvas_export():
    body = remove_bg_selected_body()
    assert "const obj = selectedLayerObject()" in body
    assert "const image = imageObjectToDataUrl(obj)" in body
    assert "data.url.startsWith('data:') ? data.url : data.url + '?t=' + Date.now()" in body
    assert "canvas.toDataURL" not in body


def test_remove_bg_does_not_change_global_canvas_background_or_checker():
    body = remove_bg_selected_body()
    assert "canvas.backgroundColor = null" not in body
    assert "canvas.setBackgroundColor" not in body
    assert "canvasShell').classList.add('checker')" not in body
    assert "선택한 이미지 레이어에만" in body


def test_remove_bg_keeps_cutout_transform_and_other_layers_untouched_label():
    body = remove_bg_selected_body()
    for token in [
        "left: obj.left",
        "top: obj.top",
        "scaleX: obj.scaleX",
        "scaleY: obj.scaleY",
        "angle: obj.angle",
        "canvas.insertAt(cutout, idx + 1, false)",
        "obj.visible = false",
    ]:
        assert token in body
