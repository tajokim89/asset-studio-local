from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
CSS = (ROOT / "styles" / "app.css").read_text(encoding="utf-8")


def test_phase7a_history_helpers_and_serialization():
    for token in [
        "const SERIALIZED_PROPS",
        "excludeFromExport",
        "function undoHistory()",
        "function redoHistory()",
        "function isEditableTextField",
        "$('undoBtn').onclick = undoHistory",
        "$('redoBtn').onclick = redoHistory",
        "canvas.toDatalessJSON(SERIALIZED_PROPS)",
    ]:
        assert token in JS


def test_phase7a_pan_zoom_shortcuts_exist():
    for token in [
        "function zoomBy",
        "function beginWorkspacePan",
        "function updateWorkspacePan",
        "function endWorkspacePan",
        "function startTemporaryPan",
        "function endTemporaryPan",
        "temporaryPanPreviousTool",
        "e.code === 'Space' && !e.repeat",
        "endTemporaryPan()",
        "e.button === 1",
        "['+','=','-','0'].includes(e.key)",
    ]:
        assert token in JS
    assert "styles/app.css?v=phase8f-selection-ux-polish" in INDEX
    assert "src/main.js?v=phase8f-selection-ux-polish" in INDEX
    assert ".workspace.is-panning" in CSS


def test_phase7a_history_labels_for_mask_actions():
    for label in ["Grip anchor", "Clear mask", "Invert mask", "Freehand erase", "Mask rectangle", "Mask brush stroke"]:
        assert label in JS


def test_phase7a_tool_shortcuts_exist():
    for token in [
        "function handleToolShortcut",
        "function toggleDrawingTool",
        "function toggleShapeTool",
        "case 'a': activateTool('region')",
        "case 'v': activateTool('select')",
        "case 'b': toggleDrawingTool()",
        "case 'r': toggleShapeTool()",
        "if (handleToolShortcut(e)) return",
    ]:
        assert token in JS
    for label in [">V<", ">C<", ">B<", ">E<", ">M<", ">T<", ">R<"]:
        assert label in INDEX


def test_phase7a_crop_drag_selection_exists():
    for token in [
        "let isCropDragging",
        "let cropStart",
        "let cropPreview",
        "function beginCropSelection",
        "function updateCropSelection",
        "function finishCropSelection",
        "function clearCropPreview",
        "isCropPreview",
        "if (currentTool === 'crop')",
        "setCropInputs(left, top",
        "캔버스 위에서 드래그해 크롭 영역",
    ]:
        assert token in JS or token in INDEX


def test_layer_visibility_buttons_are_clickable_inside_draggable_rows():
    for token in [
        "const visibilityIcon = obj.visible === false ? '👁️‍🗨️' : '👁️'",
        "data-act=\"vis\" draggable=\"false\"",
        "btn.addEventListener('pointerdown', (e) => e.stopPropagation())",
        "btn.addEventListener('dragstart', (e) => e.preventDefault())",
        "btn.addEventListener('click', (e) =>",
        "e.stopPropagation()",
        "if (act === 'vis')",
        "applyDrawingLayerVisibility(obj)",
    ]:
        assert token in JS
