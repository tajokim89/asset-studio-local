from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_phase8h_region_panel_has_ai_edit_button_and_cache_bust():
    for token in [
        "phase11b-project-file-qa",
        'id="regionAiEdit"',
        "선택영역 AI 수정",
        'id="directInpaintDetails"',
        'id="aiEditPanel"',
    ]:
        assert token in INDEX


def test_region_ai_edit_bridge_validates_target_and_region_then_focuses_prompt():
    for token in [
        "function selectedRegionEditState()",
        "function prepareSelectedRegionAiEdit()",
        "const target = selectedLayerObject();",
        "positiveEditMaskOverlays()",
        "regionBoundsFromMaskOverlays()",
        "$('directInpaintDetails').open = true",
        "$('aiEditPanel')?.scrollIntoView({ behavior: 'smooth', block: 'start' })",
        "$('inpaintPrompt')?.focus()",
        "setStatus('선택영역 AI 수정 준비 완료",
    ]:
        assert token in JS


def test_region_ai_edit_button_is_wired_without_running_ai_immediately():
    assert "$('regionAiEdit').onclick = prepareSelectedRegionAiEdit" in JS
    bridge_fn = JS.split("function prepareSelectedRegionAiEdit", 1)[1].split("function setInpaintBusy", 1)[0]
    assert "runSelectedAreaAiEdit" not in bridge_fn
    assert "fetch('/api/inpaint'" not in bridge_fn


def test_region_ai_edit_updates_summary_with_bbox_and_target():
    for token in [
        "const bbox = regionBoundsFromMaskOverlays();",
        "const summary = `선택영역 AI 수정 준비: ${nameOf(state.target)} · ${Math.round(state.bbox.width)}×${Math.round(state.bbox.height)}`;",
        "$('aiMaskSummary').textContent = summary",
        "$('inpaintResult').textContent = '프롬프트 입력 후 선택영역 직접 재생성을 누르세요.'",
    ]:
        assert token in JS
