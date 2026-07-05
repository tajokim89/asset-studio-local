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


def test_erased_image_preserves_native_resolution_not_canvas_bbox():
    assert "function eraseImageAtNativeResolution" in JS
    assert "function replaceImagePreservingTransform" in JS
    eraser_fn = JS.split("async function eraseImageWithMaskDataUrl", 1)[1].split("function pathToMaskDataUrl", 1)[0]
    assert "eraseImageAtNativeResolution(obj, maskDataUrl)" in eraser_fn
    assert "replaceImagePreservingTransform" in eraser_fn
    assert "replaceImageWithCroppedCanvasLayer" not in eraser_fn
    assert "imageElementSize(obj)" in JS
    assert "원본 해상도를 유지" in JS


def test_eraser_switches_canvas_preview_to_transparency_checker():
    assert "function showTransparentCanvasPreview" in JS
    eraser_fn = JS.split("async function eraseImageWithMaskDataUrl", 1)[1].split("function pathToMaskDataUrl", 1)[0]
    assert "showTransparentCanvasPreview();" in eraser_fn
    assert "canvas.backgroundColor = null" in JS
    assert "classList.add('checker')" in JS
    assert "alpha=0 투명" in JS
