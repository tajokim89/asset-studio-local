from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from asset_studio.recipes import (
    RecipeRegistryError,
    legacy_by_key,
    load_recipe_registry,
    recipe_by_id,
    validate_recipe_registry,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "contracts" / "asset-recipes.json"


def registry_fixture() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def legacy_fixture(**overrides) -> dict:
    item = {
        "legacy_id": "object.alias",
        "family": "object",
        "type": "alias",
        "classification": "alias",
        "recipe_id": "static-transparent-object",
        "variant": "alias",
        "migration_action": "normalize_alias",
        "reason": "The legacy subtype is a variant of the static object recipe.",
    }
    item.update(overrides)
    return item


class RecipeRegistryLoaderTests(unittest.TestCase):
    def assert_invalid(self, registry: object) -> None:
        with self.assertRaises(RecipeRegistryError):
            validate_recipe_registry(registry)

    def test_loads_default_registry_and_supports_exact_lookups(self):
        registry = load_recipe_registry()

        actor = recipe_by_id(registry, "actor-animation")
        self.assertEqual(actor["transport"], {"family": "sprite", "type": "character"})
        self.assertIsNone(recipe_by_id(registry, "missing"))

        if registry["legacy_subtypes"]:
            legacy = registry["legacy_subtypes"][0]
            self.assertEqual(
                legacy_by_key(registry, legacy["family"], legacy["type"]),
                legacy,
            )
        self.assertIsNone(legacy_by_key(registry, "missing", "missing"))

    def test_loads_an_injected_path_and_wraps_file_or_json_errors(self):
        fixture = registry_fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recipes.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            self.assertEqual(load_recipe_registry(path), fixture)

            path.write_text("{", encoding="utf-8")
            with self.assertRaises(RecipeRegistryError):
                load_recipe_registry(path)
            with self.assertRaises(RecipeRegistryError):
                load_recipe_registry(Path(directory) / "missing.json")

    def test_top_level_recipe_transport_and_legacy_objects_are_strict(self):
        cases = []

        missing_top = registry_fixture()
        del missing_top["quality_rubric_version"]
        cases.append(missing_top)

        unknown_top = registry_fixture()
        unknown_top["extra"] = True
        cases.append(unknown_top)

        missing_recipe = registry_fixture()
        del missing_recipe["recipes"][0]["description"]
        cases.append(missing_recipe)

        unknown_recipe = registry_fixture()
        unknown_recipe["recipes"][0]["extra"] = True
        cases.append(unknown_recipe)

        unknown_transport = registry_fixture()
        unknown_transport["recipes"][0]["transport"]["extra"] = True
        cases.append(unknown_transport)

        missing_export_capability = registry_fixture()
        del missing_export_capability["recipes"][0]["export_capability"]
        cases.append(missing_export_capability)

        unknown_export_capability = registry_fixture()
        unknown_export_capability["recipes"][0]["export_capability"]["extra"] = True
        cases.append(unknown_export_capability)

        missing_legacy = registry_fixture()
        item = legacy_fixture()
        del item["reason"]
        missing_legacy["legacy_subtypes"].append(item)
        cases.append(missing_legacy)

        unknown_legacy = registry_fixture()
        item = legacy_fixture(extra=True)
        unknown_legacy["legacy_subtypes"].append(item)
        cases.append(unknown_legacy)

        for index, case in enumerate(cases):
            with self.subTest(index=index):
                self.assert_invalid(case)

    def test_rejects_invalid_versions_enums_and_stage_contracts(self):
        mutations = (
            ("schema_version", "asset-studio.asset-recipes/v2"),
            ("quality_rubric_version", "quality-rubric-v2"),
        )
        for key, value in mutations:
            registry = registry_fixture()
            registry[key] = value
            with self.subTest(key=key):
                self.assert_invalid(registry)

        recipe_mutations = {
            "channel": "preview",
            "readiness": "mostly-ready",
            "reference_policy": "sometimes",
        }
        for key, value in recipe_mutations.items():
            registry = registry_fixture()
            registry["recipes"][0][key] = value
            with self.subTest(key=key):
                self.assert_invalid(registry)

        for stages in (
            ["generate", "local_qa"],
            [
                "generate",
                "local_qa",
                "visual_qa",
                "user_approval",
                "edit",
                "edit",
            ],
            [
                "generate",
                "local_qa",
                "visual_qa",
                "user_approval",
                "export",
                "edit",
            ],
        ):
            registry = registry_fixture()
            registry["recipes"][0]["required_stages"] = stages
            with self.subTest(stages=stages):
                self.assert_invalid(registry)

        unresolved_ready_profile = registry_fixture()
        unresolved_ready_profile["recipes"][0]["readiness"] = "ready"
        unresolved_ready_profile["recipes"][0]["default_output_profile_id"] = None
        self.assert_invalid(unresolved_ready_profile)

    def test_recipe_and_legacy_identifiers_are_unique_and_references_resolve(self):
        duplicate_recipe = registry_fixture()
        duplicate_recipe["recipes"].append(copy.deepcopy(duplicate_recipe["recipes"][0]))
        self.assert_invalid(duplicate_recipe)

        duplicate_golden_job = registry_fixture()
        duplicate_golden_job["recipes"][1]["golden_job_ids"].append("static-object")
        self.assert_invalid(duplicate_golden_job)

        duplicate_transport = registry_fixture()
        duplicate_transport["recipes"][1]["transport"] = copy.deepcopy(
            duplicate_transport["recipes"][0]["transport"]
        )
        self.assert_invalid(duplicate_transport)

        duplicate_legacy = registry_fixture()
        duplicate_legacy["legacy_subtypes"].extend(
            [legacy_fixture(), legacy_fixture(reason="Duplicate key")]
        )
        self.assert_invalid(duplicate_legacy)

        missing_recipe = registry_fixture()
        missing_recipe["legacy_subtypes"].append(
            legacy_fixture(recipe_id="unknown-recipe")
        )
        self.assert_invalid(missing_recipe)

    def test_legacy_id_matches_key_and_classification_action_matrix(self):
        mismatched_key = registry_fixture()
        mismatched_key["legacy_subtypes"].append(
            legacy_fixture(legacy_id="test_fixture.other")
        )
        self.assert_invalid(mismatched_key)

        combinations = {
            "production": "use_recipe",
            "alias": "normalize_alias",
            "lab": "keep_lab",
            "retired": "remove",
        }
        for classification, action in combinations.items():
            registry = registry_fixture()
            if classification == "production":
                target = next(
                    item
                    for item in registry["legacy_subtypes"]
                    if item["legacy_id"] == "object.item"
                )
            else:
                recipe_id = (
                    "static-transparent-object" if classification == "alias" else None
                )
                target = legacy_fixture(
                    classification=classification,
                    migration_action=action,
                    recipe_id=recipe_id,
                    variant=None if classification in {"lab", "retired"} else "alias",
                )
                registry["legacy_subtypes"].append(target)
            with self.subTest(classification=classification):
                validate_recipe_registry(registry)

            wrong_action = copy.deepcopy(registry)
            wrong_target = next(
                item
                for item in wrong_action["legacy_subtypes"]
                if item["legacy_id"] == target["legacy_id"]
            )
            wrong_target["migration_action"] = (
                "remove" if action != "remove" else "keep_lab"
            )
            with self.subTest(classification=classification, invalid_action=True):
                self.assert_invalid(wrong_action)

    def test_production_and_alias_require_recipe_while_lab_and_retired_are_nullable(self):
        for classification, action in (
            ("production", "use_recipe"),
            ("alias", "normalize_alias"),
        ):
            registry = registry_fixture()
            registry["legacy_subtypes"].append(
                legacy_fixture(
                    classification=classification,
                    migration_action=action,
                    recipe_id=None,
                )
            )
            with self.subTest(classification=classification):
                self.assert_invalid(registry)

        for classification, action in (("lab", "keep_lab"), ("retired", "remove")):
            allowed_recipe_ids = (None, "tile-autotile") if classification == "lab" else (None,)
            for recipe_id in allowed_recipe_ids:
                registry = registry_fixture()
                family_overrides = (
                    {"legacy_id": "tile.fixture", "family": "tile", "type": "fixture"}
                    if recipe_id == "tile-autotile"
                    else {}
                )
                registry["legacy_subtypes"].append(
                    legacy_fixture(
                        classification=classification,
                        migration_action=action,
                        recipe_id=recipe_id,
                        variant=None,
                        **family_overrides,
                    )
                )
                with self.subTest(classification=classification, recipe_id=recipe_id):
                    validate_recipe_registry(registry)

        retired_with_recipe = registry_fixture()
        retired_with_recipe["legacy_subtypes"].append(
            legacy_fixture(
                classification="retired",
                migration_action="remove",
                recipe_id="tile-autotile",
                variant=None,
            )
        )
        self.assert_invalid(retired_with_recipe)

        lab_with_production_recipe = registry_fixture()
        lab_with_production_recipe["legacy_subtypes"].append(
            legacy_fixture(
                classification="lab",
                migration_action="keep_lab",
                recipe_id="static-transparent-object",
                variant=None,
            )
        )
        self.assert_invalid(lab_with_production_recipe)

    def test_production_and_alias_require_variant_and_a_production_recipe(self):
        for classification, action in (
            ("production", "use_recipe"),
            ("alias", "normalize_alias"),
        ):
            missing_variant = registry_fixture()
            missing_variant["legacy_subtypes"].append(
                legacy_fixture(
                    classification=classification,
                    migration_action=action,
                    variant=None,
                )
            )
            with self.subTest(classification=classification, case="variant"):
                self.assert_invalid(missing_variant)

            lab_recipe = registry_fixture()
            lab_recipe["legacy_subtypes"].append(
                legacy_fixture(
                    classification=classification,
                    migration_action=action,
                    recipe_id="tile-autotile",
                )
            )
            with self.subTest(classification=classification, case="lab recipe"):
                self.assert_invalid(lab_recipe)

        cross_family_alias = registry_fixture()
        equipment = next(
            item
            for item in cross_family_alias["legacy_subtypes"]
            if item["legacy_id"] == "object.equipment"
        )
        equipment["recipe_id"] = "actor-animation"
        self.assert_invalid(cross_family_alias)

    def test_export_capability_is_strict_and_matches_recipe_family(self):
        invalid_cases = []

        invalid_route = registry_fixture()
        invalid_route["recipes"][0]["export_capability"]["route"] = "actor"
        invalid_cases.append(invalid_route)

        empty_options = registry_fixture()
        empty_options["recipes"][0]["export_capability"]["options"] = []
        invalid_cases.append(empty_options)

        duplicate_options = registry_fixture()
        duplicate_options["recipes"][0]["export_capability"]["options"] = [
            "states",
            "states",
        ]
        invalid_cases.append(duplicate_options)

        invalid_option = registry_fixture()
        invalid_option["recipes"][0]["export_capability"]["options"] = [
            "not portable!"
        ]
        invalid_cases.append(invalid_option)

        for index, registry in enumerate(invalid_cases):
            with self.subTest(index=index):
                self.assert_invalid(registry)

    def test_production_entries_are_canonical_and_cover_every_production_recipe(self):
        mismatched_transport = registry_fixture()
        character = next(
            item
            for item in mismatched_transport["legacy_subtypes"]
            if item["legacy_id"] == "sprite.character"
        )
        character["legacy_id"] = "sprite.hero"
        character["type"] = "hero"
        character["variant"] = "hero"
        self.assert_invalid(mismatched_transport)

        missing_canonical = registry_fixture()
        missing_canonical["legacy_subtypes"] = [
            item
            for item in missing_canonical["legacy_subtypes"]
            if item["legacy_id"] != "sprite.character"
        ]
        self.assert_invalid(missing_canonical)


if __name__ == "__main__":
    unittest.main()
