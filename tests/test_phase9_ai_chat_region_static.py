from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")

spec = importlib.util.spec_from_file_location("asset_studio_server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def test_phase9_cache_bust_and_chat_mentions_region_edit():
    assert "phase11-project-v2" in INDEX
    assert "선택영역을 AI 수정으로 보낼 수 있습니다" in INDEX


def test_chat_context_tracks_region_selection_separately_from_mask_tool():
    for token in [
        "const regionCount = positiveRegionSelectionOverlays().length;",
        "const regionBbox = regionBoundsFromMaskOverlays();",
        "regionSelection: { count: regionCount, bbox: regionBbox }",
        "선택영역 ${ctx.regionSelection.count}",
    ]:
        assert token in JS


def test_server_routes_selected_region_edit_to_region_inpaint_action():
    context = {
        "selectedLayer": {"type": "image", "name": "Fixture Image"},
        "mask": {"count": 0, "editCount": 0, "occlusionCount": 0},
        "regionSelection": {"count": 1, "bbox": {"x": 10, "y": 12, "width": 32, "height": 40}},
    }
    result = server.classify_chat_command("선택영역 얼굴 부분 자연스럽게 수정해줘", context)
    assert result["success"] is True
    assert result["action"]["type"] == "prepare_region_inpaint"
    assert result["action"]["params"]["prompt"] == "선택영역 얼굴 부분 자연스럽게 수정해줘"
    assert result["action"]["requires_confirm"] is True


def test_prepare_region_inpaint_executes_bridge_not_generic_details():
    for token in [
        "case 'prepare_region_inpaint':",
        "const prepared = prepareSelectedRegionAiEdit();",
        "if ($('inpaintPrompt')) $('inpaintPrompt').value = params.prompt || '';",
        "done('준비됨: 선택영역 AI 수정 패널로 연결했습니다. 프롬프트 확인 후 실행하세요.');",
    ]:
        assert token in JS
