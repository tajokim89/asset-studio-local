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
        'motionPreviewCanvas', 'aria-label="모션 미리보기 캔버스"',
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
        "prefers-reduced-motion", "imageSmoothingEnabled", "localStorage",
        "ArrowRight", "ArrowLeft", "Home", "End", "URL.createObjectURL",
        "samplePreview", "runQA", "importManifest", "stableStringify", "dragover", "drop"
    ]:
        assert token in text
    css = CSS.read_text(encoding="utf-8")
    assert "grid-template-columns" in css and "@media" in css
    assert "grid-column: 1 / 7" in css and "grid-row: 2" in css


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
