from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
SERVER = (ROOT / "server.py").read_text(encoding="utf-8")


def test_phase16_reference_ui_exists():
    required = [
        "pixelUseReference",
        "선택한 이미지 레이어를 기준 이미지로 사용",
    ]
    for token in required:
        assert token in INDEX
    assert "선택 이미지의 캐릭터·탈것·장비·부속을 포함한 전체 전경을 필수로 잠그고" in JS


def test_phase16_reference_frontend_posts_reference_image():
    required = [
        "const useReference",
        "selectedLayerObject()",
        "'/api/generate-reference'",
        "payload.reference_image = imageObjectToDataUrl(referenceObj)",
        "샘플팩은 기준 이미지 레이어를 먼저 선택해야 합니다",
        "const baseReference",
        "canvas.setActiveObject(baseReference)",
    ]
    for token in required:
        assert token in JS


def test_phase16_reference_backend_endpoint_exists():
    required = [
        'if path == "/api/generate-reference"',
        "collect_codex_reference_sprite_b64",
        "build_reference_sprite_prompt",
        "reference_image is required",
        "input_image",
        "Reference image to preserve identity/style",
        "reference-image-sprite-generation",
    ]
    for token in required:
        assert token in SERVER
