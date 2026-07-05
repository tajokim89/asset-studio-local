from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_region_selection_tool_ui_exists():
    for token in [
        'data-tool="region"',
        'data-tool-panel="region"',
        'id="regionMode"',
        'value="rect"',
        'value="ellipse"',
        'value="lasso"',
        'id="clearRegionSelection"',
    ]:
        assert token in INDEX


def test_region_selection_functions_exist_and_target_selected_layer():
    for token in [
        "let regionSelectionMode = 'rect'",
        "function configureRegionSelectionTool",
        "function beginRegionSelection",
        "function updateRegionSelection",
        "function finishRegionSelection",
        "function addRegionEllipse",
        "function addRegionPath",
        "function ensureRegionSelectionTarget",
        "maskRole = 'selection-mask'",
        "targetLayerId = layerKey(target)",
    ]:
        assert token in JS


def test_region_selection_integrates_with_mouse_and_shortcuts():
    for token in [
        "toolNames = { select:'선택', region:'영역 선택'",
        "currentTool === 'region'",
        "configureRegionSelectionTool()",
        "beginRegionSelection(opt)",
        "updateRegionSelection(opt)",
        "finishRegionSelection()",
        "case 'a': activateTool('region')",
        "regionSelectionMode === 'lasso'",
    ]:
        assert token in JS
