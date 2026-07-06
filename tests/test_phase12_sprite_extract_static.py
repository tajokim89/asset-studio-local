from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text()
JS = (ROOT / "src" / "main.js").read_text()


def test_phase12_sprite_extract_ui_exists():
    for token in [
        "phase14-animation-preview",
        "스프라이트 시트 추출",
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
        "alphaAt(x, y) > 12",
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
        "addPatchImageUrl(url, { x: slice.x, y: slice.y",
        "downloadDataUrl(url, `sprite-slice-",
        "$('detectSprites').onclick",
        "$('extractSpriteLayer').onclick",
        "$('exportSpritePng').onclick",
    ]:
        assert token in JS


def test_phase12b_batch_zip_export_ui_exists():
    for token in [
        "phase14-animation-preview",
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
        "phase14-animation-preview",
        "그리드 슬라이스",
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
        "async function detectGridSpriteSlices()",
        "async function exportGridSpriteSlicesZip()",
        "grid-sprite-001.png",
        "grid-manifest.json",
        "spriteSummary(`그리드",
        "$('detectGridSprites').onclick",
        "$('exportGridSpritesZip').onclick",
    ]:
        assert token in JS
