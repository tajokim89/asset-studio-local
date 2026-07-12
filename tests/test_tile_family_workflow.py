"""C1 RED contracts for deterministic tile-family generation.

These tests intentionally specify the complete tile contract before C2 implements it.
They execute the real browser builders in Node and the real Python normalizer; no
browser, provider, network, preview, or export path is used.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

import server

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
REGISTRY = json.loads((ROOT / "contracts" / "asset-recipes.json").read_text(encoding="utf-8"))

TILE_KEYS = {
    "environment", "material", "use", "tile_size", "shape", "margin", "spacing",
    "mode", "rows", "columns", "seamless", "topology", "inner_corners",
    "outer_corners", "transitions", "terrain_types", "variants", "metadata",
}
FOREIGN_KEYS = {
    "sprite", "ui", "object", "animation_mode", "action", "direction_mode",
    "target_direction", "reference_direction", "frame_count", "walk_frames",
    "equipment", "effect_category", "sequence_mode", "fps", "pivot", "states",
    "nine_slice", "view", "shadow", "ground_contact",
}
SAMPLE_TILE = {
    "environment": "flooded crypt",
    "material": "mossy limestone",
    "use": "walkable dungeon floor and wall borders",
    "tile_size": {"width": 32, "height": 32},
    "shape": "square",
    "margin": 2,
    "spacing": 1,
    "mode": "autotile",
    "rows": 8,
    "columns": 8,
    "seamless": True,
    "topology": "blob",
    "inner_corners": True,
    "outer_corners": True,
    "transitions": ["grass-to-stone", "stone-to-water"],
    "terrain_types": ["grass", "stone", "water"],
    "variants": [
        {"id": "base", "weight": 3},
        {"id": "cracked", "weight": 1},
    ],
    "metadata": {
        "collision": {"type": "none"},
        "occlusion": {"mode": "none"},
        "navigation": {"walkable": True, "cost": 1.0},
        "custom": {"biome": "crypt", "wet": True},
    },
}

def _function_source(name):
    match = re.search(rf"\bfunction\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", JS)
    assert match, f"production function {name}() must exist"
    start = match.end() - 1
    depth = 0
    quote = None
    escaped = False
    for i in range(start, len(JS)):
        char = JS[i]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "'\"`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return JS[match.start():i + 1]
    raise AssertionError(f"unclosed production function {name}()")


@pytest.fixture(scope="module")
def browser_tile_result():
    functions = "\n".join(_function_source(name) for name in (
        "validateAndBuildRecipeViews", "recipeGenerationSubtypesForFamily",
        "legacyAssetSubtypesForFamily", "projectAssetSubtypesForFamily",
        "normalizeStyleProfile", "resolveStyleProfileForFamily", "styleProfileFromControls",
        "currentAssetFamily", "currentAssetSubtype", "buildTileContract",
        "buildAssetGenerationPayload", "buildAssetFamilyPrompt",
    ))
    controls_values = {
        "assetSubtype": "autotile", "assetCorePrompt": "mossy limestone flooded crypt floor",
        "assetStylePreset": "pixel_refined", "assetStyleNotes": "limited earth palette",
        "assetOutputWidth": 267, "assetOutputHeight": 267, "assetBackground": "opaque",
        "tileEnvironment": SAMPLE_TILE["environment"], "tileMaterial": SAMPLE_TILE["material"],
        "tileUse": SAMPLE_TILE["use"], "tileWidth": 32, "tileHeight": 32,
        "tileShape": "square", "tileMargin": 2, "tileSpacing": 1,
        "tileMode": "autotile", "tileRows": 8, "tileColumns": 8,
        "tileSeamless": True, "tileTopology": "blob", "tileInnerCorners": True,
        "tileOuterCorners": True, "tileTransitions": "grass-to-stone,stone-to-water",
        "tileTerrainTypes": "grass,stone,water",
        "tileVariants": json.dumps(SAMPLE_TILE["variants"]),
        "tileCollision": json.dumps(SAMPLE_TILE["metadata"]["collision"]),
        "tileOcclusion": json.dumps(SAMPLE_TILE["metadata"]["occlusion"]),
        "tileNavigation": json.dumps(SAMPLE_TILE["metadata"]["navigation"]),
        "tileCustomMetadata": json.dumps(SAMPLE_TILE["metadata"]["custom"]),
        # Poison hidden controls: a tile builder must never serialize these.
        "pixelAnimationPreset": "attack", "pixelDirectionMode": "8dir",
        "pixelTargetDirection": "NE", "equipment": "sword", "effectCategory": "Magic",
        "uiStates": "hover,pressed", "objectView": "side",
    }
    harness = f"""
const values = {json.dumps(controls_values)};
const controls = Object.fromEntries(Object.entries(values).map(([id, value]) =>
  [id, typeof value === 'boolean' ? {{checked:value, value:String(value)}} : {{value:String(value)}}]));
const document = {{getElementById:id => controls[id] || null}};
const DEFAULT_STYLE_PROFILE = {JS[JS.index("const DEFAULT_STYLE_PROFILE"):JS.index("function normalizeStyleProfile")].split("=", 1)[1].rsplit("let canonicalProjectStyleProfile", 1)[0].strip().rstrip(";")};
let canonicalProjectStyleProfile = JSON.parse(JSON.stringify(DEFAULT_STYLE_PROFILE));
const $ = id => controls[id] || null;
const ASSET_FAMILY_SUBTYPES = {{tile:['floor','wall','corner','door','terrain','decal','autotile','tileset']}};
const PROJECT_FAMILIES = ['sprite','tile','ui','object'];
const assetFamilyDrafts = new Map();
let selectedAssetFamily = 'tile';
const controlValue = (id, fallback='') => controls[id] ? controls[id].value : fallback;
const controlNumber = (id, fallback=0) => {{ const n=Number(controlValue(id, fallback)); return Number.isFinite(n)?n:fallback; }};
const controlChecked = (id, fallback=false) => controls[id] ? !!controls[id].checked : fallback;
const clampFamilyNumber = (value,min,max) => Math.min(max,Math.max(min,value));
{functions}
const assetRecipeRegistry = {json.dumps(REGISTRY)};
const recipeViews = validateAndBuildRecipeViews(assetRecipeRegistry);
const assetRecipeRegistryState = {{status:'ready',registry:assetRecipeRegistry,production:recipeViews.production,known:recipeViews.known}};
const poisonBase = {{sprite:{{action:'attack'}}, ui:{{states:'hover'}}, object:{{view:'side'}},
 action:'attack', direction_mode:'8dir', equipment:'sword', effect_category:'Magic'}};
let generation;
try {{ generation = {{status:'returned',payload:buildAssetGenerationPayload(poisonBase)}}; }}
catch (error) {{ generation = {{status:'rejected',error:String(error.message || error)}}; }}
process.stdout.write(JSON.stringify({{
 contract: buildTileContract(), generation,
 prompt: buildAssetFamilyPrompt()
}}));
"""
    completed = subprocess.run(
        ["node", "-e", harness], cwd=ROOT, text=True, capture_output=True,
        timeout=15, check=False,
    )
    assert completed.returncode == 0, f"Node harness failed:\n{completed.stderr}"
    return json.loads(completed.stdout)


def _normalize(tile=None, **root_poison):
    return server.normalize_asset_generation_payload({
        "asset_family": "tile", "asset_type": "autotile", "prompt": "crypt floor",
        "style": {"preset": "pixel_refined"},
        "output": {"width": 267, "height": 267, "background": "opaque"},
        "tile": SAMPLE_TILE if tile is None else tile,
        **root_poison,
    })


def test_browser_preserves_complete_nested_tile_contract(browser_tile_result):
    assert browser_tile_result["contract"] == SAMPLE_TILE


def test_browser_rejects_lab_tile_before_generation_payload_creation(browser_tile_result):
    generation = browser_tile_result["generation"]
    assert generation["status"] == "rejected"
    assert "invalid asset family or subtype" in generation["error"].lower()
    assert "payload" not in generation


def test_server_preserves_complete_nested_tile_contract_and_isolation():
    normalized = _normalize(
        sprite={"action": "attack"}, ui={"states": "hover"}, object={"view": "side"},
        animation_mode="attack", direction_mode="8dir", equipment="sword",
        effect_category="Magic",
    )
    assert normalized["tile"] == SAMPLE_TILE
    assert normalized["family_contract"] == SAMPLE_TILE
    assert not (FOREIGN_KEYS & normalized.keys())
    assert not (FOREIGN_KEYS & normalized["tile"].keys())


@pytest.mark.parametrize("tile", [None, {}, {"animation_mode": "poison", "equipment": "poison"}])
def test_server_defaults_absent_empty_or_foreign_only_tile_contract(tile):
    payload = {"asset_family": "tile", "asset_type": "terrain"}
    if tile is not None:
        payload["tile"] = tile
    contract = server.normalize_asset_generation_payload(payload)["tile"]
    assert set(contract) == TILE_KEYS
    assert contract["tile_size"] == {"width": 32, "height": 32}
    assert contract["margin"] == contract["spacing"] == 0
    assert contract["metadata"] == {
        "collision": {}, "occlusion": {}, "navigation": {}, "custom": {},
    }


def test_legacy_server_tile_path_already_strips_root_foreign_family_poison():
    normalized = _normalize(
        sprite={"action": "attack"}, ui={"states": "hover"}, object={"view": "side"},
        animation_mode="attack", direction_mode="8dir", equipment="sword",
    )
    assert not ({"sprite", "ui", "object", "animation_mode", "direction_mode", "equipment"}
                & normalized.keys())


def test_legacy_browser_tile_contract_remains_nested_and_actor_free(browser_tile_result):
    contract = browser_tile_result["contract"]
    assert isinstance(contract, dict)
    assert not ({"animation_mode", "action", "direction_mode", "equipment"}
                & contract.keys())


def test_legacy_tile_baseline_preserves_rows_seamless_and_opaque_output(browser_tile_result):
    contract = browser_tile_result["contract"]
    assert contract["rows"] == 8
    assert contract["seamless"] is True
    assert _normalize()["output"] == {"width": 267, "height": 267, "background": "opaque"}


@pytest.mark.parametrize("mode", ["single", "tileset", "autotile"])
def test_server_accepts_all_declared_tile_modes(mode):
    tile = {**SAMPLE_TILE, "mode": mode}
    assert _normalize(tile)["tile"]["mode"] == mode


@pytest.mark.parametrize("topology", ["corner", "edge", "corner+edge", "blob"])
def test_server_accepts_and_deterministically_preserves_declared_topologies(topology):
    tile = {**SAMPLE_TILE, "topology": topology}
    first = _normalize(tile)["tile"]
    second = _normalize(tile)["tile"]
    assert first == second
    assert first["topology"] == topology


@pytest.mark.parametrize("topology", ["corner", "edge", "corner+edge", "blob"])
def test_topology_preserves_explicit_corner_and_transition_settings(topology):
    tile = {
        **SAMPLE_TILE, "topology": topology, "inner_corners": False,
        "outer_corners": False, "transitions": [], "terrain_types": [],
    }
    normalized = _normalize(tile)["tile"]
    assert normalized["inner_corners"] is False
    assert normalized["outer_corners"] is False
    assert normalized["transitions"] == []
    assert normalized["terrain_types"] == []


def test_declared_topology_fields_have_contract_types():
    tile = _normalize()["tile"]
    assert isinstance(tile["inner_corners"], bool)
    assert isinstance(tile["outer_corners"], bool)
    assert isinstance(tile["transitions"], list)
    assert isinstance(tile["terrain_types"], list)


@pytest.mark.parametrize("variants", [
    [{"id": "base", "weight": float("nan")}],
    [{"id": "base", "frequency": float("inf")}],
    [{"id": "base", "weight": "often"}],
    [{"id": "base", "frequency": None}],
])
def test_variant_frequency_or_weight_must_be_finite_numeric(variants):
    with pytest.raises(ValueError, match="variant|weight|frequency"):
        _normalize({**SAMPLE_TILE, "variants": variants})


@pytest.mark.parametrize("variants", [
    [],
    [{"id": "base", "weight": 0}],
    [{"id": "base", "weight": -1}],
    [{"id": "base", "weight": 1}, {"id": "base", "weight": 2}],
])
def test_finite_variant_lists_are_preserved_without_engine_policy(variants):
    assert _normalize({**SAMPLE_TILE, "variants": variants})["tile"]["variants"] == variants


@pytest.mark.parametrize("change", [
    {"tile_size": {"width": 0, "height": 32}},
    {"tile_size": {"width": 32, "height": 0}},
    {"margin": -1}, {"spacing": -1}, {"rows": 0}, {"columns": 0},
])
def test_positive_dimensions_and_grid_and_nonnegative_atlas_offsets(change):
    with pytest.raises(ValueError, match="dimension|margin|spacing|row|column|bounds"):
        _normalize({**SAMPLE_TILE, **change})


def test_sample_atlas_declares_output_large_enough_for_its_grid():
    normalized = _normalize()
    assert normalized["output"]["width"] >= 267
    assert normalized["output"]["height"] >= 267


@pytest.mark.parametrize("key", ["collision", "occlusion", "navigation", "custom"])
def test_metadata_schema_is_present_and_typed(key):
    metadata = _normalize()["tile"]["metadata"]
    assert isinstance(metadata[key], dict)


def test_server_rejects_non_object_declared_metadata_section():
    bad = {**SAMPLE_TILE, "metadata": {**SAMPLE_TILE["metadata"], "custom": ["not", "an", "object"]}}
    with pytest.raises(ValueError, match="metadata"):
        _normalize(bad)


def test_browser_tile_prompt_avoids_foreign_workflow_language(browser_tile_result):
    prompt = browser_tile_result["prompt"].lower()
    assert not re.search(r"\b(actor|action|direction|equipment|animation|sprite|ui|button|panel)\b", prompt)


def test_server_tile_prompt_avoids_foreign_workflow_language():
    prompt = server.build_asset_family_prompt(_normalize()).lower()
    assert not re.search(r"\b(actor|action|direction|equipment|animation|sprite|ui|button|panel)\b", prompt)
