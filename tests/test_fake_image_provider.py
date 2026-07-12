import hashlib
import tempfile
import unittest
from pathlib import Path

from asset_studio.provider import ImageProvider, ProviderArtifact, ProviderError, ProviderRequest
from tests.helpers.fake_image_provider import FakeImageProvider


class FakeImageProviderTests(unittest.TestCase):
    def test_success_is_deterministic_and_records_the_request(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = FakeImageProvider(Path(first_dir))
            second = FakeImageProvider(Path(second_dir))

            first_result = first.generate("small red potion", aspect_ratio="square")
            second_result = second.generate("small red potion", aspect_ratio="square")

            first_bytes = Path(first_result["image"]).read_bytes()
            second_bytes = Path(second_result["image"]).read_bytes()
            self.assertEqual(hashlib.sha256(first_bytes).digest(), hashlib.sha256(second_bytes).digest())
            self.assertTrue(first_result["success"])
            self.assertEqual(first_result["provider"], "fake-image-provider")
            self.assertEqual(first.calls, [{"prompt": "small red potion", "aspect_ratio": "square"}])

    def test_different_prompt_produces_a_different_png(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FakeImageProvider(Path(temp_dir))

            first = Path(provider.generate("red potion")["image"]).read_bytes()
            second = Path(provider.generate("blue potion")["image"]).read_bytes()

            self.assertNotEqual(hashlib.sha256(first).digest(), hashlib.sha256(second).digest())

    def test_failure_response_creates_no_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            provider = FakeImageProvider(
                output_dir,
                failure={"error": "provider unavailable", "error_type": "unavailable"},
            )

            result = provider.generate("anything")

            self.assertEqual(
                result,
                {
                    "success": False,
                    "error": "provider unavailable",
                    "error_type": "unavailable",
                    "provider": "fake-image-provider",
                },
            )
            self.assertEqual(list(output_dir.iterdir()), [])
            self.assertEqual(len(provider.calls), 1)

    def test_health_surface_never_generates_an_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FakeImageProvider(Path(temp_dir))

            self.assertTrue(provider.is_available())
            self.assertEqual(provider.default_model(), "fake-image-v1")
            self.assertEqual(
                provider.capabilities(),
                {"modalities": ["text", "image"], "max_reference_images": 4},
            )
            self.assertEqual(
                provider.health(),
                {
                    "status": "ready",
                    "available": True,
                    "provider": "fake-image-provider",
                },
            )
            self.assertEqual(provider.calls, [])

    def test_canonical_generate_is_deterministic_and_protocol_conformant(self):
        request = ProviderRequest(
            prompt="small red potion",
            aspect_ratio="portrait",
            request_id="canonical-001",
        )
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = FakeImageProvider(Path(first_dir))
            second = FakeImageProvider(Path(second_dir))

            first_artifact = first.generate(request)
            second_artifact = second.generate(request)

            self.assertIsInstance(first, ImageProvider)
            self.assertIsInstance(first_artifact, ProviderArtifact)
            self.assertEqual(first_artifact.kind, "image")
            self.assertEqual(first_artifact.request_id, "canonical-001")
            self.assertEqual(
                hashlib.sha256(Path(first_artifact.uri).read_bytes()).digest(),
                hashlib.sha256(Path(second_artifact.uri).read_bytes()).digest(),
            )
            self.assertEqual(first.calls, [{"operation": "generate", "request": request}])

    def test_canonical_edit_and_review_are_deterministic_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FakeImageProvider(Path(temp_dir))
            edit_request = ProviderRequest(
                prompt="make the potion blue",
                input_artifacts=("asset://potion.png",),
                mask_artifact="asset://mask.png",
                request_id="edit-001",
            )
            review_request = ProviderRequest(
                prompt="check transparent border",
                input_artifacts=("asset://candidate.png",),
                request_id="review-001",
            )

            edit = provider.edit(edit_request)
            review = provider.review(review_request)

            self.assertEqual(edit.kind, "image")
            self.assertTrue(Path(edit.uri).is_file())
            self.assertEqual(review.kind, "review")
            self.assertEqual(review.data["verdict"], "pass")
            self.assertEqual(review.request_id, "review-001")
            self.assertEqual(
                [call["operation"] for call in provider.calls],
                ["edit", "review"],
            )

    def test_canonical_failure_raises_but_legacy_failure_shape_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FakeImageProvider(
                Path(temp_dir),
                failure={"error": "provider unavailable", "error_type": "unavailable"},
            )

            with self.assertRaises(ProviderError) as raised:
                provider.generate(ProviderRequest(prompt="anything"))
            legacy = provider.generate("anything")

            self.assertEqual(raised.exception.code, "unavailable")
            self.assertEqual(
                legacy,
                {
                    "success": False,
                    "error": "provider unavailable",
                    "error_type": "unavailable",
                    "provider": "fake-image-provider",
                },
            )


if __name__ == "__main__":
    unittest.main()
