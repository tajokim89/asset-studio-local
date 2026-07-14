from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_sprite_slice_export_crops_from_source_image_not_full_canvas():
    body = JS[JS.index("async function spriteSliceDataUrl"):JS.index("async function extractSpriteSliceToLayer")]
    assert "imageObjectDataUrl(target)" in body
    assert "canvasWithOnlyObjectDataUrl(target)" not in body
    assert "spriteSlices are selected-image-local coordinates" in body
    assert "ctx.drawImage(img, sx, sy, sw, sh" in body


def test_sprite_slice_crop_scales_local_slice_to_natural_source_buffer():
    body = JS[JS.index("async function spriteSliceDataUrl"):JS.index("async function extractSpriteSliceToLayer")]
    for token in [
        "naturalW / Math.max(1, bounds.w)",
        "naturalH / Math.max(1, bounds.h)",
        "Math.round((slice.x || 0) * scaleX)",
        "Math.round((slice.y || 0) * scaleY)",
        "Math.round((slice.width || 1) * scaleX)",
        "Math.round((slice.height || 1) * scaleY)",
    ]:
        assert token in body


def test_cache_busts_sprite_crop_fix():
    assert "src/main.js?v=20260714.11" in INDEX
