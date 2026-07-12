from __future__ import annotations

import json
import unittest
from pathlib import Path

from asset_studio.recipes import migrate_legacy_selection
from tests.helpers.js_runtime_harness import JavaScriptRuntimeHarness


ROOT = Path(__file__).resolve().parents[1]
MAIN_JS = ROOT / "src" / "main.js"
REGISTRY_PATH = ROOT / "contracts" / "asset-recipes.json"


class RecipeRegistryFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.harness = JavaScriptRuntimeHarness(MAIN_JS)
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def test_registry_view_exposes_only_production_canonical_subtypes(self):
        result = self.harness.run_json(
            names=("validateAndBuildRecipeViews",),
            prelude=f"const fixture = {json.dumps(self.registry)};",
            script="console.log(JSON.stringify(validateAndBuildRecipeViews(fixture)));",
        )

        self.assertEqual(
            result["production"],
            {
                "sprite": ["character", "effect"],
                "ui": ["button"],
                "object": ["item"],
            },
        )
        exposed = {
            subtype
            for subtypes in result["production"].values()
            for subtype in subtypes
        }
        self.assertTrue({"monster", "npc", "autotile"}.isdisjoint(exposed))

    def test_frontend_rejects_semantically_invalid_production_registry(self):
        result = self.harness.run_json(
            names=("validateAndBuildRecipeViews",),
            prelude=f"const fixture = {json.dumps(self.registry)};",
            script="""
const mutate = callback => {
  const registry = JSON.parse(JSON.stringify(fixture));
  callback(registry);
  try { validateAndBuildRecipeViews(registry); return false; } catch (_) { return true; }
};
const findCharacter = registry => registry.legacy_subtypes.find(item => item.legacy_id === 'sprite.character');
console.log(JSON.stringify([
  mutate(registry => { findCharacter(registry).variant = null; }),
  mutate(registry => { findCharacter(registry).recipe_id = 'tile-autotile'; }),
  mutate(registry => {
    const item = findCharacter(registry);
    item.legacy_id = 'sprite.hero'; item.type = 'hero'; item.variant = 'hero';
  }),
  mutate(registry => {
    registry.legacy_subtypes = registry.legacy_subtypes.filter(item => item.legacy_id !== 'sprite.character');
  }),
  mutate(registry => {
    registry.legacy_subtypes.find(item => item.legacy_id === 'object.equipment').recipe_id = 'actor-animation';
  }),
  mutate(registry => { registry.recipes[0].export_capability.route = 'actor'; }),
  mutate(registry => { registry.recipes[0].export_capability.options = []; }),
  mutate(registry => { registry.recipes[0].export_capability.extra = true; }),
]));
""",
        )

        self.assertEqual(result, [True, True, True, True, True, True, True, True])

    def test_legacy_selection_migration_preserves_variant_and_never_promotes_lab(self):
        result = self.harness.run_json(
            names=("validateAndBuildRecipeViews", "migrateLegacyAssetSelection"),
            prelude=f"const fixture = {json.dumps(self.registry)};",
            script="""
const production = migrateLegacyAssetSelection(fixture, 'sprite', 'character');
const alias = migrateLegacyAssetSelection(fixture, 'sprite', 'monster');
const lab = migrateLegacyAssetSelection(fixture, 'tile', 'autotile');
let unknownRejected = false;
try { migrateLegacyAssetSelection(fixture, 'sprite', 'unknown'); } catch (_) { unknownRejected = true; }
const retiredFixture = JSON.parse(JSON.stringify(fixture));
const retired = retiredFixture.legacy_subtypes.find(item => item.legacy_id === 'ui.cursor');
retired.classification = 'retired';
retired.migration_action = 'remove';
retired.recipe_id = null;
retired.variant = null;
let retiredRejected = false;
try { migrateLegacyAssetSelection(retiredFixture, 'ui', 'cursor'); } catch (_) { retiredRejected = true; }
console.log(JSON.stringify({ production, alias, lab, unknownRejected, retiredRejected }));
""",
        )

        self.assertEqual(result["production"]["transport"], {"family": "sprite", "type": "character"})
        self.assertEqual(result["alias"]["transport"], {"family": "sprite", "type": "character"})
        self.assertEqual(result["alias"]["variant"], "monster")
        self.assertEqual(result["alias"]["channel"], "production")
        self.assertEqual(result["lab"]["channel"], "lab")
        self.assertEqual(result["lab"]["classification"], "lab")
        self.assertTrue(result["unknownRejected"])
        self.assertTrue(result["retiredRejected"])

        for family, subtype, key in (
            ("sprite", "character", "production"),
            ("sprite", "monster", "alias"),
            ("tile", "autotile", "lab"),
        ):
            with self.subTest(parity=f"{family}.{subtype}"):
                self.assertEqual(
                    result[key],
                    migrate_legacy_selection(self.registry, family, subtype),
                )

    def test_lab_migration_uses_recipe_transport_when_a_lab_recipe_is_attached(self):
        registry = json.loads(json.dumps(self.registry))
        floor = next(
            item
            for item in registry["legacy_subtypes"]
            if item["legacy_id"] == "tile.floor"
        )
        floor["recipe_id"] = "tile-autotile"
        floor["variant"] = "floor"

        result = self.harness.run_json(
            names=("validateAndBuildRecipeViews", "migrateLegacyAssetSelection"),
            prelude=f"const fixture = {json.dumps(registry)};",
            script="console.log(JSON.stringify(migrateLegacyAssetSelection(fixture, 'tile', 'floor')));",
        )

        self.assertEqual(result, migrate_legacy_selection(registry, "tile", "floor"))
        self.assertEqual(result["transport"], {"family": "tile", "type": "autotile"})

    def test_legacy_constant_remains_complete_but_generation_paths_use_recipe_view(self):
        legacy = self.harness.run_json(
            names=("ASSET_FAMILY_SUBTYPES",),
            script="console.log(JSON.stringify(ASSET_FAMILY_SUBTYPES));",
        )
        self.assertEqual(sum(map(len, legacy.values())), 32)

        for symbol in (
            "currentAssetFamily",
            "currentAssetSubtype",
            "renderAssetSubtypeOptions",
            "setAssetFamily",
            "buildAssetGenerationPayload",
        ):
            with self.subTest(symbol=symbol):
                self.assertNotIn(
                    "ASSET_FAMILY_SUBTYPES",
                    self.harness.source_for(symbol),
                )

    def test_disabling_generation_controls_does_not_disable_editor_controls(self):
        result = self.harness.run_json(
            names=(
                "RECIPE_GENERATION_CONTROL_IDS",
                "setRecipeGenerationControlsEnabled",
            ),
            prelude="""
const nodes = Object.create(null);
function $(id) {
  if (!nodes[id]) nodes[id] = { disabled: false };
  return nodes[id];
}
""",
            script="""
nodes.brushTool = { disabled: false };
setRecipeGenerationControlsEnabled(false);
console.log(JSON.stringify({
  generation: Object.fromEntries(RECIPE_GENERATION_CONTROL_IDS.map(id => [id, nodes[id].disabled])),
  editorDisabled: nodes.brushTool.disabled,
}));
""",
        )

        self.assertTrue(result["generation"])
        self.assertTrue(all(result["generation"].values()))
        self.assertFalse(result["editorDisabled"])

    def test_only_families_with_production_subtypes_remain_visible(self):
        result = self.harness.run_json(
            names=(
                "RECIPE_GENERATION_CONTROL_IDS",
                "assetRecipeRegistryState",
                "recipeGenerationSubtypesForFamily",
                "isRecipeRegistryReady",
                "setRecipeGenerationControlsEnabled",
                "applyRecipeRegistryToGenerationUi",
            ),
            prelude="""
const controls = Object.create(null);
const tabs = ['sprite', 'tile', 'ui', 'object'].map(family => ({
  dataset: { assetFamily: family }, disabled: false, hidden: false,
  setAttribute(name, value) { this[name] = value; },
}));
function $(id) { return controls[id] ||= { disabled: false }; }
const document = { querySelectorAll() { return tabs; } };
let selectedAssetFamily = 'sprite';
let selected = null;
function setAssetFamily(family) { selected = family; }
function renderAssetSubtypeOptions() {}
""",
            script="""
assetRecipeRegistryState = {
  status: 'ready', registry: {},
  production: { sprite: ['character', 'effect'], ui: ['button'], object: ['item'] },
  known: {},
};
applyRecipeRegistryToGenerationUi();
console.log(JSON.stringify({
  selected,
  tabs: Object.fromEntries(tabs.map(tab => [tab.dataset.assetFamily, {
    disabled: tab.disabled, hidden: tab.hidden,
  }])),
}));
""",
        )

        self.assertEqual(result["selected"], "sprite")
        self.assertEqual(
            result["tabs"],
            {
                "sprite": {"disabled": False, "hidden": False},
                "tile": {"disabled": True, "hidden": True},
                "ui": {"disabled": False, "hidden": False},
                "object": {"disabled": False, "hidden": False},
            },
        )

    def test_ready_registry_without_production_recipes_keeps_generation_disabled(self):
        result = self.harness.run_json(
            names=(
                "RECIPE_GENERATION_CONTROL_IDS",
                "assetRecipeRegistryState",
                "recipeGenerationSubtypesForFamily",
                "isRecipeRegistryReady",
                "setRecipeGenerationControlsEnabled",
                "applyRecipeRegistryToGenerationUi",
            ),
            prelude="""
const controls = Object.create(null);
const tabs = ['sprite', 'tile', 'ui', 'object'].map(family => ({
  dataset:{ assetFamily:family }, disabled:false, hidden:false,
  setAttribute(name, value) { this[name] = value; },
}));
function $(id) { return controls[id] ||= { disabled:false }; }
const document = { querySelectorAll() { return tabs; } };
let selectedAssetFamily = 'sprite';
function setAssetFamily() { throw new Error('no family should be selected'); }
function renderAssetSubtypeOptions() {}
""",
            script="""
assetRecipeRegistryState = { status:'ready', registry:{}, production:{}, known:{} };
applyRecipeRegistryToGenerationUi();
console.log(JSON.stringify({
  controls:Object.fromEntries(RECIPE_GENERATION_CONTROL_IDS.map(id => [id, controls[id].disabled])),
  tabs:tabs.map(tab => ({ disabled:tab.disabled, hidden:tab.hidden })),
}));
""",
        )

        self.assertTrue(all(result["controls"].values()))
        self.assertTrue(all(tab == {"disabled": True, "hidden": True} for tab in result["tabs"]))

    def test_editor_family_state_is_separate_from_generation_eligibility(self):
        result = self.harness.run_json(
            names=("currentAssetFamily", "currentAssetSubtype"),
            prelude="""
const PROJECT_FAMILIES = ['sprite','tile','ui','object'];
let selectedAssetFamily = 'tile';
const assetFamilyDrafts = new Map([['tile', { subtype:'autotile' }]]);
function $(id) { return id === 'assetSubtype' ? { value:'' } : null; }
function projectAssetSubtypesForFamily(family) { return family === 'tile' ? ['autotile'] : []; }
""",
            script="console.log(JSON.stringify({ family:currentAssetFamily(), subtype:currentAssetSubtype() }));",
        )

        self.assertEqual(result, {"family": "tile", "subtype": "autotile"})

    def test_retry_rejects_lab_result_before_provider_request(self):
        result = self.harness.run_json(
            names=(
                "validateAndBuildRecipeViews",
                "migrateLegacyAssetSelection",
                "retryAssetResult",
            ),
            prelude=f"""
const assetRecipeRegistryState = {{ status:'ready', registry:{json.dumps(self.registry)} }};
let fetchCalls = 0;
function isRecipeRegistryReady() {{ return true; }}
function blockAssetGeneration() {{ return new Error('blocked'); }}
function fetch() {{ fetchCalls += 1; throw new Error('provider must not run'); }}
const assetResultStore = {{
  get() {{ return {{ family:'tile', type:'autotile', sourceRequest:{{ asset_family:'tile', asset_type:'autotile' }} }}; }},
}};
""",
            script="""
retryAssetResult('lab-result').then(
  () => console.log(JSON.stringify({ rejected:false, fetchCalls })),
  error => console.log(JSON.stringify({ rejected:true, fetchCalls, message:error.message }))
);
""",
        )

        self.assertTrue(result["rejected"])
        self.assertEqual(result["fetchCalls"], 0)
        self.assertIn("Production", result["message"])

    def test_registry_loader_fetches_api_and_sanitizes_failure_status(self):
        actor_profile = json.loads(
            (ROOT / "profiles" / "generic-pixel-actor-v1.json").read_text(
                encoding="utf-8"
            )
        )
        success = self.harness.run_json(
            names=(
                "assetRecipeRegistryState",
                "actorOutputProfileState",
                "ACTOR_ACTION_ALIASES",
                "validateActorOutputProfile",
                "actorActionRecipe",
                "applyActorOutputProfileUi",
                "loadActorOutputProfile",
                "validateAndBuildRecipeViews",
                "loadAssetRecipeRegistry",
            ),
            prelude=f"""
const fixture = {json.dumps(self.registry)};
const actorProfile = {json.dumps(actor_profile)};
const requests = [];
const statuses = [];
async function fetch(url) {{
  requests.push(url);
  return {{ ok: true, async json() {{ return url === '/api/recipes' ? fixture : actorProfile; }} }};
}}
const $ = () => null;
function applyRecipeRegistryToGenerationUi() {{}}
function setStatus(message) {{ statuses.push(message); }}
""",
            script="""
loadAssetRecipeRegistry().then(() => console.log(JSON.stringify({
  requests,
  status: assetRecipeRegistryState.status,
  production: assetRecipeRegistryState.production,
  message: statuses.at(-1),
})));
""",
        )
        self.assertEqual(
            success["requests"],
            ["/api/recipes", "/api/output-profiles/generic-pixel-actor-v1"],
        )
        self.assertEqual(success["status"], "ready")
        self.assertEqual(success["production"]["sprite"], ["character", "effect"])

        failure = self.harness.run_json(
            names=(
                "assetRecipeRegistryState",
                "actorOutputProfileState",
                "validateAndBuildRecipeViews",
                "loadAssetRecipeRegistry",
            ),
            prelude="""
const statuses = [];
async function fetch() { throw new Error('/Users/private/contracts/asset-recipes.json'); }
function applyRecipeRegistryToGenerationUi() {}
function setStatus(message) { statuses.push(message); }
""",
            script="""
loadAssetRecipeRegistry().then(() => console.log(JSON.stringify({
  status: assetRecipeRegistryState.status,
  message: statuses.at(-1),
})));
""",
        )
        self.assertEqual(failure["status"], "failed")
        self.assertIn("AI 생성", failure["message"])
        self.assertNotIn("/Users/private", failure["message"])

    def test_generate_fails_closed_before_any_provider_request(self):
        result = self.harness.run_json(
            names=(
                "assetRecipeRegistryState",
                "isRecipeRegistryReady",
                "blockAssetGeneration",
                "generateAiAsset",
            ),
            prelude="""
let fetchCalls = 0;
const statuses = [];
function fetch() { fetchCalls += 1; throw new Error('provider must not run'); }
function setStatus(message) { statuses.push(message); }
function $() { return null; }
""",
            script="""
Promise.resolve(generateAiAsset()).then(
  () => console.log(JSON.stringify({ fetchCalls, rejected: false, message: statuses.at(-1) })),
  error => console.log(JSON.stringify({ fetchCalls, rejected: true, error: error.message, message: statuses.at(-1) })),
);
""",
        )

        self.assertEqual(result["fetchCalls"], 0)
        self.assertTrue(result["rejected"])
        self.assertIn("레시피", result["error"])
        self.assertIn("AI 생성", result["message"])

    def test_app_initialization_loads_registry_without_opening_a_browser(self):
        source = MAIN_JS.read_text(encoding="utf-8")
        self.assertIn("loadAssetRecipeRegistry();", source)
        self.assertNotIn("window.open(", self.harness.source_for("loadAssetRecipeRegistry"))


if __name__ == "__main__":
    unittest.main()
