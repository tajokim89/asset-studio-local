"""Task A5 regressions for legacy actor adaptation and endpoint validation."""

import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

import server


LEGACY_ACTOR_PAYLOAD = {
    "prompt": "small knight walking south",
    "preset": "pixel",
    "aspect_ratio": "square",
    "background_mode": "chroma_green",
    "animation_mode": "walk",
    "direction_mode": "single",
    "frame_count": 4,
    "target_direction": "S",
    "reference_direction": "S",
    "chroma_mode": "global",
}


def test_real_pre_a5_flat_actor_payload_defaults_to_sprite_character():
    normalized = server.normalize_asset_generation_payload(LEGACY_ACTOR_PAYLOAD)

    assert normalized["asset_family"] == "sprite"
    assert normalized["asset_type"] == "character"
    assert normalized["sprite"]["animation_mode"] == "walk"
    assert normalized["sprite"]["direction_mode"] == "single"
    assert normalized["sprite"]["frame_count"] == 4
    assert normalized["sprite"]["target_direction"] == "S"
    assert normalized["sprite"]["reference_direction"] == "S"
    assert normalized["sprite"]["chroma_mode"] == "global"


def test_real_pre_a5_flat_actor_payload_preserves_explicit_actor_type():
    normalized = server.normalize_asset_generation_payload({
        **LEGACY_ACTOR_PAYLOAD,
        "asset_type": "monster",
    })

    assert normalized["asset_family"] == "sprite"
    assert normalized["asset_type"] == "monster"


@pytest.mark.parametrize("payload", (
    {"prompt": "generic prompt only"},
    {"asset_family": "", "asset_type": "", "sprite": {}},
    {"asset_family": "sprite", "asset_type": "", "sprite": {}},
    {"asset_family": "bogus", "asset_type": "character", "animation_mode": "walk"},
))
def test_missing_or_malformed_structured_payload_does_not_acquire_character_semantics(payload):
    with pytest.raises(ValueError):
        server.normalize_asset_generation_payload(payload)


class _QuietHandler(server.Handler):
    def log_message(self, format, *args):
        pass


@pytest.fixture
def generation_server(monkeypatch):
    provider_calls = []

    def provider_must_not_load():
        provider_calls.append(True)
        raise AssertionError("validation must reject before provider loading")

    monkeypatch.setattr(server, "load_provider", provider_must_not_load)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _QuietHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address[1], provider_calls
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


@pytest.mark.parametrize("endpoint", ("/api/generate", "/api/generate-reference"))
@pytest.mark.parametrize("payload,expected_error", (
    ({"prompt": "generic prompt only"}, "asset_family"),
    ({"asset_family": "sprite", "asset_type": "", "sprite": {}}, "asset_type"),
    ({"asset_family": "invalid", "asset_type": "character"}, "asset_family"),
))
def test_generation_endpoints_return_json_400_for_family_validation(
    generation_server, endpoint, payload, expected_error,
):
    port, provider_calls = generation_server
    body = json.dumps(payload).encode("utf-8")
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(
            "POST", endpoint, body=body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
        )
        response = connection.getresponse()
        response_body = response.read()
    finally:
        connection.close()

    decoded = json.loads(response_body)
    assert response.status == 400
    content_type = response.getheader("Content-Type")
    assert content_type and content_type.startswith("application/json")
    assert decoded["success"] is False
    assert expected_error in decoded["error"]
    assert provider_calls == []
