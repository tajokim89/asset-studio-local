from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_region_copy_cut_use_internal_clipboard_not_immediate_layer():
    for token in [
        "let regionClipboard = null;",
        "async function putSelectedRegionOnClipboard({ cut = false } = {})",
        "regionClipboard = {",
        "kind: 'region-image'",
        "sourceLayerId: layerKey(target)",
        "await eraseSelectedImageOnCanvasWithMask(target, maskDataUrl, 'Cut selected region')",
        "return regionClipboard",
    ]:
        assert token in JS
    clipboard_fn = JS.split("async function putSelectedRegionOnClipboard", 1)[1].split("async function pasteRegionClipboard", 1)[0]
    assert "addPatchImageUrl" not in clipboard_fn


def test_cut_erase_uses_full_canvas_mask_not_native_coordinate_projection():
    for token in [
        "async function eraseSelectedImageOnCanvasWithMask(obj, maskDataUrl, historyLabel = 'Cut selected region')",
        "selectedImageAsFullCanvasDataUrl(obj)",
        "maskImageToAlphaCanvas(maskImg, out.width, out.height)",
        "replaceImageWithCroppedCanvasLayer(obj, out.toDataURL('image/png')",
    ]:
        assert token in JS
    cut_fn = JS.split("async function putSelectedRegionOnClipboard", 1)[1].split("async function pasteRegionClipboard", 1)[0]
    assert "eraseImageAtNativeResolution" not in cut_fn


def test_region_paste_and_keyboard_shortcuts_are_wired():
    for token in [
        "async function pasteRegionClipboard()",
        "addPatchImageUrl(regionClipboard.url, pasteBounds",
        "function handleClipboardShortcut(e)",
        "putSelectedRegionOnClipboard({ cut: false })",
        "putSelectedRegionOnClipboard({ cut: true })",
        "pasteRegionClipboard()",
        "if (handleClipboardShortcut(e)) return;",
    ]:
        assert token in JS


def test_lasso_is_closed_filled_selection_mask_not_a_visible_stroke_only():
    for token in [
        "function closeLassoPath(path)",
        "closeLassoPath(path);",
        "fill: 'rgba(239,68,68,0.18)'",
        "strokeDashArray: [8, 5]",
        "fill: isErase ? '#000' : '#fff'",
        "clearRegionSelectionVisuals()",
    ]:
        assert token in JS
