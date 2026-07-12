import unittest
from pathlib import Path

from asset_studio.provider import (
    ImageProvider,
    ProviderArtifact,
    ProviderError,
    ProviderRequest,
)


class ProviderContractTests(unittest.TestCase):
    def test_request_is_validated_and_defensively_frozen(self):
        options = {"seed": 7, "style": {"palette": ["red", "blue"]}}

        request = ProviderRequest(
            prompt="small red potion",
            input_artifacts=["asset://reference"],
            options=options,
            request_id="request-001",
        )
        options["seed"] = 99
        options["style"]["palette"].append("green")

        self.assertEqual(request.input_artifacts, ("asset://reference",))
        self.assertEqual(request.options["seed"], 7)
        self.assertEqual(request.options["style"]["palette"], ("red", "blue"))
        with self.assertRaises(TypeError):
            request.options["seed"] = 1

    def test_request_rejects_malformed_provider_neutral_values(self):
        invalid = (
            {"prompt": "   "},
            {"prompt": "valid", "aspect_ratio": ""},
            {"prompt": "valid", "model": ""},
            {"prompt": "valid", "input_artifacts": [""]},
            {"prompt": "valid", "mask_artifact": ""},
            {"prompt": "valid", "options": {"path": Path("private.png")}},
        )

        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaises((TypeError, ValueError)):
                    ProviderRequest(**values)

    def test_artifact_requires_exactly_one_payload_surface(self):
        image = ProviderArtifact(
            kind="image",
            provider="fake-image-provider",
            media_type="image/png",
            uri="asset://generated.png",
            metadata={"width": 16, "height": 16},
        )
        review = ProviderArtifact(
            kind="review",
            provider="fake-image-provider",
            media_type="application/json",
            data={"verdict": "pass", "checks": ["alpha"]},
        )

        self.assertEqual(image.uri, "asset://generated.png")
        self.assertEqual(review.data["checks"], ("alpha",))
        with self.assertRaises(TypeError):
            image.metadata["width"] = 32
        for values in (
            {},
            {"uri": "asset://x", "data": {"verdict": "pass"}},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    ProviderArtifact(
                        kind="image",
                        provider="fake-image-provider",
                        media_type="image/png",
                        **values,
                    )

    def test_provider_error_has_stable_machine_readable_shape(self):
        error = ProviderError(
            "unavailable",
            "provider unavailable",
            provider="fake-image-provider",
            retryable=True,
            details={"attempt": 1},
        )

        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(str(error), "provider unavailable")
        self.assertEqual(
            error.as_dict(),
            {
                "code": "unavailable",
                "message": "provider unavailable",
                "provider": "fake-image-provider",
                "retryable": True,
                "details": {"attempt": 1},
            },
        )

    def test_protocol_is_runtime_checkable_and_rejects_incomplete_objects(self):
        class IncompleteProvider:
            name = "incomplete"
            display_name = "Incomplete"

            def health(self):
                return {}

        self.assertFalse(isinstance(IncompleteProvider(), ImageProvider))


if __name__ == "__main__":
    unittest.main()
