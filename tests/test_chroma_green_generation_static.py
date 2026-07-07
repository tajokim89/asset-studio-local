from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text()
JS = (ROOT / "src" / "main.js").read_text()
SERVER = (ROOT / "server.py").read_text()


def test_generate_api_accepts_chroma_green_background_mode():
    assert 'background_mode: str = "none"' in SERVER
    assert 'background_mode = (background_mode or "none").strip()' in SERVER
    assert 'background_mode == "chroma_green"' in SERVER
    assert 'RGB(0,255,0) / #00FF00' in SERVER
    assert 'data.get("background_mode", "none")' in SERVER
    assert "force_chroma_green_background(src.read_bytes())" in SERVER
    assert '"background_mode": background_mode' in SERVER
    assert "def remove_chroma_green_bytes" in SERVER
    assert "subtle green spill/halo" in SERVER
    assert "green_ratio > 1.18" in SERVER
    assert "transparent_neighbors >= 5" in SERVER
    assert "chroma-green-key-" in SERVER


def test_object_generation_sends_chroma_green_background_mode():
    fn = JS.split("async function generateReplacementObject()", 1)[1].split("function fitReplacementTransform", 1)[0]
    assert "background_mode: 'chroma_green'" in fn


def test_ai_asset_generation_uses_chroma_green_except_background_preset():
    handler = JS.split("async function generateAiAsset()", 1)[1].split("async function runPixelWorkflow", 1)[0]
    assert "const backgroundMode = preset === 'background' ? 'none' : 'chroma_green';" in handler
    assert "background_mode: backgroundMode" in handler
    assert "#00FF00" in INDEX
    assert "RGB(0,255,0)" in INDEX
