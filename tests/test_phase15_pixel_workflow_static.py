import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def _function_body(name: str) -> str:
    match = re.search(rf"\bfunction\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", JS)
    assert match, f"Expected JavaScript function {name}()"
    opening = match.end() - 1
    depth = 0
    quote = None
    escaped = False
    for index in range(opening, len(JS)):
        char = JS[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return JS[opening + 1:index]
    raise AssertionError(f"Unclosed JavaScript function {name}()")


def test_phase15_pixel_workflow_ui_exists():
    required = [
        "pixel-workflow-panel",
        "자동 처리",
        "pixelFrameW",
        "pixelFrameH",
        "pixelWorkflowCleanBg",
        "runPixelWorkflow",
        "생성 → 배경 제거 → 그리드 값 맞춤",
        "애니메이션 확인은 오른쪽 스프라이트 도구에서 실행합니다.",
    ]
    for token in required:
        assert token in INDEX


def test_phase15_pixel_workflow_logic_exists():
    required = [
        "function pixelPresetFrameCount",
        "function applyPixelWorkflowGridDefaults",
        "function generateAiAsset",
        "async function runPixelWorkflow",
        "pixelWorkflowCleanBg",
    ]
    for token in required:
        assert token in JS
    generate = _function_body("generateAiAsset")
    workflow = _function_body("runPixelWorkflow")
    assert "const request = (async () =>" in generate
    assert "return request;" in generate
    assert "const result = await generateAiAsset()" in workflow
    assert "await removeBgSelected('chroma_green'" in workflow
    assert "spriteSlices = buildGridSpriteSlices()" in workflow
    assert "그리드 값 자동 설정됨" in workflow


def test_phase15_buttons_are_wired():
    assert "$('runPixelWorkflow').onclick" in JS
    assert "applyPixelWorkflowGridDefaults()" in JS
    assert "if ($('generateBtn')) $('generateBtn').onclick = () => generateAiAsset()" in JS
