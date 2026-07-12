import json
import unittest

from asset_studio.hermes_provider import HermesProviderAdapter
from asset_studio.provider import (
    ImageProvider,
    ProviderArtifact,
    ProviderError,
    ProviderRequest,
)


class _CapturedHermesBackend:
    name = "openai-codex"
    display_name = "OpenAI (Codex auth)"

    def __init__(self, *, capabilities=None, result=None, failure=None):
        self._capabilities = capabilities or {
            "modalities": ["text", "image"],
            "max_reference_images": 4,
            "supports_edit_mask": True,
        }
        self.result = result or {
            "success": True,
            "image": "asset://generated/orc.png",
            "model": "gpt-image-2-medium",
        }
        self.failure = failure
        self.calls = []

    def is_available(self):
        return True

    def capabilities(self):
        return dict(self._capabilities)

    def default_model(self):
        return "gpt-image-2-medium"

    def generate(self, prompt, aspect_ratio="square", **kwargs):
        self.calls.append(
            {"prompt": prompt, "aspect_ratio": aspect_ratio, **kwargs}
        )
        if self.failure is not None:
            raise self.failure
        return dict(self.result)


class HermesProviderAdapterTests(unittest.TestCase):
    def test_multi_reference_order_and_roles_reach_hermes_unchanged(self):
        backend = _CapturedHermesBackend()
        adapter = HermesProviderAdapter(backend)
        request = ProviderRequest(
            prompt="SE black orc walk contact pose",
            aspect_ratio="square",
            input_artifacts=(
                "asset://identity-master.png",
                "asset://direction-master-se.png",
                "asset://walk-left-contact.png",
            ),
            options={
                "reference_roles": [
                    "identity_master",
                    "direction_master",
                    "pose_guide",
                ],
                "api_key": "sk-must-not-be-forwarded",
            },
            request_id="frame-001",
        )

        artifact = adapter.generate(request)

        self.assertIsInstance(adapter, ImageProvider)
        self.assertIsInstance(artifact, ProviderArtifact)
        self.assertEqual(
            backend.calls,
            [
                {
                    "prompt": "SE black orc walk contact pose",
                    "aspect_ratio": "square",
                    "image_url": "asset://identity-master.png",
                    "reference_image_urls": [
                        "asset://direction-master-se.png",
                        "asset://walk-left-contact.png",
                    ],
                    "reference_roles": [
                        "identity_master",
                        "direction_master",
                        "pose_guide",
                    ],
                }
            ],
        )
        self.assertEqual(artifact.provider, "hermes")
        self.assertEqual(artifact.uri, "asset://generated/orc.png")
        self.assertEqual(artifact.request_id, "frame-001")
        self.assertEqual(
            artifact.metadata["reference_roles"],
            ("identity_master", "direction_master", "pose_guide"),
        )
        self.assertEqual(artifact.metadata["input_artifact_count"], 3)
        self.assertNotIn("api_key", backend.calls[0])
        self.assertNotIn("sk-must-not-be-forwarded", json.dumps(dict(artifact.metadata)))

    def test_supported_mask_is_forwarded_only_to_edit_surface(self):
        backend = _CapturedHermesBackend()
        adapter = HermesProviderAdapter(backend)
        request = ProviderRequest(
            prompt="repair only the malformed right hand",
            input_artifacts=("asset://candidate.png",),
            mask_artifact="asset://right-hand-mask.png",
            options={"reference_roles": ["candidate_frame"]},
        )

        artifact = adapter.edit(request)

        self.assertEqual(
            backend.calls[0]["mask_image_url"], "asset://right-hand-mask.png"
        )
        self.assertEqual(backend.calls[0]["image_url"], "asset://candidate.png")
        self.assertTrue(artifact.metadata["mask_applied"])
        self.assertEqual(artifact.metadata["operation"], "edit")

    def test_reference_limit_fails_closed_without_clamping_or_calling_backend(self):
        backend = _CapturedHermesBackend(
            capabilities={
                "modalities": ["text", "image"],
                "max_reference_images": 2,
                "supports_edit_mask": True,
            }
        )
        adapter = HermesProviderAdapter(backend)
        request = ProviderRequest(
            prompt="three inputs are required",
            input_artifacts=("asset://a", "asset://b", "asset://c"),
            options={"reference_roles": ["identity", "direction", "pose"]},
        )

        with self.assertRaises(ProviderError) as caught:
            adapter.generate(request)

        self.assertEqual(caught.exception.code, "unsupported")
        self.assertEqual(
            caught.exception.as_dict()["details"],
            {"requested_reference_images": 3, "max_reference_images": 2},
        )
        self.assertEqual(backend.calls, [])

    def test_image_and_mask_capabilities_are_required_explicitly(self):
        cases = (
            (
                {"modalities": ["image"], "max_reference_images": 1},
                ProviderRequest(prompt="text-only request"),
            ),
            (
                {"modalities": ["text"], "max_reference_images": 0},
                ProviderRequest(
                    prompt="image conditioned",
                    input_artifacts=("asset://identity",),
                    options={"reference_roles": ["identity_master"]},
                ),
            ),
            (
                {"modalities": ["text", "image"], "max_reference_images": 2},
                ProviderRequest(
                    prompt="masked edit",
                    input_artifacts=("asset://candidate",),
                    mask_artifact="asset://mask",
                    options={"reference_roles": ["candidate_frame"]},
                ),
            ),
        )

        for capabilities, request in cases:
            with self.subTest(capabilities=capabilities):
                backend = _CapturedHermesBackend(capabilities=capabilities)
                adapter = HermesProviderAdapter(backend)
                with self.assertRaises(ProviderError) as caught:
                    if request.input_artifacts:
                        adapter.edit(request)
                    else:
                        adapter.generate(request)
                self.assertEqual(caught.exception.code, "unsupported")
                self.assertEqual(backend.calls, [])

    def test_role_metadata_must_be_ordered_and_aligned(self):
        invalid_options = (
            {"reference_roles": ["identity_master"]},
            {"reference_roles": ["identity_master", " "]},
            {"reference_roles": "identity_master"},
        )

        for options in invalid_options:
            with self.subTest(options=options):
                backend = _CapturedHermesBackend()
                adapter = HermesProviderAdapter(backend)
                request = ProviderRequest(
                    prompt="bad metadata",
                    input_artifacts=("asset://identity", "asset://pose"),
                    options=options,
                )
                with self.assertRaises(ProviderError) as caught:
                    adapter.generate(request)
                self.assertEqual(caught.exception.code, "invalid_request")
                self.assertEqual(backend.calls, [])

    def test_missing_roles_receive_stable_provider_neutral_defaults(self):
        backend = _CapturedHermesBackend()
        adapter = HermesProviderAdapter(backend)

        artifact = adapter.generate(
            ProviderRequest(
                prompt="generic edit",
                input_artifacts=("asset://primary", "asset://reference"),
            )
        )

        self.assertEqual(
            backend.calls[0]["reference_roles"], ["primary", "reference_1"]
        )
        self.assertEqual(
            artifact.metadata["reference_roles"], ("primary", "reference_1")
        )

    def test_upstream_failures_do_not_expose_credentials_or_private_paths(self):
        secrets = (
            RuntimeError(
                "Bearer secret-token from /Users/example/.hermes/auth.json"
            ),
            None,
        )

        for failure in secrets:
            with self.subTest(failure=failure):
                result = (
                    {
                        "success": False,
                        "error_type": "auth_required",
                        "error": "sk-secret at /Users/example/private/key",
                    }
                    if failure is None
                    else None
                )
                backend = _CapturedHermesBackend(result=result, failure=failure)
                adapter = HermesProviderAdapter(backend)
                with self.assertRaises(ProviderError) as caught:
                    adapter.generate(ProviderRequest(prompt="safe request"))
                serialized = json.dumps(caught.exception.as_dict())
                self.assertNotIn("secret", serialized)
                self.assertNotIn("/Users/", serialized)
                self.assertNotIn("Bearer", serialized)
                self.assertEqual(len(backend.calls), 1)

    def test_health_failure_is_generic_and_does_not_raise(self):
        class BrokenBackend(_CapturedHermesBackend):
            def is_available(self):
                raise RuntimeError("/Users/example/.hermes/credentials.json")

        health = HermesProviderAdapter(BrokenBackend()).health()

        self.assertEqual(
            health,
            {
                "status": "unavailable",
                "available": False,
                "provider": "hermes",
                "reason": "provider_health_failed",
            },
        )
        self.assertNotIn("/Users/", json.dumps(health))


if __name__ == "__main__":
    unittest.main()
