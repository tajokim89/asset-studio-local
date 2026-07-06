from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_phase8f_cache_busted_and_escape_clear_exists():
    assert "phase12-ai-chat-exec-router2" in INDEX
    for token in [
        "function handleEscapeShortcut(e)",
        "if (handleEscapeShortcut(e)) return;",
        "clearRegionSelectionVisuals('Selection cleared')",
        "e.key === 'Escape'",
    ]:
        assert token in JS


def test_region_selection_overlays_are_editable_without_stealing_target_layer():
    for token in [
        "function setRegionOverlayInteractivity(editable)",
        "o.selectable = editable",
        "o.evented = editable",
        "function rememberSelectedLayer(obj)",
        "if (!obj || obj.isMaskOverlay || obj.excludeFromLayers) return;",
        "setRegionOverlayInteractivity(true)",
        "canvas.on('object:modified', (e) => {",
        "updateRegionInfoFromOverlay(e.target)",
    ]:
        assert token in JS


def test_paste_region_offsets_repeated_pastes_and_selects_new_layer():
    for token in [
        "let regionPasteCount = 0;",
        "const offset = regionPasteCount * 12;",
        "x: baseX + offset",
        "y: baseY + offset",
        "regionPasteCount += 1;",
        "canvas.setActiveObject(img);",
        "rememberSelectedLayer(img);",
    ]:
        assert token in JS


def test_region_bounds_follow_moved_or_resized_overlay_geometry():
    for token in [
        "function updateRegionInfoFromOverlay(overlay)",
        "const rect = overlay.getBoundingRect(true, true);",
        "region.left = rect.left;",
        "region.width = rect.width;",
        "region.height = rect.height;",
    ]:
        assert token in JS
