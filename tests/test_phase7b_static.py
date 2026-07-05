from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
CSS = (ROOT / "styles" / "app.css").read_text(encoding="utf-8")


def test_phase7b_layer_action_functions_exist():
    for token in [
        "function isLayerLocked",
        "function setLayerLocked",
        "function toggleLayerVisibility",
        "function deleteLogicalLayer",
        "function duplicateLogicalLayer",
        "function mergeSelectedLayers",
        "function handleLayerAction",
        "function canSelectLayer",
        "function enforceLayerInteractivity",
    ]:
        assert token in JS


def test_phase7b_layer_buttons_are_labeled_and_tooltipped():
    for token in [
        "data-act=\"duplicate\"",
        "data-act=\"merge\"",
        "data-act=\"delete\"",
        "const visibilityIcon = obj.visible === false ? '👁️‍🗨️' : '👁️'",
        "const lockTitle = isLayerLocked(obj) ? 'Unlock layer' : 'Lock layer'",
        "aria-label=",
        "layer-state-badges",
        "layer-action-row",
    ]:
        assert token in JS or token in CSS


def test_phase7b_hidden_and_locked_layers_are_guarded():
    for token in [
        "obj.selectable = obj.visible !== false && !isLayerLocked(obj)",
        "obj.evented = obj.visible !== false && !isLayerLocked(obj)",
        "if (!canSelectLayer(obj))",
        "레이어가 숨김 상태입니다",
        "레이어가 잠겨 있습니다",
        "if (isLayerLocked(obj)) { setStatus",
        "object:moving",
    ]:
        assert token in JS


def test_phase7b_layer_panel_css_supports_more_actions():
    for token in [
        "grid-template-columns: 22px 1fr",
        ".layer-main-row",
        ".layer-action-row",
        ".layer-state-badges",
        ".layer-badge",
        ".layer-item.is-hidden",
        ".layer-item.is-locked",
    ]:
        assert token in CSS
