import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from asset_studio.output_profiles import (
    OutputProfileError,
    load_output_profile,
    validate_output_profile_semantics,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "output-profile.schema.json"
GENERIC_PATH = ROOT / "profiles" / "generic-pixel-actor-v1.json"
DUNGEON_PATH = ROOT / "profiles" / "dungeon-cleanup-inc-actor-v1.json"


def load_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_ref(root_schema, ref):
    value = root_schema
    for token in ref.removeprefix("#/").split("/"):
        value = value[token]
    return value


def schema_errors(value, schema, root_schema=None, path="$"):
    """Validate the small JSON Schema subset used by this contract."""
    root_schema = root_schema or schema
    if "$ref" in schema:
        return schema_errors(value, _resolve_ref(root_schema, schema["$ref"]), root_schema, path)

    errors = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: not in enum")

    expected_type = schema.get("type")
    type_matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
    }
    if expected_type and not type_matches[expected_type]:
        return errors + [f"{path}: expected {expected_type}"]

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}: missing {name}")
        if schema.get("additionalProperties") is False:
            for name in value.keys() - properties.keys():
                errors.append(f"{path}: unexpected {name}")
        for name, item in value.items():
            if name in properties:
                errors.extend(schema_errors(item, properties[name], root_schema, f"{path}.{name}"))

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: too few items")
        if len(value) > schema.get("maxItems", len(value)):
            errors.append(f"{path}: too many items")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: duplicate items")
        for index, item in enumerate(value):
            errors.extend(schema_errors(item, schema["items"], root_schema, f"{path}[{index}]"))

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: too short")
        if len(value) > schema.get("maxLength", len(value)):
            errors.append(f"{path}: too long")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            errors.append(f"{path}: pattern mismatch")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema.get("minimum", value):
            errors.append(f"{path}: below minimum")
        if value > schema.get("maximum", value):
            errors.append(f"{path}: above maximum")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: below exclusive minimum")

    return errors


class OutputProfileContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load_json(SCHEMA_PATH)
        cls.generic = load_output_profile(GENERIC_PATH)
        cls.dungeon = load_output_profile(DUNGEON_PATH)

    def test_schema_is_strict_at_every_object_boundary(self):
        self.assertFalse(self.schema["additionalProperties"])
        for name in ("frame", "direction", "pivot", "sheetLayout", "action", "importHints"):
            self.assertFalse(self.schema["$defs"][name]["additionalProperties"], name)

    def test_both_profiles_pass_schema_and_cross_field_contracts(self):
        for profile in (self.generic, self.dungeon):
            with self.subTest(profile=profile["id"]):
                self.assertEqual([], schema_errors(profile, self.schema))
                validated = validate_output_profile_semantics(profile)
                self.assertEqual(profile, validated)
                self.assertIsNot(profile, validated)
                self.assertIsNot(profile["actions"], validated["actions"])

    def test_generic_profile_is_the_default_32px_actor_contract(self):
        self.assertEqual("default", self.generic["role"])
        self.assertEqual({"width": 32, "height": 32}, {
            "width": self.generic["frame"]["width"],
            "height": self.generic["frame"]["height"],
        })
        self.assertEqual(
            ["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
            [item["code"] for item in self.generic["directions"]],
        )
        actions = {action["id"]: action for action in self.generic["actions"]}
        self.assertEqual({
            "idle", "walk", "run", "attack", "ranged_attack", "cast",
            "block", "dodge", "jump", "hurt", "death", "interact", "pickup", "static",
        }, set(actions))
        self.assertEqual((4, 6, True), (actions["idle"]["frame_count"], actions["idle"]["fps"], actions["idle"]["loop"]))
        self.assertEqual((4, 10, True), (actions["walk"]["frame_count"], actions["walk"]["fps"], actions["walk"]["loop"]))
        self.assertEqual(["N", "L", "N", "R"], actions["walk"]["beats"])
        self.assertEqual((6, 12, False), (actions["attack"]["frame_count"], actions["attack"]["fps"], actions["attack"]["loop"]))
        for action in actions.values():
            self.assertEqual(action["frame_count"], len(action["beats"]))
            self.assertTrue(action["prompt_contract"])
            self.assertTrue(action["acceptance"])
        self.assertNotIn("dungeon", json.dumps(self.generic).lower())

    def test_dungeon_profile_is_an_explicit_88px_example_not_a_default(self):
        self.assertEqual("example", self.dungeon["role"])
        self.assertNotEqual("default", self.dungeon["role"])
        self.assertEqual((88, 88), (self.dungeon["frame"]["width"], self.dungeon["frame"]["height"]))
        self.assertEqual(
            ["S", "SE", "E", "NE", "N", "NW", "W", "SW"],
            [item["code"] for item in self.dungeon["directions"]],
        )
        actions = {action["id"]: action for action in self.dungeon["actions"]}
        self.assertEqual((4, 4), (actions["idle"]["frame_count"], actions["idle"]["fps"]))
        self.assertEqual((6, 8), (actions["walk"]["frame_count"], actions["walk"]["fps"]))
        self.assertEqual("godot-4", self.dungeon["import_hints"]["engine"])

    def test_schema_invalid_profiles_are_rejected_without_external_dependencies(self):
        invalid_cases = []

        unknown_field = copy.deepcopy(self.generic)
        unknown_field["unused_menu"] = True
        invalid_cases.append(("unknown root field", unknown_field))

        missing_layout = copy.deepcopy(self.generic)
        del missing_layout["actions"][0]["sheet_layout"]
        invalid_cases.append(("missing action layout", missing_layout))

        invalid_pivot = copy.deepcopy(self.generic)
        invalid_pivot["actions"][0]["pivot"]["x"] = -1
        invalid_cases.append(("negative pivot", invalid_pivot))

        for label, profile in invalid_cases:
            with self.subTest(case=label):
                self.assertTrue(
                    schema_errors(profile, self.schema),
                    f"{label} should be rejected",
                )

    def test_semantics_reject_duplicate_direction_and_action_identity(self):
        cases = {}
        cases["direction id"] = copy.deepcopy(self.generic)
        cases["direction id"]["directions"][1]["id"] = "south"
        cases["direction code"] = copy.deepcopy(self.generic)
        cases["direction code"]["directions"][1]["code"] = "S"
        cases["action id"] = copy.deepcopy(self.generic)
        cases["action id"]["actions"][1]["id"] = "idle"

        for label, profile in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(OutputProfileError):
                    validate_output_profile_semantics(profile)

    def test_semantics_reject_direction_order_drift(self):
        profile = copy.deepcopy(self.generic)
        profile["actions"][0]["sheet_layout"]["direction_order"] = [
            "west",
            "south",
            "east",
            "north",
        ]

        with self.assertRaises(OutputProfileError):
            validate_output_profile_semantics(profile)

    def test_semantics_reject_sheet_shape_and_frame_order_drift(self):
        cases = {}
        cases["frame order"] = copy.deepcopy(self.generic)
        cases["frame order"]["actions"][1]["sheet_layout"]["frame_order"] = [
            0,
            1,
            2,
            3,
            5,
            4,
        ]
        cases["columns"] = copy.deepcopy(self.generic)
        cases["columns"]["actions"][0]["sheet_layout"]["columns"] = 5
        cases["rows"] = copy.deepcopy(self.generic)
        cases["rows"]["actions"][0]["sheet_layout"]["rows"] = 3

        for label, profile in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(OutputProfileError):
                    validate_output_profile_semantics(profile)

    def test_semantics_reject_action_recipe_drift(self):
        cases = {}
        cases["beat count"] = copy.deepcopy(self.generic)
        cases["beat count"]["actions"][0]["beats"].pop()
        cases["blank prompt contract"] = copy.deepcopy(self.generic)
        cases["blank prompt contract"]["actions"][0]["prompt_contract"] = ""
        cases["blank acceptance"] = copy.deepcopy(self.generic)
        cases["blank acceptance"]["actions"][0]["acceptance"] = ""
        cases["blank beat"] = copy.deepcopy(self.generic)
        cases["blank beat"]["actions"][0]["beats"][0] = "   "
        cases["fps above limit"] = copy.deepcopy(self.generic)
        cases["fps above limit"]["actions"][0]["fps"] = 121
        cases["terminal loop"] = copy.deepcopy(self.generic)
        cases["terminal loop"]["actions"][0]["terminal"] = True

        for label, profile in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(OutputProfileError):
                    validate_output_profile_semantics(profile)

    def test_semantics_reject_pivot_outside_frame(self):
        for coordinate, value in (("x", 32), ("y", -1)):
            profile = copy.deepcopy(self.generic)
            profile["actions"][0]["pivot"][coordinate] = value
            with self.subTest(coordinate=coordinate):
                with self.assertRaises(OutputProfileError):
                    validate_output_profile_semantics(profile)

    def test_semantics_fail_closed_for_malformed_structure(self):
        malformed_profiles = (
            None,
            {},
            {"frame": {}, "directions": [], "actions": []},
            {
                "frame": {"width": 32, "height": 32},
                "directions": "south",
                "actions": [],
            },
        )
        for profile in malformed_profiles:
            with self.subTest(profile=profile):
                with self.assertRaises(OutputProfileError):
                    validate_output_profile_semantics(profile)

    def test_loader_accepts_injected_path_and_wraps_load_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(self.generic), encoding="utf-8")
            self.assertEqual(self.generic, load_output_profile(path))

            path.write_text("{", encoding="utf-8")
            with self.assertRaises(OutputProfileError) as malformed_json:
                load_output_profile(path)
            self.assertIsInstance(malformed_json.exception.__cause__, json.JSONDecodeError)

            with self.assertRaises(OutputProfileError) as missing_file:
                load_output_profile(Path(directory) / "missing.json")
            self.assertIsInstance(missing_file.exception.__cause__, OSError)


if __name__ == "__main__":
    unittest.main()
