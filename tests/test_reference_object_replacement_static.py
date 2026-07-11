from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src" / "main.js").read_text()
SERVER = (ROOT / "server.py").read_text()
INDEX = (ROOT / "index.html").read_text()


def test_server_has_reference_object_replace_endpoint_and_prompt():
    assert 'if path == "/api/replace-object"' in SERVER
    assert "build_replace_object_prompt" in SERVER
    assert "The first input image is the real reference/context crop" in SERVER
    assert "collect_codex_replacement_b64" in SERVER
    assert "replacement_patch_with_mask" in SERVER
    assert '"codex-reference-object-replace+transparent-mask-patch+1to1-bbox"' in SERVER


def test_frontend_masked_replacement_sends_selected_image_and_mask_not_plain_generate():
    fn = JS.split("async function generateReplacementObject()", 1)[1].split("function exportCanvasWithoutMaskOverlays", 1)[0]
    masked_branch = fn.split("if (hasReplacementMask)", 1)[1].split("const contextName", 1)[0]
    assert "canvasWithOnlyObjectDataUrl(target)" in masked_branch
    assert "buildMaskDataUrl('edit')" in masked_branch
    assert "fetch('/api/replace-object'" in masked_branch
    assert "fetch('/api/generate'" not in masked_branch
    assert "addPatchImageUrl(objectUrl, patchBox" in masked_branch


def test_direct_inpaint_uses_selected_image_source_and_one_to_one_patch_metadata():
    run_fn = JS.split("async function runSelectedAreaAiEdit()", 1)[1].split("function configureRegionSelectionTool", 1)[0]
    apply_fn = JS.split("async function applyPendingInpaintAsLayer()", 1)[1].split("async function applyPendingInpaintAsReplacement", 1)[0]
    add_patch_fn = JS.split("function addPatchImageUrl", 1)[1].split("function loadHtmlImage", 1)[0]
    assert "const image = await canvasWithOnlyObjectDataUrl(target);" in run_fn
    assert "patch_width: pendingInpaintResult.patch_width" in apply_fn
    assert "exactPatch ? 1 : box.width / img.width" in add_patch_fn
    assert '"patch_width": bbox["width"]' in SERVER
    assert '"patch_height": bbox["height"]' in SERVER


def test_ui_explains_masked_replacement_and_unmasked_new_layer_flow():
    assert "마스크/선택 영역이 있으면 그 부분만 교체합니다." in INDEX
    assert "마스크가 있으면 교체 배치, 없으면 새 오브젝트 레이어로 생성합니다." in INDEX
