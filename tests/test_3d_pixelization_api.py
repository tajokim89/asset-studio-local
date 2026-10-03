import base64
import io
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import server


ROOT = Path(__file__).resolve().parents[1]
SERVER_TEXT = (ROOT / "server.py").read_text(encoding="utf-8")


def png_data_url(image: Image.Image) -> str:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def test_pixelize_3d_frame_uses_reference_provider_and_returns_exact_game_frame():
    reference = Image.new("RGBA", (128, 128), (243, 245, 247, 255))
    reference.paste((90, 60, 30, 255), (42, 18, 86, 112))
    generated = Image.new("RGBA", (256, 256), (0, 255, 0, 255))
    generated.paste((55, 70, 90, 255), (82, 28, 174, 228))
    generated.paste((190, 125, 45, 255), (104, 62, 152, 126))
    generated_bytes = io.BytesIO()
    generated.save(generated_bytes, format="PNG")
    calls = []

    def fake_generator(prompt, *, image_url=None, reference_image_urls=None):
        calls.append((prompt, image_url, reference_image_urls))
        return generated_bytes.getvalue(), {
            "provider": "fake-hermes",
            "model": "fake-image-model",
            "reference_roles": ["direction_master"],
        }

    output, metadata = server.pixelize_3d_frame({
        "reference_image": png_data_url(reference),
        "direction": "S",
        "action": "walk",
        "pose_frame": 50,
        "resolution": 64,
        "palette_colors": 16,
        "style": "32-bit refined RPG",
        "shape_lock": 90,
        "pixel_simplify": 70,
    }, generator=fake_generator)

    assert len(calls) == 1
    prompt, input_image, extra_references = calls[0]
    assert "exactly ONE" in prompt
    assert "selected walk pose at 50%" in prompt
    assert "final 64x64 frame" in prompt
    assert input_image.startswith("data:image/png;base64,")
    assert extra_references is None

    image = Image.open(io.BytesIO(output)).convert("RGBA")
    assert image.size == (64, 64)
    assert image.getpixel((0, 0))[3] == 0
    assert image.getchannel("A").getbbox() is not None
    visible_colors = {(r, g, b) for r, g, b, a in image.getdata() if a}
    assert len(visible_colors) <= 16
    assert metadata["provider"] == "fake-hermes"
    assert metadata["model"] == "fake-image-model"
    assert len(metadata["artifact_digest"]) == 64
    assert metadata["qa"]["frame"]["status"] == "PASS"


def test_3d_pixel_proof_contract_rejects_unsupported_settings():
    cases = [
        ("direction", "N", "S direction only"),
        ("resolution", 72, "48, 64, or 96"),
        ("palette_colors", 20, "16, 24, or 32"),
        ("action", "attack", "idle, walk, or run"),
    ]
    for field, value, message in cases:
        reference = png_data_url(Image.new("RGBA", (32, 32), (20, 30, 40, 255)))
        payload = {
            "reference_image": reference,
            "direction": "S",
            "action": "idle",
            "resolution": 64,
            "palette_colors": 24,
            "style": "32-bit refined RPG",
        }
        payload[field] = value
        try:
            server.normalize_3d_pixel_proof_payload(payload)
        except ValueError as error:
            assert message in str(error)
        else:
            raise AssertionError(f"{field}={value!r} should be rejected")


def test_server_routes_and_async_jobs_retire_3d_pixel_proof_endpoint():
    # Helpers remain available for existing offline scripts, not the application API.
    assert 'if path == "/api/pixelize-3d-frame"' not in SERVER_TEXT
    assert '"/api/pixelize-3d-frame",' not in SERVER_TEXT
    assert "pixelize_3d_frame(data)" not in SERVER_TEXT


def test_server_routes_and_async_jobs_retire_local_comfy_action_endpoint():
    assert 'if path == "/api/local-3d-action-sheet"' not in SERVER_TEXT
    assert '"/api/local-3d-action-sheet",' not in SERVER_TEXT
    assert "generate_local_action_sheet(data)" not in SERVER_TEXT
    assert "from asset_studio.local_3d_model_pipeline" not in SERVER_TEXT


def test_hermes_resolver_supports_windows_local_appdata_install_location():
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        repo = root / "hermes" / "hermes-agent"
        provider = repo / server.HERMES_PROVIDER_RELATIVE
        provider.parent.mkdir(parents=True)
        provider.write_text("", encoding="utf-8")
        environment = {
            "HERMES_REPO": "",
            "HERMES_HOME": "",
            "HERMES_COMMAND": "",
            "LOCALAPPDATA": str(root),
        }
        with patch.dict(server.os.environ, environment, clear=False), patch.object(
            server.Path, "home", return_value=root / "empty-home"
        ):
            assert server.resolve_hermes_repo() == repo
