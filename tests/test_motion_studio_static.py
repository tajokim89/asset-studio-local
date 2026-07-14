from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
UI = ROOT / "src" / "motion-studio.js"
MAIN = ROOT / "src" / "main.js"
CSS = ROOT / "styles" / "motion-studio.css"


def test_motion_workspace_integrates_after_existing_workspace_and_load_order():
    parser = HTMLParser(); parser.feed(INDEX); parser.close()
    assert 'id="studioWorkspaceSwitch"' in INDEX
    assert 'data-studio-workspace="canvas"' in INDEX and 'data-studio-workspace="motion"' in INDEX
    assert "에셋 편집" in INDEX and "모션 제작" in INDEX
    assert INDEX.index('id="workspace"') < INDEX.index('id="motionStudioWorkspace"') < INDEX.index('id="rightResize"')
    assert INDEX.index("src/main.js") < INDEX.index("src/motion-studio-core.js") < INDEX.index("src/motion-studio.js")
    assert 'styles/motion-studio.css' in INDEX


def test_korean_first_three_column_accessible_workspace_contract():
    for token in [
        'motion-studio__left', 'motion-studio__center', 'motion-studio__right',
        'motionSourceDropzone', 'accept="image/png,image/jpeg,image/webp"',
        'motionAssetId', 'motionCanvasW', 'motionCanvasH', 'motionPivotX', 'motionPivotY',
        'motionGroundX', 'motionGroundY', 'motionFacing', 'motionSampling',
        'motionRouterForm', 'motionRecommendation', 'motionApplyRecommendation',
        'role="tablist"', 'data-motion-tier="static"', 'data-motion-tier="transform_tween"',
        'data-motion-tier="state_swap"', 'data-motion-tier="rigid_parts"',
        'data-motion-tier="limited_frames"', 'data-motion-tier="full_frames"',
        'data-motion-tier="rig_paper_doll"', 'motionVfxEnabled', 'motionVfxPreview',
        '현재 캔버스에서 재생', '선택 레이어만 임시로 움직이며 원본 값은 바뀌지 않습니다.',
        'motionPlay', 'motionPause', 'motionRestart', 'motionScrubber',
        'motionRunQa', 'motionExport', 'motionImport', 'motionReset',
        'motionManifestPreview', 'aria-live="polite"'
    ]:
        assert token in INDEX
    assert UI.exists() and CSS.exists()


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


def test_motion_workspace_uses_shared_editor_image_layers_as_primary_source():
    text = UI.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    for token in (
        'id="motionLayerLinkStatus"',
        "위 캔버스의 선택 레이어에 움직임만 추가합니다.",
        'id="rightPanelLayersTab"',
    ):
        assert token in INDEX
    for token in (
        "listImageLayers",
        "getSelectedImageLayer",
        "selectImageLayer",
        "exportImageLayer",
        "subscribeLayers",
    ):
        assert token in main
    for token in (
        "editorBridge",
        "refreshEditorLayers",
        "useEditorLayer",
        "sourceLayerId",
        '$("rightPanelLayersTab")?.click()',
    ):
        assert token in text
    assert 'id="motionEditorLayerSelect"' not in INDEX
    assert 'id="motionUseEditorLayer"' not in INDEX


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


def test_motion_mode_keeps_editor_canvas_visible_and_exposes_only_simple_controls():
    css = CSS.read_text(encoding="utf-8")
    assert ".app.motion-mode > #workspace" in css
    assert "grid-row: 3" in css
    assert 'class="motion-studio__left" hidden aria-hidden="true"' in INDEX
    assert '<details class="motion-vfx" hidden aria-hidden="true">' in INDEX
    assert '<details class="motion-delivery" hidden aria-hidden="true">' in INDEX
    for label in ("움직임 없음", "위치·크기", "이미지 전환", "프레임 재생"):
        assert label in INDEX
    for tier in ("rigid_parts", "full_frames", "rig_paper_doll"):
        marker = f'data-motion-tier="{tier}"'
        button = INDEX[INDEX.index(marker):INDEX.index("</button>", INDEX.index(marker))]
        assert "hidden" in button


def test_motion_playback_uses_the_existing_editor_canvas_without_a_duplicate_preview_canvas():
    text = UI.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    assert 'id="motionPreviewCanvas"' not in INDEX
    assert 'id="motionPreviewBg"' not in INDEX
    assert 'id="motionZoom"' not in INDEX
    assert "previewImageLayer" in main
    assert "restoreImageLayerPreview" in main
    assert "previewImageLayer" in text
    assert "restoreImageLayerPreview" in text


def test_linked_motion_uses_editor_canvas_dimensions_and_selected_layer_identity():
    text = UI.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    assert "getCanvasSize" in main
    assert "bridge.getCanvasSize()" in text
    assert '$("motionCanvasW").value = canvasSize.width' in text
    assert '$("motionCanvasH").value = canvasSize.height' in text
    assert '$("motionCanvasW").value = img.naturalWidth' not in text
    assert '$("motionCanvasH").value = img.naturalHeight' not in text


def test_motion_quick_presets_offer_one_click_preview_and_explicit_apply_cancel():
    text = UI.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    for token in (
        'id="motionQuickPresets"',
        'data-motion-preset="float"',
        'data-motion-preset="breathe"',
        'data-motion-preset="bounce"',
        'data-motion-preset="shake"',
        'data-motion-preset="enter"',
        'data-motion-preset="exit"',
        'id="motionApplyToLayer"',
        'id="motionCancelApplied"',
        '이 모션 적용',
        '적용 취소',
    ):
        assert token in INDEX
    for token in (
        "QUICK_PRESETS",
        "quickPresetForLayer",
        "layerMotionMetrics",
        "applyQuickPreset",
        "applyMotionToLayer",
        "clearMotionFromLayer",
        "bridge.applyMotionToLayer",
        "bridge.clearMotionFromLayer",
    ):
        assert token in text
    for token in (
        "motionManifest",
        "applyMotionToLayer",
        "clearMotionFromLayer",
        "Motion applied to layer",
        "Motion removed from layer",
    ):
        assert token in main


def test_motion_quick_direction_buttons_cover_all_eight_compass_directions():
    text = UI.read_text(encoding="utf-8")
    for token in (
        'id="motionDirectionPresets"',
        'data-motion-direction="N"',
        'data-motion-direction="NE"',
        'data-motion-direction="E"',
        'data-motion-direction="SE"',
        'data-motion-direction="S"',
        'data-motion-direction="SW"',
        'data-motion-direction="W"',
        'data-motion-direction="NW"',
        '8방향 이동',
    ):
        assert token in INDEX
    for token in (
        "DIRECTION_VECTORS",
        "directionalTravelDistance",
        "movementOption",
        "MOVEMENT_DISTANCE_FACTORS",
        "MOVEMENT_DURATION_FACTORS",
        "applyDirectionalPreset",
        "motionDirectionPresets",
        'loop:movementMode',
    ):
        assert token in text


def test_directional_movement_exposes_compact_distance_speed_and_once_or_roundtrip_controls():
    text = UI.read_text(encoding="utf-8")
    for token in (
        'id="motionMovementOptions"',
        'data-movement-option="distance"',
        'data-movement-value="short"',
        'data-movement-value="normal"',
        'data-movement-value="far"',
        'data-movement-option="speed"',
        'data-movement-value="slow"',
        'data-movement-value="fast"',
        'data-movement-option="mode"',
        'data-movement-value="once"',
        'data-movement-value="pingpong"',
        "짧게",
        "멀리",
        "느리게",
        "빠르게",
        "한 번 이동",
        "왕복 이동",
    ):
        assert token in INDEX
    for token in (
        'distanceFactor=MOVEMENT_DISTANCE_FACTORS',
        'durationFactor=MOVEMENT_DURATION_FACTORS',
        'movementOption("mode","once")',
        'selectedDirection?.dataset.motionDirection',
    ):
        assert token in text


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
