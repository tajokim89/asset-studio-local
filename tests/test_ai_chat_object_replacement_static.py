from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
SERVER = (ROOT / "server.py").read_text(encoding="utf-8")


def test_object_replacement_button_is_usable_without_mask():
    assert 'id="generateReplacement" class="primary">오브젝트 생성/앵커 배치' in INDEX
    assert 'id="generateReplacement" class="primary" disabled' not in INDEX
    assert "const hasReplacementMask = !!bbox;" in JS
    assert "마스크가 있으면 교체 배치, 없으면 새 오브젝트 레이어로 생성합니다." in JS
    assert "if ($('generateReplacement')) $('generateReplacement').disabled = false;" in JS
    assert "addImageUrl(objectUrl, `Object - ${prompt.slice(0, 28)}`);" in JS


def test_ai_chat_executes_object_replacement_flow_with_negative():
    assert 'id="aiChatNegative"' in INDEX
    assert '"execute_replace_object"' in SERVER
    assert "내부 오브젝트 치환 파이프라인을 호출합니다" in SERVER
    assert "case 'execute_replace_object':" in JS
    assert "$('replaceObjectNegative').value = params.negative || '';" in JS
    assert "await generateReplacementObject();" in JS
