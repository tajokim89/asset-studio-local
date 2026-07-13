"""Runtime payload-isolation contracts for Task A4.

The browser builder is evaluated in Node with inexpensive DOM-control stubs.  The
server normalizer is imported directly.  No HTTP server or generation provider is
started, and no paid endpoint is called.
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
ACTOR_PROFILE = json.loads((ROOT / "profiles" / "generic-pixel-actor-v1.json").read_text(encoding="utf-8"))
FAMILY_KEYS = {"sprite", "tile", "ui", "object"}
REPRESENTATIVES = (
    ("sprite", "character"),
    ("sprite", "effect"),
    ("ui", "button"),
    ("object", "item"),
)
SHARED_KEYS = {"asset_family", "asset_type", "prompt", "style_profile", "output"}
ACTOR_KEYS = {
    "animation_mode", "direction_mode", "target_direction", "reference_direction",
    "frame_count", "walk_frames", "chroma_mode", "preservation", "equipment", "gait",
}
UI_STATIC_INVARIANTS = {
    "animation_mode": "ui_static", "direction_mode": "none", "frame_count": 1,
}
UI_FOREIGN_FAMILY_KEYS = {
    "effect_category", "loop", "size_basis",
    "tile_size", "layout", "seamless", "connections",
    "view", "world_scale", "shadow", "usage", "ground_contact",
}


def _server_object_fixture():
    return {
        "usage": "world", "identity": {"subtype": "item"}, "view": "three-quarter",
        "scale": {"basis": "tile-relative"},
        "source": {"canvas": {"width": 160, "height": 128}, "padding": {"top": 0, "right": 0, "bottom": 0, "left": 0}},
        "placement": {"pivot": {"x": 0, "y": 1}, "ground_point": {"x": 0, "y": 1}, "y_sort_point": {"x": 0, "y": 1}, "snap_points": []},
        "shadow": {"mode": "contact", "baked": False}, "states": [], "variants": [],
        "collision": {}, "interaction": {}, "custom_properties": {},
    }
FAMILY_SPECIFIC_KEYS = {
    "sprite": {
        "animation_mode", "direction_mode", "target_direction", "reference_direction",
        "frame_count", "walk_frames", "chroma_mode", "preservation", "no_baked_vfx",
        "sequence_mode", "effect_category", "loop", "fps", "rows", "columns", "gap",
        "envelope_width", "envelope_height", "pivot", "size_basis", "trim_policy",
    },
    "tile": {
        "environment", "material", "use", "tile_size", "shape", "margin", "spacing",
        "mode", "rows", "columns", "seamless", "topology", "inner_corners",
        "outer_corners", "transitions", "terrain_types", "variants", "metadata",
    },
    "ui": {
        "purpose", "information_structure", "source_size", "sizing_mode", "slice_margins",
        "content_safe_area", "padding", "border", "corner", "decor_density", "edge_mode",
        "center_mode", "opacity", "states", "target_resolution", "device_safe_area",
        "text_free", "animation_mode", "direction_mode", "frame_count",
    },
    "object": {
        "usage", "identity", "view", "scale", "source", "placement", "shadow", "states",
        "variants", "collision", "interaction", "custom_properties",
    },
}

EXPECTED_BROWSER_CONTRACTS = {
    "sprite/character": {
        "required": {
            "animation_mode", "direction_mode", "target_direction", "reference_direction",
            "frame_count", "walk_frames", "chroma_mode", "preservation", "no_baked_vfx",
        },
        "values": {
            "animation_mode": "walk", "direction_mode": "8dir", "target_direction": "NE",
            "reference_direction": "AUTO", "frame_count": 4, "walk_frames": 4,
            "chroma_mode": "outer", "no_baked_vfx": True,
        },
    },
    "sprite/effect": {
        "required": {
            "animation_mode", "effect_category", "loop", "frame_count", "pivot",
            "size_basis", "no_baked_vfx",
        },
        "values": {
            "animation_mode": "effect_sequence", "effect_category": "Smoke", "loop": "loop",
            "frame_count": 1, "pivot": {"preset": "source", "x": 0.5, "y": 0.5},
            "size_basis": "actor-relative",
            "no_baked_vfx": False,
        },
    },
    "ui/button": {
        "required": {
            "purpose", "information_structure", "source_size", "sizing_mode", "slice_margins",
            "content_safe_area", "padding", "border", "corner", "decor_density", "edge_mode",
            "center_mode", "opacity", "states", "target_resolution", "device_safe_area",
            "text_free", "animation_mode", "direction_mode", "frame_count",
        },
        "values": {
            "purpose": "reusable interface component",
            "information_structure": ["header", "content", "actions"],
            "source_size": {"width": 320, "height": 180}, "sizing_mode": "nine-slice",
            "slice_margins": {"top": 0, "right": 0, "bottom": 0, "left": 0},
            "decor_density": "medium", "opacity": 1,
            "states": ["normal", "hover", "pressed", "disabled"],
            "text_free": True,
            **UI_STATIC_INVARIANTS,
        },
    },
    "object/item": {
        "required": {
            "usage", "identity", "view", "scale", "source", "placement", "shadow", "states",
            "variants", "collision", "interaction", "custom_properties",
        },
        "values": {
            "view": "three-quarter", "usage": "world",
            "source": {"canvas": {"width": 160, "height": 128}, "padding": {"top": 0, "right": 7, "bottom": 11, "left": 0}},
            "placement": {"pivot": {"x": 0, "y": 1}, "ground_point": {"x": 0, "y": 1}, "y_sort_point": {"x": 0, "y": 0.875}, "snap_points": [{"id": "origin", "x": 0, "y": 0}]},
        },
    },
}


def _function_source(name: str) -> str:
    match = re.search(rf"\bfunction\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", JS)
    assert match, f"Expected function {name}()"
    opening = match.end() - 1
    depth = 0
    quote = None
    escaped = False
    for index in range(opening, len(JS)):
        char = JS[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return JS[match.start():index + 1]
    raise AssertionError(f"Unclosed function {name}()")


def _object_constant_source(name: str) -> str:
    """Extract a production object constant so the harness cannot drift on subtype lists."""
    match = re.search(rf"\bconst\s+{re.escape(name)}\s*=\s*\{{", JS)
    assert match, f"Expected object constant {name}"
    opening = match.end() - 1
    depth = 0
    for index in range(opening, len(JS)):
        if JS[index] == "{":
            depth += 1
        elif JS[index] == "}":
            depth -= 1
            if depth == 0:
                semicolon = JS.find(";", index)
                assert semicolon >= 0, f"Expected semicolon after {name}"
                return JS[match.start():semicolon + 1]
    raise AssertionError(f"Unclosed object constant {name}")


def _const_callable_source(name: str) -> str:
    """Extract one production ``const`` callable declaration, including its body."""
    match = re.search(rf"\bconst\s+{re.escape(name)}\s*=", JS)
    assert match, f"Could not extract production helper {name!r}: const declaration not found"
    depths = {"(": 0, "[": 0, "{": 0}
    closing = {")": "(", "]": "[", "}": "{"}
    quote = None
    escaped = False
    for index in range(match.end(), len(JS)):
        char = JS[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char in depths:
            depths[char] += 1
        elif char in closing:
            opener = closing[char]
            depths[opener] -= 1
            assert depths[opener] >= 0, (
                f"Could not extract production helper {name!r}: unbalanced {char!r}"
            )
        elif char == ";" and not any(depths.values()):
            return JS[match.start():index + 1]
    raise AssertionError(
        f"Could not extract production helper {name!r}: declaration has no terminating semicolon"
    )


def _variable_source(name: str) -> str:
    """Extract one simple production ``let``/``const`` declaration."""
    match = re.search(rf"\b(?:let|const)\s+{re.escape(name)}\s*=[^;]+;", JS)
    assert match, f"Could not extract production variable {name!r}"
    return match.group(0)


def _diagnostic_text(value):
    if value is None:
        return "<empty>"
    return value.decode(errors="replace") if isinstance(value, bytes) else value


@pytest.fixture(scope="module")
def browser_runtime_payloads():
    functions = "\n\n".join(_function_source(name) for name in (
        "validateAndBuildRecipeViews", "recipeGenerationSubtypesForFamily",
        "projectAssetSubtypesForFamily",
        "normalizeStyleProfile", "resolveStyleProfileForFamily", "styleProfileFromControls",
        "currentAssetFamily", "currentAssetSubtype", "actorActionRecipe",
        "inferReferenceDirection", "buildSpriteContract",
        "buildTileContract", "buildUiContract", "buildObjectContract",
        "buildAssetGenerationPayload",
    ))
    # Execute production DOM adapters as well as production builders.  A missing or
    # changed declaration must fail extraction rather than silently use a test copy.
    subtype_constant = "\n".join((
        _object_constant_source("DEFAULT_STYLE_PROFILE"),
        _object_constant_source("ASSET_FAMILY_SUBTYPES"),
    ))
    helper_sources = "\n".join(_const_callable_source(name) for name in (
        "controlValue", "controlNumber", "clampFamilyNumber", "controlChecked",
    ))
    harness = f"""
const controls = Object.create(null);
const $ = id => Object.prototype.hasOwnProperty.call(controls, id) ? controls[id] : null;
const document = {{ getElementById: $ }};
{subtype_constant}
{_variable_source("canonicalProjectStyleProfile")}
{_variable_source("assetRecipeRegistryState")}
{_variable_source("assetFamilyDrafts")}
{_variable_source("PROJECT_FAMILIES")}
{_variable_source("ACTOR_ACTION_ALIASES")}
let selectedAssetFamily = 'sprite';
{helper_sources}
const actorProfile = {json.dumps(ACTOR_PROFILE)};
let actorOutputProfileState = {{
  status: 'ready', profile: actorProfile,
  actions: new Map(actorProfile.actions.map(action => [action.id, action])),
}};
{functions}
const recipeRegistry = {json.dumps(REGISTRY)};
const recipeViews = validateAndBuildRecipeViews(recipeRegistry);
assetRecipeRegistryState = {{
  status: 'ready', registry: recipeRegistry,
  production: recipeViews.production, known: recipeViews.known,
}};
function setControls(values) {{
  for (const key of Object.keys(controls)) delete controls[key];
  for (const [key, value] of Object.entries(values)) {{
    controls[key] = typeof value === 'object' ? value : {{ value: String(value) }};
  }}
}}
function build(family, subtype, extra = {{}}) {{
  selectedAssetFamily = family;
  setControls({{
    assetSubtype: subtype,
    assetCorePrompt: 'runtime payload',
    assetStylePreset: 'pixel_refined',
    assetStyleNotes: 'limited palette',
    assetOutputWidth: 640,
    assetOutputHeight: 384,
    assetBackground: family === 'tile' ? 'opaque' : 'transparent',
    pixelAnimationPreset: 'walk',
    pixelDirectionMode: '8dir',
    pixelTargetDirection: 'NE',
    pixelReferenceDirection: 'S',
    pixelChromaMode: 'outer',
    pixelPalette: 'actor-only palette',
    effectCategory: 'Smoke',
    effectLoop: 'loop',
    effectFrameCount: 0,
    effectPivot: 'source',
    tileMargin: 0,
    tileSpacing: 0,
    uiDecorationDensity: 0,
    uiBackgroundOpacity: 0,
    objectUsage: 'world', objectIdentitySubtype: subtype, objectForm: 'brass lever',
    objectMaterial: 'brass', objectFunction: 'opens gate', objectView: 'three-quarter',
    objectScaleBasis: 'tile-relative', objectTileRelativeWidth: 2, objectTileRelativeHeight: 1.5,
    objectCharacterRelative: 0.75, objectFootprintWidth: 2, objectFootprintDepth: 1,
    objectSourceWidth: 160, objectSourceHeight: 128, objectPaddingTop: 0, objectPaddingRight: 7,
    objectPaddingBottom: 11, objectPaddingLeft: 0, objectPivotX: 0, objectPivotY: 1,
    objectGroundX: 0, objectGroundY: 1, objectYSortX: 0, objectYSortY: 0.875,
    objectSnapPoints: '[{{"id":"origin","x":0,"y":0}}]', objectShadowMode: 'contact',
    objectShadowBaked: {{ checked: false }}, objectStates: '[{{"id":"closed"}},{{"id":"open"}}]',
    objectVariantDefinitions: '[{{"id":"brass","weight":3}}]', objectCollision: '{{"shape":"box"}}',
    objectInteraction: '{{"radius":1.25}}', objectCustomProperties: '{{"quest_gate":"cistern"}}',
    ...extra,
  }});
  return buildAssetGenerationPayload();
}}
function captureBuild(family, subtype) {{
  try {{
    return {{ marker: 'returned', payload: build(family, subtype) }};
  }} catch (error) {{
    return {{ marker: 'rejected', error: String(error && (error.stack || error.message || error)) }};
  }}
}}
const payloads = Object.fromEntries([
  ['sprite/character', build('sprite', 'character')],
  ['sprite/effect', build('sprite', 'effect')],
  ['ui/button', build('ui', 'button')],
  ['object/item', build('object', 'item')],
]);
const bounded = build('ui', 'button', {{
  assetOutputWidth: 999999, assetOutputHeight: -9, assetBackground: 'invalid',
  uiDecorationDensity: -5, uiBackgroundOpacity: 9,
}});
setControls({{ numericZero: {{ value: '0' }}, unchecked: {{ checked: false }} }});
const helperZeroes = {{
  controlNumber: controlNumber('numericZero', 37),
  clampFamilyNumber: clampFamilyNumber(0, 0, 100),
  controlChecked: controlChecked('unchecked', true),
}};
const rejectedSubtypes = {{
  empty: captureBuild('sprite', ''),
  invalid: captureBuild('sprite', '__invalid_explicit_subtype__'),
}};
const labSelections = {{
  tileAutotile: captureBuild('tile', 'autotile'),
  uiBadge: captureBuild('ui', 'badge'),
  objectInteractable: captureBuild('object', 'interactable'),
}};
process.stdout.write(JSON.stringify({{
  payloads, bounded, helperZeroes, rejectedSubtypes, labSelections,
}}));
"""
    try:
        completed = subprocess.run(
            ["node", "-e", harness], cwd=ROOT, text=True, capture_output=True,
            check=True, timeout=15,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            "Node builder harness timed out after 15s\n"
            f"stdout:\n{_diagnostic_text(exc.stdout)}\n"
            f"stderr:\n{_diagnostic_text(exc.stderr)}",
            pytrace=False,
        )
    except subprocess.CalledProcessError as exc:
        pytest.fail(
            f"Node builder harness exited with status {exc.returncode}\n"
            f"stdout:\n{_diagnostic_text(exc.stdout)}\n"
            f"stderr:\n{_diagnostic_text(exc.stderr)}",
            pytrace=False,
        )
    except OSError as exc:
        pytest.fail(f"Could not start Node builder harness: {exc}", pytrace=False)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"Node builder harness emitted invalid JSON: {exc}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
            pytrace=False,
        )


@pytest.mark.parametrize("family,subtype", REPRESENTATIVES)
def test_browser_representative_has_positive_schema_values_and_one_nested_contract(
    browser_runtime_payloads, family, subtype,
):
    payload = browser_runtime_payloads["payloads"][f"{family}/{subtype}"]
    assert set(payload) == SHARED_KEYS | {family}
    assert payload["asset_family"] == family
    assert payload["asset_type"] == subtype
    assert payload["prompt"] == "runtime payload"
    assert payload["style_profile"]["schema_version"] == "asset-studio.style-profile/v1"
    assert payload["style_profile"]["name"] == "limited palette"
    assert "style" not in payload
    assert payload["output"] == {
        "width": 640, "height": 384,
        "background": "opaque" if family == "tile" else "transparent",
    }
    assert FAMILY_KEYS & payload.keys() == {family}
    assert isinstance(payload[family], dict)
    expected = EXPECTED_BROWSER_CONTRACTS[f"{family}/{subtype}"]
    actual_keys = set(payload[family])
    assert expected["required"] <= actual_keys
    foreign_keys = set().union(*(
        keys for other_family, keys in FAMILY_SPECIFIC_KEYS.items() if other_family != family
    )) - FAMILY_SPECIFIC_KEYS[family]
    assert not (foreign_keys & actual_keys), (
        f"{family}/{subtype} nested contract contains foreign-family keys: "
        f"{sorted(foreign_keys & actual_keys)}"
    )
    for key, value in expected["values"].items():
        assert payload[family][key] == value
    if subtype == "character":
        assert payload["sprite"]["preservation"] == {
            "identity_lock": True, "equipment_lock": True,
            "palette": "actor-only palette", "root_foot_lock": True,
            "silhouette_lock": True,
        }


@pytest.mark.parametrize("family,subtype,forbidden", (
    ("sprite", "effect", {"target_direction", "reference_direction", "equipment", "gait", "walk_frames"}),
    ("ui", "button", ACTOR_KEYS - UI_STATIC_INVARIANTS.keys()),
    ("object", "item", {"animation_mode", "action", "direction_mode", "target_direction", "reference_direction"}),
))
def test_browser_non_actor_contracts_do_not_serialize_hidden_actor_controls(
    browser_runtime_payloads, family, subtype, forbidden,
):
    contract = browser_runtime_payloads["payloads"][f"{family}/{subtype}"][family]
    assert not (forbidden & contract.keys())
    if subtype == "effect":
        assert contract.get("direction_mode", "none") == "none"


def test_browser_ui_normalizes_poisoned_actor_controls_to_static_invariants(
    browser_runtime_payloads,
):
    contract = browser_runtime_payloads["payloads"]["ui/button"]["ui"]
    assert {key: contract[key] for key in UI_STATIC_INVARIANTS} == UI_STATIC_INVARIANTS


def test_browser_preserves_legitimate_zeroes_and_bounds_output(browser_runtime_payloads):
    assert browser_runtime_payloads["helperZeroes"] == {
        "controlNumber": 0, "clampFamilyNumber": 0, "controlChecked": False,
    }
    payloads = browser_runtime_payloads["payloads"]
    assert payloads["ui/button"]["ui"]["opacity"] == 1
    obj = payloads["object/item"]["object"]
    assert obj["source"]["padding"]["top"] == 0
    assert obj["placement"]["pivot"]["x"] == 0
    assert obj["placement"]["ground_point"]["x"] == 0
    assert obj["placement"]["y_sort_point"]["x"] == 0
    bounded = browser_runtime_payloads["bounded"]
    assert bounded["output"] == {"width": 4096, "height": 1, "background": "transparent"}
    assert bounded["ui"]["decor_density"] == "medium"
    assert bounded["ui"]["opacity"] == 1


@pytest.mark.parametrize("result_name", ("empty", "invalid"))
def test_browser_explicit_invalid_sprite_subtype_is_fail_closed(
    browser_runtime_payloads, result_name,
):
    result = browser_runtime_payloads["rejectedSubtypes"][result_name]
    assert result["marker"] in {"returned", "rejected"}
    if result["marker"] == "returned":
        # Omission, null, empty/sentinel values, and explicit rejection are all valid;
        # silently acquiring character semantics is the only forbidden outcome.
        payload = result.get("payload")
        subtype = payload.get("asset_type") if isinstance(payload, dict) else payload
        assert subtype != "character"


@pytest.mark.parametrize("selection", ("tileAutotile", "uiBadge", "objectInteractable"))
def test_browser_lab_selection_is_rejected(browser_runtime_payloads, selection):
    result = browser_runtime_payloads["labSelections"][selection]
    assert result["marker"] == "rejected"
    assert "Invalid asset family or subtype" in result["error"]


@pytest.mark.parametrize("family,subtype", (
    ("sprite", "effect"), ("ui", "button"), ("object", "item"),
))
def test_server_non_actor_contracts_exclude_actor_state_even_when_poisoned(family, subtype):
    poison = {key: "poison" for key in ACTOR_KEYS}
    if family == "ui":
        poison = {key: value for key, value in poison.items() if key not in UI_STATIC_INVARIANTS}
    # E2 is deliberately open within its authoritative object. Poison the root to
    # verify family isolation without asking the lossless nested contract to discard it.
    source = _server_object_fixture() if family == "object" else poison
    normalized = server.normalize_asset_generation_payload({
        "asset_family": family, "asset_type": subtype, family: source, **poison,
    })
    contract = normalized[family]
    allowed = (
        UI_STATIC_INVARIANTS.keys() if family == "ui"
        else {"animation_mode", "direction_mode", "frame_count"} if subtype == "effect"
        else set()
    )
    forbidden = ACTOR_KEYS - allowed
    assert not (forbidden & contract.keys()), f"{family}/{subtype} retained actor state"
    assert not (forbidden & (normalized.keys() - {family})), f"{family}/{subtype} flattened actor state"
    if family == "ui":
        assert {key: contract[key] for key in UI_STATIC_INVARIANTS} == UI_STATIC_INVARIANTS
    if subtype == "effect":
        assert contract["animation_mode"] == "effect_sequence"
        assert contract.get("direction_mode", "none") == "none"


def test_server_ui_contract_excludes_foreign_family_fields_when_poisoned():
    poison = {key: f"poison-{key}" for key in UI_FOREIGN_FAMILY_KEYS}
    normalized = server.normalize_asset_generation_payload({
        "asset_family": "ui", "asset_type": "button",
        "ui": {**poison, **{key: "actor-poison" for key in ACTOR_KEYS - UI_STATIC_INVARIANTS.keys()}},
        **poison,
    })
    contract = normalized["ui"]
    assert not (UI_FOREIGN_FAMILY_KEYS & contract.keys())
    assert not (UI_FOREIGN_FAMILY_KEYS & normalized.keys())
    assert {key: contract[key] for key in UI_STATIC_INVARIANTS} == UI_STATIC_INVARIANTS


def test_server_rejects_structurally_partial_authoritative_ui_contract():
    with pytest.raises(ValueError, match="purpose"):
        server.normalize_asset_generation_payload({
            "asset_family": "ui", "asset_type": "BUTTON",
            "ui": {"source_size": {"width": 320, "height": 180}},
        })


@pytest.mark.parametrize("subtype", ("", "__invalid_explicit_subtype__"))
def test_server_explicit_invalid_sprite_subtype_is_fail_closed(subtype):
    try:
        normalized = server.normalize_asset_generation_payload({
            "asset_family": "sprite", "asset_type": subtype, "sprite": {},
        })
    except Exception:
        return  # Explicit rejection is a valid fail-closed result.
    normalized_subtype = (
        normalized.get("asset_type") if isinstance(normalized, dict) else normalized
    )
    assert normalized_subtype != "character"


def test_generate_has_single_in_flight_promise_guard():
    body = _function_source("generateAiAsset")
    assert re.search(r"if\s*\(\s*assetGenerationInFlight\s*\)\s*return\s+assetGenerationInFlight", body)
    assert re.search(r"assetGenerationInFlight\s*=\s*request", body)
    assert re.search(r"assetGenerationInFlight\s*===\s*request[^;]*assetGenerationInFlight\s*=\s*null", body)
