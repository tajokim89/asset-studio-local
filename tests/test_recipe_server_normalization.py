from __future__ import annotations

import unittest
import inspect
from unittest import mock

import server


def registry_with(*entries):
    return {
        "schema_version": "asset-studio.asset-recipes/v1",
        "quality_rubric_version": "quality-rubric-v1",
        "recipes": [],
        "legacy_subtypes": list(entries),
    }


def legacy(family, type_, classification, recipe_id=None):
    return {
        "legacy_id": f"{family}.{type_}",
        "family": family,
        "type": type_,
        "classification": classification,
        "recipe_id": recipe_id,
        "variant": type_ if recipe_id else None,
        "migration_action": {
            "production": "use_recipe",
            "alias": "normalize_alias",
            "lab": "keep_lab",
            "retired": "remove",
        }[classification],
        "reason": "test fixture",
    }


class RecipeServerNormalizationTests(unittest.TestCase):
    def test_generation_taxonomy_is_derived_from_non_retired_registry_entries(self):
        registry = registry_with(
            legacy("object", "item", "production", "static-transparent-object"),
            legacy("object", "weapon", "alias", "static-transparent-object"),
            legacy("tile", "autotile", "lab", "tile-autotile"),
            legacy("ui", "popup", "retired"),
        )

        families, actor_types = server.recipe_generation_taxonomy(registry)

        self.assertEqual(families, {"object": {"item", "weapon"}, "tile": {"autotile"}})
        self.assertEqual(actor_types, set())

    def test_normalizer_accepts_production_alias_and_lab_registry_members(self):
        registry = registry_with(
            legacy("ui", "button", "production", "ui-component"),
            legacy("ui", "badge", "alias", "ui-component"),
            legacy("ui", "popup", "lab"),
        )

        with mock.patch.object(server, "load_recipe_registry", return_value=registry):
            production = server.normalize_asset_generation_payload(
                {"asset_family": "ui", "asset_type": "button", "ui": {}}
            )
            alias = server.normalize_asset_generation_payload(
                {"asset_family": "ui", "asset_type": "badge", "ui": {}}
            )
            lab = server.normalize_asset_generation_payload(
                {"asset_family": "ui", "asset_type": "popup", "ui": {}}
            )

        self.assertEqual(production["asset_type"], "button")
        self.assertEqual(alias["asset_type"], "badge")
        self.assertEqual(lab["asset_type"], "popup")

    def test_normalizer_rejects_retired_or_unregistered_values(self):
        registry = registry_with(
            legacy("ui", "button", "production", "ui-component"),
            legacy("ui", "badge", "retired", "ui-component"),
        )

        with mock.patch.object(server, "load_recipe_registry", return_value=registry):
            for type_ in ("badge", "popup"):
                with self.subTest(type=type_), self.assertRaisesRegex(ValueError, "asset_type"):
                    server.normalize_asset_generation_payload(
                        {"asset_family": "ui", "asset_type": type_, "ui": {}}
                    )

    def test_actor_compatibility_types_come_from_actor_recipe_aliases(self):
        registry = registry_with(
            legacy("sprite", "character", "production", "actor-animation"),
            legacy("sprite", "monster", "alias", "actor-animation"),
            legacy("sprite", "effect", "production", "vfx-sequence"),
        )

        families, actor_types = server.recipe_generation_taxonomy(registry)

        self.assertEqual(families["sprite"], {"character", "monster", "effect"})
        self.assertEqual(actor_types, {"character", "monster"})

    def test_downstream_recipe_route_resolves_new_aliases_without_hardcoded_actor_types(self):
        registry = registry_with(
            legacy("sprite", "hero", "alias", "actor-animation"),
            legacy("sprite", "burst", "alias", "vfx-sequence"),
            legacy("tile", "floor", "lab"),
        )

        self.assertEqual(
            server.recipe_id_for_asset_selection("sprite", "hero", registry),
            "actor-animation",
        )
        self.assertEqual(
            server.recipe_id_for_asset_selection("sprite", "burst", registry),
            "vfx-sequence",
        )
        self.assertIsNone(server.recipe_id_for_asset_selection("tile", "floor", registry))
        with self.assertRaisesRegex(ValueError, "selection"):
            server.recipe_id_for_asset_selection("sprite", "missing", registry)

        endpoint_source = inspect.getsource(server.Handler.do_POST)
        self.assertIn("recipe_id_for_asset_selection", endpoint_source)
        self.assertNotIn('{"character", "monster", "npc"}', endpoint_source)


if __name__ == "__main__":
    unittest.main()
