from __future__ import annotations

import copy
import unittest

from asset_studio.recipes import (
    RecipeRegistryError,
    load_recipe_registry,
    migrate_legacy_selection,
    recipe_by_id,
    validate_recipe_registry,
)


PRODUCTION_IDS = {
    "sprite.character",
    "sprite.effect",
    "ui.button",
    "object.item",
}
ALIAS_IDS = {
    "sprite.monster",
    "sprite.npc",
    "object.equipment",
    "object.weapon",
    "object.loot",
    "object.prop",
}
LAB_IDS = {
    "tile.floor",
    "tile.wall",
    "tile.corner",
    "tile.door",
    "tile.terrain",
    "tile.decal",
    "tile.autotile",
    "tile.tileset",
    "ui.main_panel",
    "ui.inner_panel",
    "ui.popup",
    "ui.card",
    "ui.slot",
    "ui.badge",
    "ui.hud_chip",
    "ui.gauge",
    "ui.icon",
    "ui.cursor",
    "object.furniture",
    "object.machine",
    "object.interactable",
    "object.destructible",
}
RESULT_KEYS = {
    "classification",
    "channel",
    "recipe_id",
    "transport",
    "variant",
}


class RecipeMigrationTests(unittest.TestCase):
    def test_current_32_entry_matrix_migrates_without_accidental_promotion(self):
        registry = load_recipe_registry()
        expected_classification = {
            **{legacy_id: "production" for legacy_id in PRODUCTION_IDS},
            **{legacy_id: "alias" for legacy_id in ALIAS_IDS},
            **{legacy_id: "lab" for legacy_id in LAB_IDS},
        }

        self.assertEqual(len(registry["legacy_subtypes"]), 32)
        self.assertEqual(
            {entry["legacy_id"] for entry in registry["legacy_subtypes"]},
            set(expected_classification),
        )

        for legacy in registry["legacy_subtypes"]:
            with self.subTest(legacy_id=legacy["legacy_id"]):
                classification = expected_classification[legacy["legacy_id"]]
                self.assertEqual(legacy["classification"], classification)

                migrated = migrate_legacy_selection(
                    registry, legacy["family"], legacy["type"]
                )
                self.assertEqual(set(migrated), RESULT_KEYS)
                self.assertEqual(migrated["classification"], classification)
                self.assertEqual(migrated["recipe_id"], legacy["recipe_id"])
                self.assertEqual(migrated["variant"], legacy["variant"])
                self.assertEqual(set(migrated["transport"]), {"family", "type"})

                if classification == "lab":
                    self.assertEqual(migrated["channel"], "lab")
                else:
                    recipe = recipe_by_id(registry, legacy["recipe_id"])
                    self.assertEqual(migrated["channel"], "production")
                    self.assertEqual(migrated["transport"], recipe["transport"])

    def test_production_and_alias_use_the_recipe_canonical_transport(self):
        registry = load_recipe_registry()

        self.assertEqual(
            migrate_legacy_selection(registry, "sprite", "monster"),
            {
                "classification": "alias",
                "channel": "production",
                "recipe_id": "actor-animation",
                "transport": {"family": "sprite", "type": "character"},
                "variant": "monster",
            },
        )
        self.assertEqual(
            migrate_legacy_selection(registry, "ui", "button"),
            {
                "classification": "production",
                "channel": "production",
                "recipe_id": "ui-component",
                "transport": {"family": "ui", "type": "button"},
                "variant": "button",
            },
        )

    def test_lab_result_stays_lab_with_or_without_a_linked_recipe(self):
        registry = load_recipe_registry()

        self.assertEqual(
            migrate_legacy_selection(registry, "tile", "autotile"),
            {
                "classification": "lab",
                "channel": "lab",
                "recipe_id": "tile-autotile",
                "transport": {"family": "tile", "type": "autotile"},
                "variant": "autotile",
            },
        )
        self.assertEqual(
            migrate_legacy_selection(registry, "tile", "floor"),
            {
                "classification": "lab",
                "channel": "lab",
                "recipe_id": None,
                "transport": {"family": "tile", "type": "floor"},
                "variant": None,
            },
        )

    def test_unknown_and_retired_selections_fail_closed(self):
        registry = load_recipe_registry()
        with self.assertRaises(RecipeRegistryError):
            migrate_legacy_selection(registry, "unknown", "missing")

        retired_registry = copy.deepcopy(registry)
        retired_registry["legacy_subtypes"].append(
            {
                "legacy_id": "test_fixture.retired",
                "family": "test_fixture",
                "type": "retired",
                "classification": "retired",
                "recipe_id": None,
                "variant": None,
                "migration_action": "remove",
                "reason": "Synthetic retired selection used to lock fail-closed behavior.",
            }
        )
        retired_registry = validate_recipe_registry(retired_registry)
        with self.assertRaises(RecipeRegistryError):
            migrate_legacy_selection(retired_registry, "test_fixture", "retired")


if __name__ == "__main__":
    unittest.main()
