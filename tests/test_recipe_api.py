from __future__ import annotations

import io
import json
import unittest
from unittest import mock

import server
from asset_studio.recipes import RecipeRegistryError


class RecipeApiTests(unittest.TestCase):
    def _handler(self):
        handler = server.Handler.__new__(server.Handler)
        handler.path = "/api/recipes"
        handler.command = "GET"
        handler.headers = {}
        handler.wfile = io.BytesIO()
        handler.send_response = mock.Mock()
        handler.send_header = mock.Mock()
        handler.end_headers = mock.Mock()
        return handler

    def test_get_recipes_returns_the_validated_registry(self):
        registry = {
            "schema_version": "asset-studio.asset-recipes/v1",
            "quality_rubric_version": "quality-rubric-v1",
            "recipes": [],
            "legacy_subtypes": [],
        }
        handler = self._handler()

        with mock.patch.object(server, "load_recipe_registry", return_value=registry):
            handler.do_GET()

        handler.send_response.assert_called_once_with(200)
        self.assertEqual(json.loads(handler.wfile.getvalue()), registry)

    def test_get_recipes_loads_the_real_registry_without_a_provider_call(self):
        handler = self._handler()

        handler.do_GET()

        handler.send_response.assert_called_once_with(200)
        payload = json.loads(handler.wfile.getvalue())
        self.assertEqual(payload["schema_version"], "asset-studio.asset-recipes/v1")
        self.assertEqual(len(payload["recipes"]), 5)
        self.assertEqual(len(payload["legacy_subtypes"]), 32)

    def test_get_actor_output_profile_returns_the_validated_action_catalog(self):
        handler = self._handler()
        handler.path = "/api/output-profiles/generic-pixel-actor-v1"

        handler.do_GET()

        handler.send_response.assert_called_once_with(200)
        payload = json.loads(handler.wfile.getvalue())
        self.assertEqual("generic-pixel-actor-v1", payload["id"])
        self.assertIn("dodge", {action["id"] for action in payload["actions"]})

    def test_output_profile_route_rejects_path_input_without_leaking_details(self):
        handler = self._handler()
        handler.path = "/api/output-profiles/..%2Fprivate"

        handler.do_GET()

        handler.send_response.assert_called_once_with(404)
        self.assertEqual(
            {"success": False, "error": "Output profile unavailable"},
            json.loads(handler.wfile.getvalue()),
        )

    def test_get_recipes_fails_closed_without_exposing_registry_details(self):
        handler = self._handler()
        private_detail = "/Users/example/private/contracts/asset-recipes.json"

        with mock.patch.object(
            server,
            "load_recipe_registry",
            side_effect=RuntimeError(private_detail),
        ):
            handler.do_GET()

        handler.send_response.assert_called_once_with(503)
        payload = json.loads(handler.wfile.getvalue())
        self.assertEqual(
            payload,
            {"success": False, "error": "Recipe registry unavailable"},
        )
        self.assertNotIn(private_detail, handler.wfile.getvalue().decode("utf-8"))

    def test_non_recipe_get_still_uses_static_file_handler(self):
        handler = self._handler()
        handler.path = "/index.html"

        with mock.patch.object(server.SimpleHTTPRequestHandler, "do_GET") as static_get:
            handler.do_GET()

        static_get.assert_called_once_with()

    def test_generation_post_sanitizes_registry_failure_before_provider_loading(self):
        private_detail = "/Users/example/private/contracts/asset-recipes.json"
        body = json.dumps(
            {"asset_family": "sprite", "asset_type": "character", "sprite": {}}
        ).encode("utf-8")

        for path in ("/api/generate", "/api/generate-reference"):
            with self.subTest(path=path):
                handler = self._handler()
                handler.path = path
                handler.command = "POST"
                handler.headers = {"Content-Length": str(len(body))}
                handler.rfile = io.BytesIO(body)
                provider = mock.Mock(side_effect=AssertionError("provider must not load"))

                with mock.patch.object(
                    server,
                    "load_recipe_registry",
                    side_effect=RecipeRegistryError(private_detail),
                ), mock.patch.object(server, "load_provider", provider):
                    handler.do_POST()

                handler.send_response.assert_called_once_with(503)
                payload = json.loads(handler.wfile.getvalue())
                self.assertEqual(
                    payload,
                    {"success": False, "error": "Recipe registry unavailable"},
                )
                self.assertNotIn(private_detail, handler.wfile.getvalue().decode("utf-8"))
                provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()
