from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text()
JS = (ROOT / "src" / "main.js").read_text()


def test_phase12_sprite_extract_ui_exists():
    for token in [
        "pixel-workflow-panel",
        "스프라이트 도구",
        'id="spriteMinArea"',
        'id="detectSprites"',
        'id="clearSprites"',
        'id="extractSpriteLayer"',
        'id="exportSpritePng"',
        'id="spriteExtractSummary"',
    ]:
        assert token in INDEX


def test_phase12_connected_component_detector_exists():
    for token in [
        "let spriteSlices = []",
        "let selectedSpriteSliceId = null",
        "function extractImageDataComponents",
        "alphaAt(x, y) <= 12",
        "backgroundColors",
        "new Uint8Array(width * height)",
        "area >= minArea",
        "return slices.sort",
    ]:
        assert token in JS


def test_phase12_guides_are_hidden_from_layers_and_export():
    fn = JS.split("function renderSpriteGuides()", 1)[1].split("function selectedSpriteSlice()", 1)[0]
    for token in [
        "maskRole: 'sprite-guide'",
        "excludeFromLayers: true",
        "excludeFromExport: true",
        "isMaskOverlay: true",
        "stroke: selected ? '#22c55e' : '#f59e0b'",
        "selectedSpriteSliceId = slice.id",
    ]:
        assert token in fn


def test_phase12_extract_layer_and_png_hooks_exist():
    for token in [
        "async function detectSpriteSlices()",
        "async function spriteSliceDataUrl",
        "async function extractSpriteSliceToLayer()",
        "async function exportSpriteSlicePng()",
        "spriteSliceCanvasBox(slice)",
        "addPatchImageUrl(url, { x: box?.x ?? slice.x, y: box?.y ?? slice.y",
        "downloadDataUrl(url, `sprite-slice-",
        "$('detectSprites').onclick",
        "$('extractSpriteLayer').onclick",
        "$('exportSpritePng').onclick",
    ]:
        assert token in JS


def test_phase12b_batch_zip_export_ui_exists():
    for token in [
        "pixel-workflow-panel",
        'id="exportAllSpritesZip"',
        "전체 조각 ZIP",
    ]:
        assert token in INDEX


def test_phase12b_batch_zip_export_logic_exists():
    for token in [
        "async function exportAllSpriteSlicesZip()",
        "function buildStoredZip",
        "function crc32Bytes",
        "manifest.json",
        "sprite-001.png",
        "downloadBlob(zipBlob, 'sprite-slices.zip')",
        "$('exportAllSpritesZip').onclick",
    ]:
        assert token in JS


def test_phase12c_grid_slice_ui_exists():
    for token in [
        "pixel-workflow-panel",
        "고정 그리드 자르기",
        'id="gridCols"',
        'id="gridRows"',
        'id="gridCellW"',
        'id="gridCellH"',
        'id="gridGapX"',
        'id="gridGapY"',
        'id="detectGridSprites"',
        'id="exportGridSpritesZip"',
    ]:
        assert token in INDEX


def test_phase12c_grid_slice_logic_exists():
    for token in [
        "function buildGridSpriteSlices()",
        "function spriteSliceCanvasBox(slice)",
        "async function detectGridSpriteSlices()",
        "async function exportGridSpriteSlicesZip()",
        "grid-sprite-001.png",
        "grid-manifest.json",
        "spriteSummary(`그리드",
        "$('detectGridSprites').onclick",
        "$('exportGridSpritesZip').onclick",
    ]:
        assert token in JS


def test_phase12d_sprite_auto_detect_uses_layer_relative_coords_and_grid_fallback():
    detect_fn = JS.split("async function detectSpriteSlices()", 1)[1].split("function updateSpriteGuideStyles()", 1)[0]
    for token in [
        "const bounds = imageCanvasBounds(target)",
        "const dataUrl = await imageObjectDataUrl(target)",
        "el.width = bounds.w; el.height = bounds.h",
        "x=0,y=0 is always the image layer's own top-left",
        "프레임 수 불일치 감지",
        "큰 배경 덩어리 감지",
        "fallbackToGrid",
        "현재 그리드",
    ]:
        assert token in detect_fn


def test_phase12d_guides_render_from_layer_origin_but_store_relative_coords():
    render_fn = JS.split("function renderSpriteGuides()", 1)[1].split("function selectedSpriteSlice()", 1)[0]
    sync_fn = JS.split("function syncSpriteSliceFromGuide(guide)", 1)[1].split("function renderSpriteGuides()", 1)[0]
    crop_fn = JS.split("async function spriteSliceDataUrl", 1)[1].split("async function extractSpriteSliceToLayer", 1)[0]
    assert "left: origin.left + slice.x" in render_fn
    assert "top: origin.top + slice.y" in render_fn
    assert "slice.x = Math.round((guide.left || 0) - origin.left)" in sync_fn
    assert "slice.y = Math.round((guide.top || 0) - origin.top)" in sync_fn
    assert "const scaleX = naturalW / Math.max(1, bounds.w)" in crop_fn
    assert "const scaleY = naturalH / Math.max(1, bounds.h)" in crop_fn
    assert "ctx.drawImage(img, sx, sy, sw, sh, 0, 0, el.width, el.height)" in crop_fn
