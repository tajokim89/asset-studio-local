from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_region_selection_copy_cut_buttons_exist():
    for token in [
        'id="copyRegionSelection"',
        'id="cutRegionSelection"',
        '선택영역 복사',
        '선택영역 잘라내기',
        'phase15-pixel-workflow',
    ]:
        assert token in INDEX


def test_region_selection_copy_cut_functions_use_selected_image_and_mask():
    for token in [
        'async function selectedRegionAsFullCanvasDataUrl(target, maskDataUrl)',
        'async function putSelectedRegionOnClipboard({ cut = false } = {})',
        'async function copySelectedRegionToLayer({ cut = false } = {})',
        "selectedImageAsFullCanvasDataUrl(target)",
        "buildMaskDataUrl('edit')",
        "destination-in",
        'function regionBoundsFromMaskOverlays()',
        "cropCanvasDataUrlToBounds(regionUrl, regionBounds)",
        "maskImageToAlphaCanvas(maskImg",
        "regionClipboard = {",
        "eraseSelectedImageOnCanvasWithMask(target, maskDataUrl, 'Cut selected region')",
    ]:
        assert token in JS


def test_region_selection_copy_cut_buttons_are_wired():
    for token in [
        "$('copyRegionSelection').onclick = () => putSelectedRegionOnClipboard({ cut: false })",
        "$('cutRegionSelection').onclick = () => putSelectedRegionOnClipboard({ cut: true })",
    ]:
        assert token in JS
