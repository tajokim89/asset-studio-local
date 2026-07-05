from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")


def test_freehand_eraser_targets_selected_image_not_canvas_background():
    assert "function eraseImageWithMaskDataUrl" in JS
    assert "function pathToMaskDataUrl" in JS
    assert "Freehand erase" in JS
    eraser_branch = JS.split("if (currentDrawTool === 'eraser')", 1)[1].split("path.selectable", 1)[0]
    assert "eraseImageWithMaskDataUrl" in eraser_branch
    assert "globalCompositeOperation = 'destination-out'" not in eraser_branch


def test_eraser_copy_explains_selected_image_alpha_behavior():
    assert "선택 이미지의 픽셀을 투명하게 지웁니다" in INDEX
    assert "선택 이미지가 없으면 지우개는 동작하지 않습니다" in INDEX
