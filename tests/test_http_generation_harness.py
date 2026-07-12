import tempfile
import unittest
from pathlib import Path

from tests.helpers.fake_image_provider import FakeImageProvider
from tests.helpers.http_generation_harness import GenerationHttpHarness


def object_payload():
    return {
        "asset_family": "object",
        "asset_type": "interactable",
        "prompt": "small red potion",
        "output": {"width": 16, "height": 16, "background": "transparent"},
        "object": {
            "usage": "world",
            "identity": {"subtype": "interactable", "form": "potion"},
            "view": "three-quarter",
            "scale": {"basis": "pixel"},
            "source": {
                "canvas": {"width": 16, "height": 16},
                "padding": {"top": 0, "right": 0, "bottom": 0, "left": 0},
            },
            "placement": {
                "pivot": {"x": 0.5, "y": 1},
                "ground_point": {"x": 0.5, "y": 1},
                "y_sort_point": {"x": 0.5, "y": 1},
                "snap_points": [],
            },
            "shadow": {"mode": "none", "baked": False},
            "states": [],
            "variants": [],
            "collision": {},
            "interaction": {},
            "custom_properties": {},
        },
    }


class GenerationHttpHarnessTests(unittest.TestCase):
    def test_generate_success_crosses_handler_provider_postprocess_and_json_response(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            provider = FakeImageProvider(root / "provider")
            harness = GenerationHttpHarness(provider, root / "generated")

            response = harness.post_json("/api/generate", object_payload())
            payload = response.json()

            self.assertEqual(response.status, 200)
            self.assertTrue(payload["success"])
            self.assertEqual(payload["provider"], "fake-image-provider")
            self.assertEqual(payload["qa"]["status"], "PASS")
            self.assertEqual(len(provider.calls), 1)
            self.assertEqual(len(list((root / "generated").glob("*.png"))), 1)

    def test_invalid_payload_is_rejected_before_provider_loading(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            provider = FakeImageProvider(root / "provider")
            harness = GenerationHttpHarness(provider, root / "generated")

            response = harness.post_json("/api/generate", {"prompt": "missing family"})

            self.assertEqual(response.status, 400)
            self.assertFalse(response.json()["success"])
            self.assertEqual(provider.calls, [])

    def test_provider_failure_returns_json_500_without_generated_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            provider = FakeImageProvider(
                root / "provider",
                failure={"error": "provider unavailable", "error_type": "unavailable"},
            )
            harness = GenerationHttpHarness(provider, root / "generated")

            response = harness.post_json("/api/generate", object_payload())

            self.assertEqual(response.status, 500)
            self.assertEqual(response.json()["error"], "provider unavailable")
            self.assertEqual(list((root / "generated").glob("*.png")), [])
            self.assertEqual(len(provider.calls), 1)


if __name__ == "__main__":
    unittest.main()
