from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
UI = ROOT / "src" / "motion-studio.js"
MAIN = ROOT / "src" / "main.js"
CSS = ROOT / "styles" / "motion-studio.css"






def test_ui_has_draft_storage_import_export_deterministic_preview_and_accessibility():
    text = UI.read_text(encoding="utf-8")
    for token in [
        "asset-studio.motion-draft/v1", "MotionStudioCore", "requestAnimationFrame",
        "prefers-reduced-motion", "previewImageLayer", "localStorage",
        "ArrowRight", "ArrowLeft", "Home", "End", "URL.createObjectURL",
        "samplePreview", "runQA", "importManifest", "stableStringify", "dragover", "drop"
    ]:
        assert token in text
    css = CSS.read_text(encoding="utf-8")
    assert "grid-template-columns" in css and "@media" in css
    assert "grid-column: 1 / 6" in css and "grid-row: 2" in css
    assert ".app.motion-mode > .props" in css and "grid-column: 6" in css


def test_motion_qa_is_invalidated_by_strategy_and_editor_changes():
    text = UI.read_text(encoding="utf-8")
    assert "function invalidateMotionQa()" in text
    assert "selectTier" in text and "invalidateMotionQa(); updateManifest();" in text
    assert '$("motionEditors").addEventListener("input"' in text
    assert '$("motionExport").disabled=true' in text
    assert "설정이 변경되었습니다. QA를 다시 실행하세요." in text


def test_motion_project_bridge_serializes_validates_and_hydrates_drafts():
    text = UI.read_text(encoding="utf-8")
    for token in (
        "window.AssetStudioMotion",
        "serializeProjectState",
        "validateProjectState",
        "hydrateProjectState",
        "canonical",
        "vfx",
    ):
        assert token in text


def test_project_v2_roundtrips_motion_studio_state_atomically():
    text = MAIN.read_text(encoding="utf-8")
    assert "motionStudio:" in text
    assert "serializeProjectState" in text
    assert "validateProjectState(project.motionStudio)" in text
    assert "hydrateProjectState(projectMotionState)" in text
    assert "motionBefore" in text
    assert "restoreRuntimeState(motionBefore)" in text




def test_entering_motion_workspace_syncs_the_current_editor_layer_without_reupload():
    text = UI.read_text(encoding="utf-8")
    assert 'refreshEditorLayers({ useSelected: true })' in text
    assert '$("rightPanelLayersTab")?.click()' in text
    assert 'button.addEventListener("click",()=>setWorkspace(button.dataset.studioWorkspace))' in text


def test_unchanged_linked_layer_does_not_invalidate_motion_qa_again():
    text = UI.read_text(encoding="utf-8")
    assert "state.sourceLayerId === layer.id && sourceImage?.src === layer.dataUrl" in text
    assert 'state.sourceDataUrl = layerId ? "" : dataUrl' in text
    assert "편집 레이어 연결 유지" in text


def test_motion_autodraft_does_not_persist_uploaded_source_media():
    text = UI.read_text(encoding="utf-8")
    assert 'draft.state.sourceDataUrl=""' in text
    assert 'draft.state.imageName=""' in text
    assert 'draft.state.sourceLayerId=""' in text
    assert 'state.sourceDataUrl=""' in text
    assert 'sourceImage=null' in text








def test_linked_motion_uses_editor_canvas_dimensions_and_selected_layer_identity():
    text = UI.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    assert "getCanvasSize" in main
    assert "bridge.getCanvasSize()" in text
    assert '$("motionCanvasW").value = canvasSize.width' in text
    assert '$("motionCanvasH").value = canvasSize.height' in text
    assert '$("motionCanvasW").value = img.naturalWidth' not in text
    assert '$("motionCanvasH").value = img.naturalHeight' not in text








def test_directional_travel_uses_canvas_span_and_rendered_layer_size():
    text = UI.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    for token in (
        "displayWidth",
        "displayHeight",
        "obj.getScaledWidth()",
        "obj.getScaledHeight()",
    ):
        assert token in main
    for token in (
        "canvasSpan*.28",
        "imageSpan*.55",
        "canvasSpan*.45",
        "bridge.listImageLayers()",
        "modeLabel",
    ):
        assert token in text


def test_removed_workspace_is_not_loaded_by_the_application():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    for removed in ["motionStudioWorkspace", "pixelPipelineWorkspace", "src/motion-studio", "src/pixel-pipeline", "styles/motion-studio", "styles/pixel-pipeline"]:
        assert removed not in html
