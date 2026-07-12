from __future__ import annotations

import json
import unittest
from pathlib import Path

import server

from tests.helpers.js_runtime_harness import JavaScriptRuntimeHarness


ROOT = Path(__file__).resolve().parents[1]
MAIN_JS = ROOT / "src" / "main.js"
REGISTRY_PATH = ROOT / "contracts" / "asset-recipes.json"


def object_contract() -> dict:
    return {
        "usage": "world",
        "identity": {
            "subtype": "placeholder",
            "form": "potion",
            "material": "glass",
            "function": "healing",
        },
        "view": "three-quarter",
        "scale": {
            "basis": "tile-relative",
            "tile_relative": {"width": 1, "height": 1},
            "character_relative": 0.5,
            "footprint": {"width": 1, "depth": 1},
        },
        "source": {
            "canvas": {"width": 96, "height": 80},
            "padding": {"top": 2, "right": 2, "bottom": 2, "left": 2},
        },
        "placement": {
            "pivot": {"x": 0.5, "y": 1},
            "ground_point": {"x": 0.5, "y": 1},
            "y_sort_point": {"x": 0.5, "y": 1},
            "snap_points": [],
        },
        "shadow": {"mode": "contact", "baked": False},
        "states": [],
        "variants": [],
        "collision": {},
        "interaction": {},
        "custom_properties": {},
    }


class ReplacementObjectGenerationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.harness = JavaScriptRuntimeHarness(MAIN_JS)
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def test_unmasked_replacement_builds_a_complete_canonical_object_request(self):
        payload = self.harness.run_json(
            names=(
                "validateAndBuildRecipeViews",
                "migrateLegacyAssetSelection",
                "buildReplacementObjectGenerationPayload",
            ),
            prelude=f"""
const assetRecipeRegistryState = {{ status:'ready', registry:{json.dumps(self.registry)} }};
function isRecipeRegistryReady() {{ return true; }}
function blockAssetGeneration() {{ return new Error('blocked'); }}
function buildObjectContract() {{ return {json.dumps(object_contract())}; }}
function styleProfileFromControls() {{ return {json.dumps(server.DEFAULT_STYLE_PROFILE)}; }}
function resolveStyleProfileForFamily(profile) {{ return profile; }}
""",
            script="""
console.log(JSON.stringify(buildReplacementObjectGenerationPayload(
  'red potion', 'no text', 'current canvas', 'chroma_green'
)));
""",
        )

        self.assertEqual(
            (payload["asset_family"], payload["asset_type"]),
            ("object", "item"),
        )
        self.assertEqual(payload["object"]["identity"]["subtype"], "item")
        self.assertEqual(
            payload["output"],
            {"width": 96, "height": 80, "background": "chroma_green"},
        )
        self.assertIn("red potion", payload["prompt"])
        self.assertIn("no text", payload["prompt"])

        normalized = server.normalize_asset_generation_payload(payload)
        self.assertEqual(normalized["asset_family"], "object")
        self.assertEqual(normalized["asset_type"], "item")
        self.assertEqual(normalized["object"], payload["object"])

    def test_unmasked_replacement_fails_before_contract_or_provider_when_registry_is_unavailable(self):
        result = self.harness.run_json(
            names=("buildReplacementObjectGenerationPayload",),
            prelude="""
let contractCalls = 0;
function isRecipeRegistryReady() { return false; }
function blockAssetGeneration() { return new Error('registry unavailable'); }
function buildObjectContract() { contractCalls += 1; return {}; }
""",
            script="""
let rejected = false;
try { buildReplacementObjectGenerationPayload('item', '', 'canvas'); }
catch (_) { rejected = true; }
console.log(JSON.stringify({ rejected, contractCalls }));
""",
        )

        self.assertEqual(result, {"rejected": True, "contractCalls": 0})


if __name__ == "__main__":
    unittest.main()
