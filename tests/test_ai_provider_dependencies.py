from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQ = (ROOT / "requirements.txt").read_text(encoding="utf-8")


def test_image_provider_runtime_dependencies_are_declared():
    assert "httpx" in REQ
