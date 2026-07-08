from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def test_phase14_animation_preview_ui_exists():
    required = [
        "phase15-pixel-workflow",
        "애니메이션 확인",
        "animFrameCount",
        "animFps",
        "animMode",
        "buildAnimationPreview",
        "stopAnimationPreview",
        "animationPreviewStage",
        "animationFrameStrip",
    ]
    for token in required:
        assert token in INDEX


def test_phase14_animation_preview_logic_exists():
    required = [
        "let animationPreviewTimer",
        "function buildAnimationFramesFromGrid",
        "function renderAnimationFrameStrip",
        "function playAnimationPreview",
        "function stopAnimationPreview",
        "function buildAnimationPreview",
        "pingpong",
        "frameCanvas.toDataURL('image/png')",
        "animationPreviewFrames",
    ]
    for token in required:
        assert token in JS


def test_phase14_animation_controls_are_wired():
    assert "$('buildAnimationPreview').onclick" in JS
    assert "$('stopAnimationPreview').onclick" in JS
    assert "buildAnimationPreview().catch" in JS
