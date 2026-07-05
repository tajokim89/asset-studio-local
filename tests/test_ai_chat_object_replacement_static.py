from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text()
JS = (ROOT / "src" / "main.js").read_text()
SERVER = (ROOT / "server.py").read_text()


def test_object_replacement_button_is_usable_without_mask():
    assert 'id="generateReplacement" class="primary">오브젝트 생성/앵커 배치' in INDEX
    assert 'id="generateReplacement" class="primary" disabled' not in INDEX
    assert "const hasReplacementMask = !!bbox;" in JS
    assert "마스크가 있으면 교체 배치, 없으면 새 오브젝트 레이어로 생성합니다." in JS
    assert "if ($('generateReplacement')) $('generateReplacement').disabled = false;" in JS
    assert "addImageUrl(objectUrl, `Object - ${prompt.slice(0, 28)}`);" in JS


def test_ai_chat_can_prepare_object_replacement_flow():
    assert '"prepare_replace_object"' in SERVER
    assert "오브젝트 치환 B안에 프롬프트를 넣습니다" in SERVER
    assert "case 'prepare_replace_object':" in JS
    assert "$('replaceObjectPrompt').value = params.prompt || '';" in JS
