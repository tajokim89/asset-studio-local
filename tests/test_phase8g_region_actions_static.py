from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_phase8g_region_action_ui_has_paste_and_clear_selection_copy():
    for token in [
        "phase12-ai-chat-exec-router2",
        'id="pasteRegionSelection"',
        "선택영역 붙여넣기",
        "선택 해제",
        "선택영역 PNG",
    ]:
        assert token in INDEX


def test_export_region_selection_downloads_transparent_crop_not_mask_png():
    for token in [
        "async function exportRegionSelectionPng()",
        "const target = selectedLayerObject();",
        "const maskDataUrl = await buildMaskDataUrl('edit');",
        "const regionUrl = await selectedRegionAsFullCanvasDataUrl(target, maskDataUrl);",
        "const regionCroppedUrl = await cropCanvasDataUrlToBounds(regionUrl, regionBounds);",
        "downloadDataUrl(regionCroppedUrl, 'asset-studio-region-selection.png')",
    ]:
        assert token in JS
    assert "$('exportRegionSelection').onclick = exportRegionSelectionPng" in JS
    assert "$('exportRegionSelection').onclick = exportMaskPng" not in JS


def test_region_selection_clear_does_not_clear_all_masks_or_save_history():
    for token in [
        "function clearRegionSelectionOnly()",
        "clearRegionSelectionVisuals('선택영역을 해제했습니다.')",
        "$('clearRegionSelection').onclick = clearRegionSelectionOnly",
    ]:
        assert token in JS
    clear_region_fn = JS.split("function clearRegionSelectionOnly", 1)[1].split("async function buildMaskDataUrl", 1)[0]
    assert "clearMask" not in clear_region_fn
    assert "saveHistory" not in clear_region_fn


def test_region_paste_button_is_wired_to_internal_clipboard():
    for token in [
        "$('pasteRegionSelection').onclick = () => pasteRegionClipboard().catch",
        "async function pasteRegionClipboard()",
        "setStatus('클립보드 선택영역을 새 이미지 레이어로 붙여넣었습니다.')",
    ]:
        assert token in JS
