from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_phase16_page_asset_pack_ui_exists():
    required = [
        "src/main.js?v=20260714.11",
        "runPixelSamplePack",
        "샘플팩 생성",
        "선택한 이미지 레이어를 기준 이미지로 사용",
    ]
    for token in required:
        assert token in INDEX


def test_phase16_sample_pack_logic_exists():
    required = [
        "async function runPixelSamplePack",
        "await runPixelWorkflow()",
        "샘플팩 완료",
        "runPixelSamplePack').onclick",
        "recordPixelAssetResult(finalUrl",
    ]
    for token in required:
        assert token in JS


def test_phase16_remove_bg_returns_cutout_before_grid_preview():
    workflow = JS.split("async function runPixelWorkflow()", 1)[1].split("async function runDirectionalPixelWorkflow", 1)[0]
    assert "return { url, cutout, data }" in JS
    assert "const cleaned = await removeBgSelected('chroma_green'" in workflow
    assert "finalImg = cleaned.cutout" in workflow
    assert workflow.index("const cleaned = await removeBgSelected('chroma_green'") < workflow.index("spriteSlices = buildGridSpriteSlices()")


def test_phase16_data_urls_are_not_cache_busted():
    assert "function withCacheBust" in JS
    assert "url.startsWith('data:')" in JS
    assert "const url = withCacheBust(data.url);" in JS
