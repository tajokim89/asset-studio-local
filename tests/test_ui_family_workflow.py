"""D1 RED contracts for reusable, deterministic UI-family components.

This module deliberately specifies the production contract before D2 implements it.
It executes the real browser builders in Node and the real server normalizer, while
excluding controls/DOM, prompt/postprocessing, preview/QA, and export behavior.
"""

import io
import json
import math
import re
import subprocess
from pathlib import Path

import pytest
from PIL import Image

import server

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")

UI_KEYS = {
    "purpose", "information_structure", "source_size", "sizing_mode",
    "slice_margins", "content_safe_area", "padding", "border", "corner",
    "decor_density", "edge_mode", "center_mode", "opacity", "states",
    "target_resolution", "device_safe_area", "text_free", "animation_mode",
    "frame_count", "direction_mode",
}
NORMALIZED_ROOT_KEYS = {
    "prompt", "asset_family", "asset_type", "style_profile", "output", "ui", "family_contract",
}
FOREIGN_KEYS = {
    "sprite", "tile", "object", "action", "equipment", "walk_frames", "gait",
    "effect_category", "sequence_mode", "fps", "pivot", "topology", "seamless",
    "terrain_types", "view", "world_scale", "shadow", "ground_contact",
}
EDGES = {"top": 7, "right": 11, "bottom": 13, "left": 17}
SAMPLE_UI = {
    "purpose": "inventory item action panel",
    "information_structure": ["header", "content", "primary-actions", "status-slot"],
    "source_size": {"width": 320, "height": 180},
    "sizing_mode": "nine-slice",
    "slice_margins": EDGES,
    "content_safe_area": {"top": 19, "right": 23, "bottom": 29, "left": 31},
    "padding": {"top": 3, "right": 5, "bottom": 7, "left": 9},
    "border": {"style": "double", "width": 3},
    "corner": {"style": "ornate", "radius": 6},
    "decor_density": "medium",
    "edge_mode": "tile",
    "center_mode": "stretch",
    "opacity": 0.75,
    "states": ["normal", "hover", "pressed", "disabled"],
    "target_resolution": {"width": 1920, "height": 1080},
    "device_safe_area": {"top": 24, "right": 0, "bottom": 20, "left": 0},
    "text_free": True,
    "animation_mode": "ui_static",
    "frame_count": 1,
    "direction_mode": "none",
}


def _function_source(name):
    match = re.search(rf"\bfunction\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", JS)
    assert match, f"production function {name}() must exist"
    start, depth, quote, escaped = match.end() - 1, 0, None, False
    for index in range(start, len(JS)):
        char = JS[index]
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
                return JS[match.start():index + 1]
    raise AssertionError(f"unclosed production function {name}()")


def _run_browser_ui_contract(**overrides):
    """Execute the production browser builder with deliberately raw list controls."""
    values = {
        "uiInformationStructure": "header,content,actions",
        "uiStates": "normal,hover,pressed",
        **overrides,
    }
    harness = f"""
const values = {json.dumps(values)};
const controls = Object.fromEntries(Object.entries(values).map(([id, value]) => [id, {{value:String(value)}}]));
const $ = id => controls[id] || null;
const controlValue = (id,fallback='') => controls[id] ? controls[id].value : fallback;
const controlNumber = (id,fallback=0) => {{const n=Number(controlValue(id,fallback));return Number.isFinite(n)?n:fallback;}};
{_function_source("buildUiContract")}
try {{
  process.stdout.write(JSON.stringify({{contract:buildUiContract(), error:""}}));
}} catch (error) {{
  process.stdout.write(JSON.stringify({{contract:null, error:String(error.message || error)}}));
}}
"""
    completed = subprocess.run(["node", "-e", harness], cwd=ROOT, text=True,
                               capture_output=True, timeout=15, check=False)
    assert completed.returncode == 0, f"Node harness failed:\n{completed.stderr}"
    return json.loads(completed.stdout)


@pytest.mark.parametrize("control,value,error_field", [
    ("uiStates", "normal, normal", "state"),
    ("uiStates", " , , ", "state"),
    ("uiStates", '["normal", 7]', "state"),
    ("uiInformationStructure", "header, header", "information|structure|region"),
    ("uiInformationStructure", ", ,", "information|structure|region"),
    ("uiInformationStructure", '["header", false]', "information|structure|region"),
])
def test_browser_rejects_duplicate_empty_and_nonstring_ui_semantic_lists(control, value, error_field):
    result = _run_browser_ui_contract(**{control: value})
    assert result["contract"] is None
    assert re.search(error_field, result["error"], re.I), result["error"]
    assert re.search("unique|duplicate|nonempty|string|고유|중복|비어|문자", result["error"], re.I), result["error"]


def test_browser_semantic_list_parsing_trims_preserves_order_and_ignores_incidental_csv_gaps():
    result = _run_browser_ui_contract(
        uiInformationStructure=" header, ,content, actions, ",
        uiStates=" normal, hover, ,pressed, ",
    )
    assert result["error"] == ""
    assert result["contract"]["information_structure"] == ["header", "content", "actions"]
    assert result["contract"]["states"] == ["normal", "hover", "pressed"]


@pytest.fixture(scope="module")
def browser_ui_result():
    functions = "\n".join(_function_source(name) for name in (
        "normalizeStyleProfile", "resolveStyleProfileForFamily", "styleProfileFromControls",
        "currentAssetFamily", "currentAssetSubtype", "buildUiContract",
        "buildAssetGenerationPayload",
    ))
    values = {
        "assetSubtype": "main_panel", "assetCorePrompt": "inventory panel",
        "assetStylePreset": "pixel_refined", "assetStyleNotes": "verdant brass",
        "assetOutputWidth": 320, "assetOutputHeight": 180,
        "assetBackground": "transparent",
        "uiPurpose": SAMPLE_UI["purpose"],
        "uiInformationStructure": json.dumps(SAMPLE_UI["information_structure"]),
        "uiSourceWidth": 320, "uiSourceHeight": 180, "uiSizingMode": "nine-slice",
        "uiSliceMargins": json.dumps(SAMPLE_UI["slice_margins"]),
        "uiContentSafeArea": json.dumps(SAMPLE_UI["content_safe_area"]),
        "uiPadding": json.dumps(SAMPLE_UI["padding"]),
        "uiBorder": json.dumps(SAMPLE_UI["border"]),
        "uiCorner": json.dumps(SAMPLE_UI["corner"]), "uiDecorDensity": "medium",
        "uiEdgeMode": "tile", "uiCenterMode": "stretch", "uiOpacity": 0.75,
        "uiStates": json.dumps(SAMPLE_UI["states"]),
        "uiTargetWidth": 1920, "uiTargetHeight": 1080,
        "uiDeviceSafeArea": json.dumps(SAMPLE_UI["device_safe_area"]),
        "uiTextFree": True,
        # Existing aliases are poisoned so the new contract cannot pass accidentally.
        "uiWidth": 999, "uiHeight": 998, "uiNineSlice": False,
        "uiNineSliceMargin": 997, "uiSafeArea": "poison", "uiBorderWeight": "poison",
        "uiCornerStyle": "poison", "uiDecorationDensity": 99,
        "uiBackgroundOpacity": 0.01,
        "pixelAnimationPreset": "attack", "pixelDirectionMode": "8dir",
        "effectCategory": "Magic", "tileTopology": "blob", "objectView": "side",
    }
    harness = f"""
const values = {json.dumps(values)};
const controls = Object.fromEntries(Object.entries(values).map(([id, value]) =>
 [id, typeof value === 'boolean' ? {{checked:value,value:String(value)}} : {{value:String(value)}}]));
const document = {{getElementById:id => controls[id] || null}};
const DEFAULT_STYLE_PROFILE = {JS[JS.index("const DEFAULT_STYLE_PROFILE"):JS.index("function normalizeStyleProfile")].split("=", 1)[1].rsplit("let canonicalProjectStyleProfile", 1)[0].strip().rstrip(";")};
let canonicalProjectStyleProfile = JSON.parse(JSON.stringify(DEFAULT_STYLE_PROFILE));
const $ = id => controls[id] || null;
const ASSET_FAMILY_SUBTYPES = {{ui:['main_panel','inner_panel','popup','card','button','slot','badge','hud_chip','gauge','icon','cursor']}};
let selectedAssetFamily = 'ui';
const controlValue = (id,fallback='') => controls[id] ? controls[id].value : fallback;
const controlNumber = (id,fallback=0) => {{const n=Number(controlValue(id,fallback));return Number.isFinite(n)?n:fallback;}};
const controlChecked = (id,fallback=false) => controls[id] ? !!controls[id].checked : fallback;
const clampFamilyNumber = (value,min,max) => Math.min(max,Math.max(min,value));
{functions}
const poison = {{sprite:{{action:'attack'}},tile:{{topology:'blob'}},object:{{view:'side'}},
 action:'attack',equipment:'sword',effect_category:'Magic',sequence_mode:'sequence'}};
process.stdout.write(JSON.stringify({{contract:buildUiContract(),payload:buildAssetGenerationPayload(poison)}}));
"""
    completed = subprocess.run(["node", "-e", harness], cwd=ROOT, text=True,
                               capture_output=True, timeout=15, check=False)
    assert completed.returncode == 0, f"Node harness failed:\n{completed.stderr}"
    return json.loads(completed.stdout)


def _normalize(ui=None, **root_poison):
    payload = {
        "asset_family": "ui", "asset_type": "main_panel", "prompt": "inventory panel",
        "style": {"preset": "pixel_refined"},
        "output": {"width": 320, "height": 180, "background": "transparent"},
        **root_poison,
    }
    if ui is not None:
        payload["ui"] = ui
    return server.normalize_asset_generation_payload(payload)


def test_browser_preserves_complete_nested_ui_contract(browser_ui_result):
    assert browser_ui_result["contract"] == SAMPLE_UI
    assert browser_ui_result["payload"]["ui"] == SAMPLE_UI


def test_browser_payload_is_ui_family_isolated(browser_ui_result):
    payload = browser_ui_result["payload"]
    assert set(payload) == {"prompt", "asset_family", "asset_type", "style_profile", "output", "ui"}
    assert set(payload["ui"]) == UI_KEYS
    assert not (FOREIGN_KEYS & payload.keys())
    assert not (FOREIGN_KEYS & payload["ui"].keys())


def test_server_exactly_preserves_complete_contract_deterministically_and_in_isolation():
    poison = {key: "poison" for key in FOREIGN_KEYS}
    first = _normalize(SAMPLE_UI, **poison)
    second = _normalize(SAMPLE_UI, **poison)
    assert first["ui"] == SAMPLE_UI
    assert first["family_contract"] == SAMPLE_UI
    assert first == second
    assert set(first) == NORMALIZED_ROOT_KEYS
    assert set(first["ui"]) == UI_KEYS


def test_server_strips_unknown_root_and_nested_ui_keys_by_allowlist():
    ui = {
        **SAMPLE_UI,
        "unknown_ui_key": {"must": "not survive"},
        "border": {**SAMPLE_UI["border"], "unknown_border_key": "strip me"},
        "corner": {**SAMPLE_UI["corner"], "unknown_corner_key": "strip me"},
    }
    normalized = _normalize(ui, unknown_root_key={"must": "not survive"})
    assert set(normalized) == NORMALIZED_ROOT_KEYS
    assert set(normalized["ui"]) == UI_KEYS
    assert normalized["ui"]["border"] == SAMPLE_UI["border"]
    assert normalized["ui"]["corner"] == SAMPLE_UI["corner"]


@pytest.mark.parametrize("ui", [
    None, {},
    {"action": "attack", "topology": "blob", "view": "side"},
    {"width": 999, "height": 777, "nine_slice": True,
     "nine_slice_margin": 32, "safe_area": "legacy", "border_weight": "heavy",
     "corner_style": "square", "decoration_density": 0,
     "background_opacity": 0},
])
def test_server_supplies_safe_complete_defaults_for_missing_empty_or_poison_only_contract(ui):
    normalized = _normalize(ui) if ui is not None else _normalize()
    contract = normalized["ui"]
    assert set(contract) == UI_KEYS
    assert contract["text_free"] is True
    assert contract["animation_mode"] == "ui_static"
    assert contract["frame_count"] == 1
    assert contract["direction_mode"] == "none"
    assert contract["sizing_mode"] in {"fixed", "nine-slice"}
    assert contract["states"] and len(contract["states"]) == len(set(contract["states"]))


@pytest.mark.parametrize("ui", ["not-an-object", [], ["purpose"], 0, 7, False, True])
def test_server_supplies_same_safe_complete_defaults_for_non_object_ui_root(ui):
    assert _normalize(ui)["ui"] == _normalize()["ui"]


def test_complete_ui_contract_has_ratified_types():
    ui = _normalize(SAMPLE_UI)["ui"]
    assert isinstance(ui["purpose"], str) and ui["purpose"].strip()
    assert isinstance(ui["information_structure"], list)
    assert ui["information_structure"]
    assert all(isinstance(slot, str) and slot.strip() for slot in ui["information_structure"])
    assert len(ui["information_structure"]) == len(set(ui["information_structure"]))
    for key in ("source_size", "target_resolution"):
        assert set(ui[key]) == {"width", "height"}
        assert all(isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in ui[key].values())
    for key in ("slice_margins", "content_safe_area", "padding", "device_safe_area"):
        assert set(ui[key]) == {"top", "right", "bottom", "left"}
        assert all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in ui[key].values())
    assert set(ui["border"]) == {"style", "width"}
    assert isinstance(ui["border"]["style"], str) and ui["border"]["style"].strip()
    assert isinstance(ui["border"]["width"], int) and not isinstance(ui["border"]["width"], bool)
    assert ui["border"]["width"] >= 0
    assert set(ui["corner"]) == {"style", "radius"}
    assert isinstance(ui["corner"]["style"], str) and ui["corner"]["style"].strip()
    assert isinstance(ui["corner"]["radius"], int) and not isinstance(ui["corner"]["radius"], bool)
    assert ui["corner"]["radius"] >= 0
    assert all(isinstance(state, str) and state for state in ui["states"])
    assert isinstance(ui["opacity"], (int, float)) and not isinstance(ui["opacity"], bool)


@pytest.mark.parametrize("field,values", [
    ("sizing_mode", ["fixed", "nine-slice"]),
    ("edge_mode", ["stretch", "tile"]),
    ("center_mode", ["stretch", "tile"]),
    ("decor_density", ["low", "medium", "high"]),
])
def test_server_accepts_every_declared_ui_enum_value(field, values):
    for value in values:
        assert _normalize({**SAMPLE_UI, field: value})["ui"][field] == value


@pytest.mark.parametrize("field,value", [
    ("source_size", {"width": 0, "height": 180}),
    ("source_size", {"width": 320, "height": -1}),
    ("source_size", {"width": 3.5, "height": 180}),
    ("target_resolution", {"width": True, "height": 1080}),
    ("target_resolution", {"width": 1920}),
])
def test_server_rejects_malformed_dimensions(field, value):
    with pytest.raises(ValueError, match="dimension|size|resolution|width|height"):
        _normalize({**SAMPLE_UI, field: value})


@pytest.mark.parametrize("field,value", [
    ("slice_margins", {"top": -1, "right": 0, "bottom": 0, "left": 0}),
    ("content_safe_area", {"top": 0, "right": 0, "bottom": 0}),
    ("padding", {"top": 0, "right": 0, "bottom": 0, "left": 1.5}),
    ("padding", {"top": False, "right": 0, "bottom": 0, "left": 0}),
    ("device_safe_area", "0,0,0,0"),
])
def test_server_rejects_malformed_edge_boxes(field, value):
    with pytest.raises(ValueError, match="margin|safe|padding|edge|integer|object"):
        _normalize({**SAMPLE_UI, field: value})


@pytest.mark.parametrize("purpose", [None, "", "   ", 7, False, [], {}])
def test_server_rejects_malformed_purpose(purpose):
    with pytest.raises(ValueError, match="purpose|nonempty|string"):
        _normalize({**SAMPLE_UI, "purpose": purpose})


@pytest.mark.parametrize("information_structure", [
    None, "header,content", [], [""], ["   "], ["header", "header"],
    ["header", 7], ["header", False],
])
def test_server_rejects_malformed_information_structure(information_structure):
    with pytest.raises(ValueError, match="information|structure|region|array|unique|nonempty|string"):
        _normalize({**SAMPLE_UI, "information_structure": information_structure})


@pytest.mark.parametrize("field,value", [
    ("border", []), ("border", "solid"), ("corner", []), ("corner", None),
])
def test_server_rejects_non_object_border_and_corner_declarations(field, value):
    with pytest.raises(ValueError, match="border|corner|object"):
        _normalize({**SAMPLE_UI, field: value})


@pytest.mark.parametrize("field,value", [
    ("border", {"width": 3}),
    ("border", {"style": "", "width": 3}),
    ("border", {"style": "   ", "width": 3}),
    ("border", {"style": 7, "width": 3}),
    ("border", {"style": "solid"}),
    ("border", {"style": "solid", "width": -1}),
    ("border", {"style": "solid", "width": 1.5}),
    ("border", {"style": "solid", "width": True}),
    ("corner", {"radius": 6}),
    ("corner", {"style": "", "radius": 6}),
    ("corner", {"style": "   ", "radius": 6}),
    ("corner", {"style": False, "radius": 6}),
    ("corner", {"style": "round"}),
    ("corner", {"style": "round", "radius": -1}),
    ("corner", {"style": "round", "radius": 2.5}),
    ("corner", {"style": "round", "radius": False}),
])
def test_server_rejects_malformed_border_and_corner_fields(field, value):
    with pytest.raises(ValueError, match="border|corner|style|width|radius|integer|nonempty|string"):
        _normalize({**SAMPLE_UI, field: value})


@pytest.mark.parametrize("states", [
    "normal,hover", [], [""], ["normal", "normal"], ["normal", 7],
])
def test_server_rejects_malformed_state_ids(states):
    with pytest.raises(ValueError, match="state|array|unique|nonempty|string"):
        _normalize({**SAMPLE_UI, "states": states})


@pytest.mark.parametrize("opacity", [-0.01, 1.01, math.nan, math.inf, -math.inf, "0.5", True])
def test_server_rejects_nonfinite_out_of_range_or_nonnumeric_opacity(opacity):
    with pytest.raises(ValueError, match="opacity|finite|range|number"):
        _normalize({**SAMPLE_UI, "opacity": opacity})


@pytest.mark.parametrize("field,value", [
    ("sizing_mode", "responsive"), ("edge_mode", "mirror"),
    ("center_mode", "crop"), ("decor_density", "extreme"),
    ("text_free", False), ("animation_mode", "idle"),
    ("frame_count", 2), ("direction_mode", "8dir"),
])
def test_server_rejects_values_outside_ui_semantics(field, value):
    with pytest.raises(ValueError, match="sizing|edge|center|density|text|static|frame|direction|ui"):
        _normalize({**SAMPLE_UI, field: value})


# D2: controls, prompting, byte-preserving QA, endpoint routing, and UI state wiring.
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SERVER = (ROOT / "server.py").read_text(encoding="utf-8")


def test_d2_ui_controls_are_complete_accessible_and_static_invariants_are_read_only():
    ids = {"uiPurpose", "uiInformationStructure", "uiSourceWidth", "uiSourceHeight", "uiSizingMode",
           "uiSliceTop", "uiSliceRight", "uiSliceBottom", "uiSliceLeft", "uiContentSafeTop",
           "uiContentSafeRight", "uiContentSafeBottom", "uiContentSafeLeft", "uiPaddingTop",
           "uiPaddingRight", "uiPaddingBottom", "uiPaddingLeft", "uiBorderStyle", "uiBorderWidth",
           "uiCornerStyle", "uiCornerRadius", "uiDecorDensity", "uiEdgeMode", "uiCenterMode",
           "uiOpacity", "uiStates", "uiTargetWidth", "uiTargetHeight", "uiDeviceSafeTop",
           "uiDeviceSafeRight", "uiDeviceSafeBottom", "uiDeviceSafeLeft"}
    for control_id in ids:
        assert f'id="{control_id}"' in HTML
    # Every standalone input has for/aria-label; compact grid controls are nested
    # in a visible Korean label, which is also an accessible-name mechanism.
    ui_markup = HTML[HTML.index('id="uiSettings"'):HTML.index('id="objectSettings"')]
    assert ui_markup.count("<label") >= 10 and ui_markup.count("aria-label=") >= 20
    note_match = re.search(r'<p class="hint" role="note">([^<]+)</p>', HTML)
    assert note_match
    note = note_match.group(1)
    for exact in ("text_free=true", "animation_mode=ui_static", "frame_count=1", "direction_mode=none"):
        assert exact in note


def test_d2_ui_panel_is_hidden_for_other_families_and_switching_does_not_mutate_history():
    assert re.search(r'id="uiSettings"[^>]*class="[^"]*hidden', HTML)
    updater = _function_source("updateAssetFamilyUi")
    assert "uiSettings" in updater and "`${family}Settings`" in updater
    assert not re.search(r"history|generatedAssets|generationHistory|push\s*\(", updater, re.I)


def test_d2_server_prompt_covers_contract_semantics_without_banned_output_concepts():
    prompt = server.build_asset_family_prompt(_normalize(SAMPLE_UI))
    tokens = ("purpose=", "semantic regions=", "source=320x180", "sizing=nine-slice",
              "9-slice margins=", "content safe area=", "padding=", "border=", "corner=",
              "decor density=", "edge mode=", "center mode=", "opacity=", "states=",
              "target resolution=", "device safe area=", "text-free", "UI component contract")
    assert all(token in prompt for token in tokens)
    # Negative constraints are intentionally present in the canonical style profile;
    # only positive foreign output concepts are forbidden here.
    banned = (r"\bbaked visible (?:text|wording)\b", r"\bfake numeric labels?\b",
              r"\bfull[- ]screen mockup\b", r"\bcharacter scene\b")
    assert not any(re.search(pattern, prompt, re.I) for pattern in banned)


def test_d2_ui_postprocess_is_exactly_byte_preserving_and_reports_contract_qa():
    image = Image.new("RGBA", (320, 180), (12, 34, 56, 78))
    encoded = io.BytesIO(); image.save(encoded, format="PNG", compress_level=1); raw = encoded.getvalue()
    actual, qa = server.postprocess_ui_generation_bytes(raw, _normalize(SAMPLE_UI))
    assert actual is raw and actual == raw
    assert qa == {"status": "PASS", "reasons": [], "method": "ui-byte-preserving", "pixels_modified": False,
                  "expected_source_size": {"width": 320, "height": 180},
                  "actual_size": {"width": 320, "height": 180}, "dimension_match": True,
                  "sizing_mode": "nine-slice", "slice_margins": SAMPLE_UI["slice_margins"],
                  "content_safe_area": SAMPLE_UI["content_safe_area"], "padding": SAMPLE_UI["padding"],
                  "border": SAMPLE_UI["border"], "corner": SAMPLE_UI["corner"], "states": SAMPLE_UI["states"]}


def test_d2_both_generation_endpoints_route_ui_only_through_ui_postprocessor():
    assert SERVER.count("postprocess_ui_generation_bytes(raw, data)") == 2
    assert len(re.findall(r"elif is_ui:\s*\n\s*out, qa = postprocess_ui_generation_bytes\(raw, data\)", SERVER)) == 2


def test_d2_slice_margins_must_fit_source_dimensions():
    bad = {**SAMPLE_UI, "slice_margins": {"top": 91, "right": 0, "bottom": 90, "left": 0}}
    with pytest.raises(ValueError, match="slice margins exceed source dimensions"):
        _normalize(bad)
