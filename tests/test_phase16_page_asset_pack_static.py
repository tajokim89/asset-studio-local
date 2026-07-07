from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_phase16_page_asset_pack_ui_exists():
    required = [
        "phase17-directional-chroma",
        "runPixelSamplePack",
        "Idle/Walk/UI 샘플팩",
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
    assert "return { url, cutout, data }" in JS
    assert "const cleaned = await removeBgSelected('chroma_green'" in JS
    assert "finalImg = cleaned.cutout" in JS
    assert JS.index("const cleaned = await removeBgSelected('chroma_green'") < JS.index("await detectGridSpriteSlices()")


def test_phase16_data_urls_are_not_cache_busted():
    assert "function withCacheBust" in JS
    assert "url.startsWith('data:')" in JS
    assert "const url = withCacheBust(data.url);" in JS
