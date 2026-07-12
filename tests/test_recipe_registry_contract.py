from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "contracts" / "asset-recipes.json"
MAIN_JS_PATH = ROOT / "src" / "main.js"
MIGRATION_DOC_PATH = ROOT / "docs" / "history" / "artifacts" / "RECIPE_MIGRATION.md"


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def load_javascript_taxonomy() -> set[str]:
    source = MAIN_JS_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"const ASSET_FAMILY_SUBTYPES = \{(?P<body>.*?)\n\};",
        source,
        re.DOTALL,
    )
    if not match:
        raise AssertionError("ASSET_FAMILY_SUBTYPES not found in src/main.js")

    taxonomy: set[str] = set()
    families = re.findall(r"^\s*(\w+):\s*\[([^\]]*)\],?$", match.group("body"), re.MULTILINE)
    for family, raw_subtypes in families:
        for subtype in re.findall(r"'([^']+)'", raw_subtypes):
            legacy_id = f"{family}.{subtype}"
            if legacy_id in taxonomy:
                raise AssertionError(f"duplicate JavaScript subtype: {legacy_id}")
            taxonomy.add(legacy_id)
    return taxonomy


class RecipeRegistryContractTests(unittest.TestCase):
    def test_v1_has_four_production_recipes_and_one_explicit_lab_recipe(self):
        registry = load_registry()
        recipes = registry["recipes"]
        production = [recipe for recipe in recipes if recipe["channel"] == "production"]
        lab = [recipe for recipe in recipes if recipe["channel"] == "lab"]

        self.assertEqual(registry["schema_version"], "asset-studio.asset-recipes/v1")
        self.assertEqual(registry["quality_rubric_version"], "quality-rubric-v1")
        self.assertEqual(
            {recipe["id"] for recipe in production},
            {
                "static-transparent-object",
                "actor-animation",
                "ui-component",
                "vfx-sequence",
            },
        )
        self.assertEqual({recipe["id"] for recipe in lab}, {"tile-autotile"})
        self.assertEqual(len({recipe["id"] for recipe in recipes}), len(recipes))

    def test_contract_only_recipes_do_not_claim_unimplemented_readiness(self):
        registry = load_registry()
        expected_stages = [
            "generate",
            "local_qa",
            "visual_qa",
            "user_approval",
            "edit",
            "export",
        ]

        for recipe in registry["recipes"]:
            with self.subTest(recipe=recipe["id"]):
                self.assertEqual(recipe["readiness"], "contract_only")
                self.assertEqual(recipe["required_stages"], expected_stages)
                self.assertNotEqual(recipe["readiness"], "ready")

    def test_production_recipes_cover_all_six_golden_jobs_without_provider_lock_in(self):
        registry = load_registry()
        production = [recipe for recipe in registry["recipes"] if recipe["channel"] == "production"]
        golden_jobs = [job_id for recipe in production for job_id in recipe["golden_job_ids"]]

        self.assertEqual(
            golden_jobs,
            [
                "static-object",
                "actor-idle",
                "actor-walk",
                "actor-attack",
                "ui-button",
                "vfx-impact",
            ],
        )
        actor = next(recipe for recipe in production if recipe["id"] == "actor-animation")
        self.assertEqual(actor["generation_strategy"], "identity-direction-beat-frame")
        self.assertEqual(actor["reference_policy"], "identity_master")
        serialized = json.dumps(registry).lower()
        self.assertNotIn("dungeon-cleanup-inc", serialized)
        self.assertNotIn('"provider"', serialized)

    def test_every_javascript_legacy_subtype_is_classified_exactly_once(self):
        legacy_subtypes = load_registry()["legacy_subtypes"]
        registry_ids = [entry["legacy_id"] for entry in legacy_subtypes]
        javascript_ids = load_javascript_taxonomy()

        self.assertEqual(len(javascript_ids), 32)
        self.assertEqual(len(registry_ids), 32)
        self.assertEqual(len(set(registry_ids)), len(registry_ids))
        self.assertEqual(set(registry_ids), javascript_ids)
        for entry in legacy_subtypes:
            with self.subTest(legacy_id=entry["legacy_id"]):
                self.assertEqual(entry["legacy_id"], f'{entry["family"]}.{entry["type"]}')

    def test_legacy_classifications_are_minimal_and_references_are_valid(self):
        registry = load_registry()
        recipe_ids = {recipe["id"] for recipe in registry["recipes"]}
        legacy_subtypes = registry["legacy_subtypes"]
        allowed_classifications = {"production", "alias", "lab", "retired"}
        action_for_classification = {
            "production": "use_recipe",
            "alias": "normalize_alias",
            "lab": "keep_lab",
            "retired": "remove",
        }
        canonical = {
            "sprite.character",
            "sprite.effect",
            "ui.button",
            "object.item",
        }
        safe_aliases = {
            "sprite.monster",
            "sprite.npc",
            "object.equipment",
            "object.weapon",
            "object.loot",
            "object.prop",
        }

        self.assertEqual(
            {entry["legacy_id"] for entry in legacy_subtypes if entry["classification"] == "production"},
            canonical,
        )
        self.assertEqual(
            {entry["legacy_id"] for entry in legacy_subtypes if entry["classification"] == "alias"},
            safe_aliases,
        )
        self.assertFalse(any(entry["classification"] == "retired" for entry in legacy_subtypes))
        for entry in legacy_subtypes:
            with self.subTest(legacy_id=entry["legacy_id"]):
                self.assertEqual(
                    set(entry),
                    {
                        "legacy_id",
                        "family",
                        "type",
                        "classification",
                        "recipe_id",
                        "variant",
                        "migration_action",
                        "reason",
                    },
                )
                self.assertIn(entry["classification"], allowed_classifications)
                self.assertEqual(
                    entry["migration_action"],
                    action_for_classification[entry["classification"]],
                )
                self.assertTrue(entry["reason"].strip())
                if entry["recipe_id"] is not None:
                    self.assertIn(entry["recipe_id"], recipe_ids)
                if entry["classification"] in {"production", "alias"}:
                    self.assertIsNotNone(entry["recipe_id"])
                    self.assertIsNotNone(entry["variant"])

    def test_migration_document_covers_every_registry_entry(self):
        registry_ids = {entry["legacy_id"] for entry in load_registry()["legacy_subtypes"]}
        document = MIGRATION_DOC_PATH.read_text(encoding="utf-8")
        documented_ids = set(re.findall(r"^\| `([^`]+)` \|", document, re.MULTILINE))

        self.assertEqual(documented_ids, registry_ids)

    def test_every_recipe_declares_one_registry_owned_export_capability(self):
        registry = load_registry()
        expected = {
            "static-transparent-object": (
                "object",
                ["states", "pivot", "ground", "collision", "interaction"],
            ),
            "actor-animation": ("actor", ["sheets", "frames", "fps", "pivot"]),
            "ui-component": ("ui", ["states", "nine-slice", "safe-area"]),
            "vfx-sequence": ("effect", ["full-cell", "trim", "fps", "pivot"]),
            "tile-autotile": (
                "tile",
                ["atlas", "rules", "collision", "navigation"],
            ),
        }

        for recipe in registry["recipes"]:
            with self.subTest(recipe=recipe["id"]):
                capability = recipe["export_capability"]
                self.assertEqual(set(capability), {"route", "options"})
                self.assertEqual(
                    (capability["route"], capability["options"]),
                    expected[recipe["id"]],
                )
                self.assertEqual(capability["route"], recipe["family"])
                self.assertEqual(len(capability["options"]), len(set(capability["options"])))

    def test_non_null_default_output_profiles_resolve_to_real_fixtures(self):
        registry = load_registry()
        resolved = {
            recipe["id"]: recipe["default_output_profile_id"]
            for recipe in registry["recipes"]
            if recipe["default_output_profile_id"] is not None
        }

        self.assertEqual(resolved, {"actor-animation": "generic-pixel-actor-v1"})
        for profile_id in resolved.values():
            with self.subTest(profile_id=profile_id):
                self.assertTrue((ROOT / "profiles" / f"{profile_id}.json").is_file())


if __name__ == "__main__":
    unittest.main()
