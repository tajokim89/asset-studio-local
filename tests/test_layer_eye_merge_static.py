from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_layer_visibility_button_is_eye_icon_state_not_text_label():
    assert "const visibilityIcon = obj.visible === false ? '👁️‍🗨️' : '👁️'" in JS
    assert "data-act=\"vis\"" in JS
    assert "aria-pressed=\"${obj.visible !== false}\"" in JS
    assert ">${visibilityIcon}</button>" in JS
    assert ">${visibilityLabel}</button>" not in JS


def test_layer_panel_supports_multiselect_for_merge():
    for token in [
        "function selectedMergeableLayers",
        "function toggleLayerPanelMultiSelect",
        "function mergeSelectedLayers",
        "sel.type === 'activeSelection'",
        "e.shiftKey || e.metaKey || e.ctrlKey",
        "두 개 이상 선택",
    ]:
        assert token in JS


def test_merge_action_uses_selected_layers_not_merge_down():
    assert "function mergeLayerDown" not in JS
    assert "if (act === 'merge') { mergeSelectedLayers(); return; }" in JS
    assert "data-act=\"merge\"" in JS
    assert "Merge↓" not in JS
