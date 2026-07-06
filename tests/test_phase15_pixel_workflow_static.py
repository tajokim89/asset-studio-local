from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_phase15_pixel_workflow_ui_exists():
    required = [
        "phase15-pixel-workflow",
        "원클릭 워크플로우",
        "pixelFrameW",
        "pixelFrameH",
        "pixelWorkflowCleanBg",
        "pixelWorkflowPreview",
        "runPixelWorkflow",
        "grid/preview 자동",
    ]
    for token in required:
        assert token in INDEX


def test_phase15_pixel_workflow_logic_exists():
    required = [
        "function pixelPresetFrameCount",
        "function applyPixelWorkflowGridDefaults",
        "async function generateAiAsset",
        "async function runPixelWorkflow",
        "await generateAiAsset()",
        "await removeBgSelected('sheet')",
        "await buildAnimationPreview()",
        "pixelWorkflowCleanBg",
        "pixelWorkflowPreview",
    ]
    for token in required:
        assert token in JS


def test_phase15_buttons_are_wired():
    assert "$('runPixelWorkflow').onclick" in JS
    assert "applyPixelWorkflowGridDefaults()" in JS
    assert "$('generateBtn').onclick = () => generateAiAsset()" in JS
