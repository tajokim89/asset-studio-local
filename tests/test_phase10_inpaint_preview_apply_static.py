from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text()
JS = (ROOT / "src" / "main.js").read_text()


def test_phase10_cache_bust_and_preview_controls_exist():
    assert "phase13-pixel-generator" in INDEX
    for token in [
        'id="inpaintPreviewPanel"',
        'id="inpaintPreviewImg"',
        'id="applyInpaintNewLayer"',
        'id="applyInpaintReplace"',
        'id="retryInpaint"',
        'id="cancelInpaint"',
        "AI 결과 미리보기",
        "새 레이어 적용",
        "선택 이미지 교체",
        "다시 생성",
    ]:
        assert token in INDEX


def test_phase10_inpaint_run_only_creates_pending_preview_not_auto_apply():
    fn = JS.split("async function runSelectedAreaAiEdit()", 1)[1].split("function configureRegionSelectionTool", 1)[0]
    assert "apply_mode: 'preview'" in fn
    assert "showPendingInpaintResult(data, prompt, negative, target)" in fn
    assert "addPatchImageUrl" not in fn
    assert "addFullCanvasImageDataUrl" not in fn


def test_phase10_apply_retry_cancel_handlers_are_wired():
    for token in [
        "function showPendingInpaintResult(data, prompt, negative, target)",
        "async function applyPendingInpaintAsLayer()",
        "async function applyPendingInpaintAsReplacement()",
        "async function retryPendingInpaint()",
        "function clearPendingInpaintResult",
        "$('applyInpaintNewLayer').onclick = applyPendingInpaintAsLayer",
        "$('applyInpaintReplace').onclick = applyPendingInpaintAsReplacement",
        "$('retryInpaint').onclick = retryPendingInpaint",
        "$('cancelInpaint').onclick = () => clearPendingInpaintResult()",
    ]:
        assert token in JS


def test_phase10_replacement_preserves_original_and_records_history():
    fn = JS.split("async function applyPendingInpaintAsReplacement()", 1)[1].split("async function retryPendingInpaint()", 1)[0]
    for token in [
        "target.visible = false",
        "target._phase4PreservedOriginal = true",
        "addFullCanvasImageDataUrl",
        "saveHistory()",
        "원본은 숨김 보존됨",
    ]:
        assert token in fn
