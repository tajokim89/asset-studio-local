"""RED contracts for Task B1/B2 effect-sequence controls and plumbing.

The browser builders execute in a cost-free Node harness.  Server checks are
in-process; no endpoint, provider, or paid generation path is invoked.
"""

import base64
import io
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server  # noqa: E402

JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
REGISTRY = json.loads((ROOT / "contracts" / "asset-recipes.json").read_text(encoding="utf-8"))

EFFECT_FIELDS = {
    "sequence_mode",
    "effect_category",
    "frame_count",
    "rows",
    "columns",
    "gap",
    "envelope_width",
    "envelope_height",
    "loop",
    "pivot",
    "size_basis",
    "trim_policy",
}
EFFECT_TIMING_FIELDS = {"fps", "duration_ms"}
ACTOR_ONLY_FIELDS = {
    "action",
    "animation_action",
    "target_direction",
    "reference_direction",
    "equipment",
    "body",
    "gait",
    "walk_frames",
    "root_lock",
    "preservation",
    "chroma_mode",
}
EFFECT_CONTROL_IDS = {
    "effectCategory",
    "effectSequenceMode",
    "effectLoop",
    "effectFrameCount",
    "effectRows",
    "effectColumns",
    "effectGap",
    "effectEnvelopeWidth",
    "effectEnvelopeHeight",
    "effectSizeBasis",
    "effectPivot",
    "effectPivotX",
    "effectPivotY",
    "effectTrimPolicy",
}
EFFECT_TIMING_CONTROL_IDS = {"effectFps", "effectDuration"}
TIMING_CONTROL_SPECS = {
    "effectFps": ("fps", 20),
    "effectDuration": ("duration_ms", 50),
}


class _IdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.controls = {}
        self._select_ids = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        values = dict(attrs)
        control_id = values.get("id")
        if control_id:
            self.ids.add(control_id)
            self.controls[control_id] = {
                "tag": tag,
                "attrs": values,
                "options": [],
            }
        if tag == "select":
            self._select_ids.append(control_id)
        elif tag == "option" and self._select_ids and self._select_ids[-1]:
            self.controls[self._select_ids[-1]]["options"].append(values)

    def handle_endtag(self, tag):
        if tag.lower() == "select":
            self._select_ids.pop()


def _html_control_ids():
    parser = _IdParser()
    parser.feed(HTML)
    return parser.ids


def _option_values(control):
    return {
        option.get("value")
        for option in control["options"]
        if option.get("value") and "disabled" not in option
    }


def _numeric_attr(control, name):
    value = control["attrs"].get(name)
    assert value is not None, f"#{control['attrs']['id']} must declare {name}"
    try:
        return float(value)
    except ValueError:
        pytest.fail(f"#{control['attrs']['id']} has non-numeric {name}={value!r}", pytrace=False)


def _chosen_timing_spec():
    """Use the sole product timing control, with FPS only as a harness fallback."""
    present = EFFECT_TIMING_CONTROL_IDS & _html_control_ids()
    # Keep unrelated RED assertions independently useful before timing UI ships.
    # Zero or two controls is still rejected by the explicit DOM XOR test; the
    # deterministic fallback merely prevents fixture/setup errors from hiding
    # the remaining contract REDs.
    control_id = next(iter(present)) if len(present) == 1 else "effectFps"
    field, value = TIMING_CONTROL_SPECS[control_id]
    return control_id, field, value


def _function_source(name: str) -> str:
    """Extract a production function with nested/default parameter expressions."""
    match = re.search(rf"\b(?:async\s+)?function\s+{re.escape(name)}\s*\(", JS)
    assert match, f"Expected production function {name}()"
    opening_paren = match.end() - 1
    paren_depth = 0
    quote = None
    escaped = False
    opening = None
    for index in range(opening_paren, len(JS)):
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
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
            if paren_depth == 0:
                opening = index + 1
                while opening < len(JS) and JS[opening].isspace():
                    opening += 1
                assert JS[opening] == "{", f"Expected body for production function {name}()"
                break
    assert opening is not None, f"Unclosed parameters for production function {name}()"
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
                return JS[match.start() : index + 1]
    raise AssertionError(f"Unclosed production function {name}()")


def _object_constant_source(name: str) -> str:
    match = re.search(rf"\bconst\s+{re.escape(name)}\s*=\s*\{{", JS)
    assert match, f"Expected production object constant {name}"
    opening = match.end() - 1
    depth = 0
    for index in range(opening, len(JS)):
        if JS[index] == "{":
            depth += 1
        elif JS[index] == "}":
            depth -= 1
            if depth == 0:
                semicolon = JS.find(";", index)
                assert semicolon >= 0
                return JS[match.start() : semicolon + 1]
    raise AssertionError(f"Unclosed production object constant {name}")


def _variable_source(name: str) -> str:
    match = re.search(rf"\b(?:let|const)\s+{re.escape(name)}\s*=[^;]+;", JS)
    assert match, f"Expected production variable {name}"
    return match.group(0)


def _const_callable_source(name: str) -> str:
    match = re.search(rf"\bconst\s+{re.escape(name)}\s*=", JS)
    assert match, f"Expected production callable constant {name}"
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
            depths[closing[char]] -= 1
        elif char == ";" and not any(depths.values()):
            return JS[match.start() : index + 1]
    raise AssertionError(f"Unterminated production callable constant {name}")


def _run_node(source: str):
    try:
        completed = subprocess.run(
            ["node", "-e", source], cwd=ROOT, text=True, capture_output=True,
            check=True, timeout=15,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"Node harness timed out\nstdout:\n{exc.stdout}\nstderr:\n{exc.stderr}", pytrace=False)
    except subprocess.CalledProcessError as exc:
        pytest.fail(
            f"Node harness exited {exc.returncode}\nstdout:\n{exc.stdout}\nstderr:\n{exc.stderr}",
            pytrace=False,
        )
    except OSError as exc:
        pytest.fail(f"Could not start Node: {exc}", pytrace=False)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Node emitted invalid JSON: {exc}\n{completed.stdout}\n{completed.stderr}", pytrace=False)


@pytest.fixture(scope="module")
def browser_effect_runtime():
    timing_control, _timing_field, timing_value = _chosen_timing_spec()
    functions = "\n\n".join(
        _function_source(name)
        for name in (
            "validateAndBuildRecipeViews",
            "recipeGenerationSubtypesForFamily",
            "projectAssetSubtypesForFamily",
            "normalizeStyleProfile",
            "resolveStyleProfileForFamily",
            "styleProfileFromControls",
            "currentAssetFamily",
            "currentAssetSubtype",
            "pixelAnimationDefaultFrames",
            "isPixelActorAssetType",
            "isPixelEffectAssetType",
            "effectivePixelAnimationPreset",
            "requestedPixelFrameCount",
            "buildSpriteContract",
            "buildAssetFamilyPrompt",
            "buildAssetGenerationPayload",
        )
    )
    helpers = "\n".join(
        _const_callable_source(name)
        for name in ("controlValue", "controlNumber", "clampFamilyNumber", "controlChecked")
    )
    return _run_node(f"""
const controls = Object.create(null);
const $ = id => Object.prototype.hasOwnProperty.call(controls, id) ? controls[id] : null;
const document = {{ getElementById: $ }};
{_object_constant_source('DEFAULT_STYLE_PROFILE')}
{_variable_source('canonicalProjectStyleProfile')}
{_variable_source('assetRecipeRegistryState')}
{_variable_source('assetFamilyDrafts')}
{_variable_source('PROJECT_FAMILIES')}
{_object_constant_source('ASSET_FAMILY_SUBTYPES')}
{_object_constant_source('PIXEL_ANIMATION_PRESET_DEFAULT_FRAMES')}
const PIXEL_ACTOR_ASSET_TYPES = new Set(['character', 'monster', 'npc']);
const PIXEL_EFFECT_ASSET_TYPES = new Set(['effect']);
let selectedAssetFamily = 'sprite';
{helpers}
const pixelPresetFrameCount = () => 4;
const actionFrameBeats = () => '';
const spriteAnimationCoreLockContract = () => '';
const buildDirectionalSpriteSheetContract = () => '';
const directionLabel = value => value;
{functions}
const recipeRegistry = {json.dumps(REGISTRY)};
const recipeViews = validateAndBuildRecipeViews(recipeRegistry);
assetRecipeRegistryState = {{
  status: 'ready', registry: recipeRegistry,
  production: recipeViews.production, known: recipeViews.known,
}};
function setControls(values) {{
  for (const key of Object.keys(controls)) delete controls[key];
  for (const [key, value] of Object.entries(values)) controls[key] = {{ value: String(value) }};
}}
function build(sequenceMode, frameCount) {{
  setControls({{
    assetSubtype: 'effect', pixelAssetType: 'effect', assetCorePrompt: 'violet impact burst',
    assetStylePreset: 'pixel_refined', assetStyleNotes: 'limited palette',
    assetOutputWidth: 320, assetOutputHeight: 96, assetBackground: 'transparent',
    effectCategory: 'Impact', effectSequenceMode: sequenceMode,
    effectLoop: 'ping-pong', effectFrameCount: frameCount,
    effectRows: 2, effectColumns: 4, effectGap: 3,
    effectEnvelopeWidth: 80, effectEnvelopeHeight: 48,
    effectSizeBasis: 'actor-relative', effectPivot: 'source',
    effectPivotX: 0.25, effectPivotY: 0.75, effectTrimPolicy: 'preserve-envelope'
  }});
  controls[{json.dumps(timing_control)}] = {{ value: String({timing_value}) }};
  return {{
    payload: buildAssetGenerationPayload(),
    prompt: buildAssetFamilyPrompt()
  }};
}}
process.stdout.write(JSON.stringify({{
  sequence: build('sequence', 7),
  staticEffect: build('static', 9)
}}));
""")


def _effect_contract(**overrides):
    effect = {
        "sequence_mode": "sequence",
        "effect_category": "Impact",
        "frame_count": 7,
        "rows": 2,
        "columns": 4,
        "gap": 3,
        "envelope_width": 80,
        "envelope_height": 48,
        "loop": "ping-pong",
        "pivot": {"preset": "source", "x": 0.25, "y": 0.75},
        "size_basis": "actor-relative",
        "trim_policy": "preserve-envelope",
    }
    _control_id, timing_field, timing_value = _chosen_timing_spec()
    effect[timing_field] = timing_value
    effect.update(overrides)
    return effect


def _raw_effect(**overrides):
    return {
        "asset_family": "sprite",
        "asset_type": "effect",
        "prompt": "violet impact burst",
        "output": {"width": 320, "height": 96, "background": "transparent"},
        "sprite": _effect_contract(**overrides),
    }


def _assert_effect_prompt(prompt: str):
    prompt = prompt.lower()
    assert re.search(
        r"(?:\b7\b.{0,24}\b(?:frames?|frame[_ -]?count|sequence)\b"
        r"|\b(?:frames?|frame[_ -]?count|sequence)\b.{0,24}\b7\b)",
        prompt,
    ), "effectFrameCount=7 must be expressed near frame/sequence language"


def _assert_no_effect_sequence_contradictions(prompt: str):
    contradiction_patterns = (
        r"\bui[_-]static\b",
        r"(?<!\w)single\s+asset(?!\w)",
        r"(?<!\w)no\s+sprite(?:\s+sheet|sheet)(?!\w)",
        # Keep one-frame checks tied to generation/count semantics.  Logical
        # cell descriptions such as "single frame envelope" and
        # "single-frame dimensions" are valid in a multi-frame sheet prompt.
        r"\b(?:generate|produce|create|render|output|deliver)\s+"
        r"(?:only\s+)?(?:1|one|a\s+single)\s+frames?\b"
        r"(?![ -](?:envelope|dimensions?)\b)",
        r"\b(?:only|exactly)\s+(?:1|one|a\s+single)\s+frames?\b"
        r"(?![ -](?:envelope|dimensions?)\b)",
        r"(?<!\w)(?:1|one|single)[ -]frame\s+"
        r"(?:effect|asset|sequence|sprite(?:\s+sheet)?)\b",
    )
    for pattern in contradiction_patterns:
        match = re.search(pattern, prompt, flags=re.IGNORECASE)
        if match:
            pytest.fail(
                f"effect sequence prompt contradicts itself with {match.group(0)!r}",
                pytrace=False,
            )


@pytest.mark.parametrize(
    "prompt",
    (
        "Generate an 11 frame sequence using a single frame envelope for every logical cell.",
        "Render 11 frames; keep single-frame dimensions at 80 by 48 pixels.",
        "Render a single frame envelope for each of the 11 frames.",
        "Output only one frame envelope per logical cell across all 11 frames.",
        "Each sprite-sheet cell has one frame envelope and single-frame dimensions.",
    ),
)
def test_effect_sequence_contradiction_check_allows_frame_envelope_wording(prompt):
    _assert_no_effect_sequence_contradictions(prompt)


@pytest.mark.parametrize(
    "prompt",
    (
        "Generate only 1 frame.",
        "Produce one frame for the requested sequence.",
        "Create a single frame.",
        "Render exactly one frame.",
        "Output only a single frame.",
        "Deliver 1 frame.",
        "Return exactly 1 frame.",
        "Make this a single-frame effect.",
        "Build a one-frame sprite sheet.",
        "This is a 1-frame sequence.",
    ),
)
def test_effect_sequence_contradiction_check_rejects_actual_one_frame_requests(prompt):
    with pytest.raises(pytest.fail.Exception, match="contradicts itself"):
        _assert_no_effect_sequence_contradictions(prompt)


def _assert_effect_contract(actual: dict, expected: dict):
    """Assert common metadata plus the timing representation chosen by the UI."""
    _assert_effect_timing(actual)
    assert EFFECT_FIELDS <= actual.keys()
    assert {key: actual[key] for key in EFFECT_FIELDS} == {
        key: expected[key] for key in EFFECT_FIELDS
    }


def _assert_effect_timing(actual: dict):
    timing = EFFECT_TIMING_FIELDS & actual.keys()
    _control_id, chosen_field, chosen_value = _chosen_timing_spec()
    assert timing == {chosen_field}, (
        f"effect contract must expose only {chosen_field}, matching the sole UI timing choice; "
        f"got {sorted(timing)}"
    )
    assert actual[chosen_field] > 0
    expected_value = (
        pytest.approx(chosen_value, abs=1)
        if chosen_field == "duration_ms"
        else pytest.approx(chosen_value)
    )
    assert actual[chosen_field] == expected_value, (
        f"timing is not coherent with {chosen_field}={chosen_value} from the UI"
    )


def _assert_effect_direction_is_neutral(effect: dict):
    assert effect.get("direction_mode") in (None, "none")


def test_effect_controls_exist_in_real_dom():
    parser = _IdParser()
    parser.feed(HTML)
    timing_controls = EFFECT_TIMING_CONTROL_IDS & parser.ids
    assert len(timing_controls) == 1, (
        "UI must expose exactly one timing control: effectFps or effectDuration; "
        f"got {sorted(timing_controls)}"
    )
    assert EFFECT_CONTROL_IDS <= parser.ids

    for control_id in EFFECT_CONTROL_IDS | timing_controls:
        accessible_name = parser.controls[control_id]["attrs"].get("aria-label", "").strip()
        assert accessible_name, f"#{control_id} must have an accessible name"

    select_specs = {
        "effectSequenceMode": {"static", "sequence"},
        "effectLoop": {"one-shot", "loop", "ping-pong"},
        "effectSizeBasis": {"pixels", "tile", "actor-relative", "world", "screen"},
        "effectCategory": {"Impact"},
    }
    for control_id, required_options in select_specs.items():
        control = parser.controls[control_id]
        assert control["tag"] == "select", f"#{control_id} must be a usable select"
        assert "disabled" not in control["attrs"], f"#{control_id} must be enabled"
        option_values = _option_values(control)
        assert required_options <= option_values, (
            f"#{control_id} is missing options {sorted(required_options - option_values)}"
        )
    for control_id in ("effectPivot", "effectTrimPolicy"):
        control = parser.controls[control_id]
        assert control["tag"] == "select", f"#{control_id} must be a usable select"
        assert "disabled" not in control["attrs"], f"#{control_id} must be enabled"
        assert _option_values(control), f"#{control_id} must provide at least one option"
    positive_numeric_ids = {
        "effectFrameCount", "effectRows", "effectColumns",
        "effectEnvelopeWidth", "effectEnvelopeHeight",
    }
    for control_id in positive_numeric_ids:
        control = parser.controls[control_id]
        assert control["tag"] == "input" and control["attrs"].get("type", "").lower() == "number", (
            f"#{control_id} must be an input[type=number]"
        )
        assert "disabled" not in control["attrs"], f"#{control_id} must be enabled"
        assert _numeric_attr(control, "min") > 0, f"#{control_id} must have a positive minimum"

    gap = parser.controls["effectGap"]
    assert gap["tag"] == "input" and gap["attrs"].get("type", "").lower() == "number", (
        "#effectGap must be an input[type=number]"
    )
    assert "disabled" not in gap["attrs"], "#effectGap must be enabled"
    assert _numeric_attr(gap, "min") >= 0, "#effectGap must permit a zero gap"

    for control_id in ("effectPivotX", "effectPivotY"):
        control = parser.controls[control_id]
        assert control["tag"] == "input" and control["attrs"].get("type", "").lower() in {"number", "range"}, (
            f"#{control_id} must be a numeric input"
        )
        assert "disabled" not in control["attrs"], f"#{control_id} must be enabled"
        assert _numeric_attr(control, "min") == 0
        assert _numeric_attr(control, "max") == 1

    timing = parser.controls[next(iter(timing_controls))]
    assert timing["tag"] == "input" and timing["attrs"].get("type", "").lower() == "number", (
        "the sole effect timing control must be an input[type=number]"
    )
    assert "disabled" not in timing["attrs"], "the sole effect timing control must be enabled"
    assert _numeric_attr(timing, "min") > 0, "effect timing must have a positive minimum"


def test_real_animation_mode_control_exposes_accessible_one_shot_option():
    parser = _IdParser()
    parser.feed(HTML)
    control = parser.controls["animMode"]
    assert control["tag"] == "select"
    assert "once" in _option_values(control)
    assert re.search(
        r'<option\s+value=["\']once["\'][^>]*>\s*(?:1회|한 번|Once|One[- ]shot)\s*</option>',
        HTML,
        flags=re.IGNORECASE,
    ), "#animMode once option needs a clear visible label"


def test_browser_sequence_uses_complete_b2_contract(browser_effect_runtime):
    payload = browser_effect_runtime["sequence"]["payload"]
    assert payload["asset_family"] == "sprite" and payload["asset_type"] == "effect"
    effect = payload["sprite"]
    assert effect["animation_mode"] == "effect_sequence"
    _assert_effect_contract(effect, _effect_contract())
    assert effect["no_baked_vfx"] is False
    assert not (ACTOR_ONLY_FIELDS & effect.keys())
    _assert_effect_direction_is_neutral(effect)


def test_browser_effect_grid_capacity_is_canonicalized():
    functions = _function_source("buildSpriteContract")
    helpers = "\n".join(
        _const_callable_source(name)
        for name in ("controlValue", "controlNumber", "clampFamilyNumber")
    )
    result = _run_node(f"""
const controls = Object.create(null);
const $ = id => controls[id] || null;
const selectedAssetFamily = 'sprite';
{helpers}
const pixelPresetFrameCount = () => 4;
{functions}
function build(rows, columns) {{
  Object.assign(controls, {{
    assetSubtype: {{value: 'effect'}}, effectSequenceMode: {{value: 'sequence'}},
    effectFrameCount: {{value: '7'}}, effectRows: {{value: String(rows)}},
    effectColumns: {{value: String(columns)}}
  }});
  return buildSpriteContract('effect');
}}
process.stdout.write(JSON.stringify([build(1, 1), build(2, 1)]));
""")
    assert [(item["frame_count"], item["rows"], item["columns"]) for item in result] == [
        (7, 1, 7), (7, 2, 4),
    ]


def test_effect_animation_preset_has_effect_semantics():
    result = _run_node(f"""
const controls = Object.create(null);
const $ = id => controls[id] || null;
const PIXEL_ACTOR_ASSET_TYPES = new Set(['character', 'monster', 'npc']);
const PIXEL_EFFECT_ASSET_TYPES = new Set(['effect']);
{_function_source('isPixelActorAssetType')}
{_function_source('isPixelEffectAssetType')}
{_function_source('effectivePixelAnimationPreset')}
controls.pixelAssetType = {{value: 'effect'}};
controls.effectSequenceMode = {{value: 'sequence'}};
const sequence = effectivePixelAnimationPreset();
controls.effectSequenceMode.value = 'static';
process.stdout.write(JSON.stringify({{sequence, staticEffect: effectivePixelAnimationPreset()}}));
""")
    assert result == {"sequence": "effect_sequence", "staticEffect": "static"}


def test_existing_effect_baseline_remains_intact(browser_effect_runtime):
    """Already-shipped B1 behavior must not become an accidental RED root."""
    effect = browser_effect_runtime["sequence"]["payload"]["sprite"]
    assert effect["animation_mode"] == "effect_sequence"
    assert effect["effect_category"] == "Impact"
    assert effect["frame_count"] == 7
    assert effect["no_baked_vfx"] is False


def test_browser_static_and_sequence_are_distinct_with_common_contract(browser_effect_runtime):
    sequence = browser_effect_runtime["sequence"]["payload"]["sprite"]
    static_effect = browser_effect_runtime["staticEffect"]["payload"]["sprite"]
    assert sequence["sequence_mode"] == "sequence"
    assert sequence["animation_mode"] == "effect_sequence"
    assert sequence["frame_count"] == 7
    assert static_effect["sequence_mode"] == "static"
    assert static_effect["animation_mode"] == "static"
    assert static_effect["frame_count"] == 1

    common_fields = EFFECT_FIELDS - {"sequence_mode", "frame_count"}
    assert {key: static_effect[key] for key in common_fields} == {
        key: sequence[key] for key in common_fields
    }
    _assert_effect_timing(sequence)
    _assert_effect_timing(static_effect)

    # Exercise the actual browser payload through server normalization so the
    # static common contract is not covered by two disconnected fixtures.
    server_static = server.normalize_asset_generation_payload(
        browser_effect_runtime["staticEffect"]["payload"]
    )["sprite"]
    assert server_static["animation_mode"] == "static"
    assert server_static["frame_count"] == 1
    assert {key: server_static[key] for key in common_fields} == {
        key: static_effect[key] for key in common_fields
    }
    _control_id, chosen_timing_field, _timing_value = _chosen_timing_spec()
    assert server_static[chosen_timing_field] == static_effect[chosen_timing_field]
    _assert_effect_timing(server_static)


def test_browser_sequence_prompt_has_labelled_generation_semantics(browser_effect_runtime):
    _assert_effect_prompt(browser_effect_runtime["sequence"]["prompt"])


def test_browser_effect_sequence_prompt_rejects_static_contradictions(browser_effect_runtime):
    _assert_no_effect_sequence_contradictions(browser_effect_runtime["sequence"]["prompt"])


def test_server_preserves_complete_sequence_contract():
    normalized = server.normalize_asset_generation_payload(_raw_effect())
    effect = normalized["sprite"]
    assert effect["animation_mode"] == "effect_sequence"
    _assert_effect_contract(effect, _effect_contract())
    assert effect["no_baked_vfx"] is False
    assert not (ACTOR_ONLY_FIELDS & effect.keys())
    _assert_effect_direction_is_neutral(effect)


@pytest.mark.parametrize("rows,columns,expected_columns", [(1, 1, 7), (2, 1, 4)])
def test_server_effect_grid_capacity_is_canonicalized(rows, columns, expected_columns):
    effect = server.normalize_asset_generation_payload(
        _raw_effect(frame_count=7, rows=rows, columns=columns)
    )["sprite"]
    assert effect["frame_count"] == 7
    assert effect["rows"] == rows
    assert effect["columns"] == expected_columns
    assert effect["rows"] * effect["columns"] >= effect["frame_count"]


def test_selected_reference_effect_uses_structured_generation_payload():
    function = _function_source("generateFrontIdleFromSelected")
    result = _run_node(f"""
const controls = {{
  pixelAssetType: {{value: 'effect'}}, effectSequenceMode: {{value: 'sequence'}},
  generateFrontIdleFromSelected: {{disabled: false}}, pixelTargetDirection: {{value: 'S'}},
  pixelReferenceDirection: {{value: 'S'}}, pixelChromaMode: {{value: 'global'}}
}};
const $ = id => controls[id] || null;
const reference = {{type: 'image'}};
const selectedLayerObject = () => reference;
const isPixelActorAssetType = () => false;
const isPixelEffectAssetType = () => true;
const effectivePixelAnimationPreset = () => 'effect_sequence';
const animationPresetSpec = () => ({{key: 'effect_sequence', label: 'Effect sequence', frames: 7}});
const buildSelectedActionSpritePrompt = () => 'structured effect prompt';
const imageObjectToDataUrl = () => 'data:image/png;base64,REFERENCE';
const directionLabel = value => value;
const setStatus = () => {{}};
const alert = message => {{ throw new Error(message); }};
let builderBase = null;
const buildAssetGenerationPayload = base => {{
  builderBase = base;
  return {{...base, asset_family: 'sprite', asset_type: 'effect', sprite: {{
    sequence_mode: 'sequence', animation_mode: 'effect_sequence', frame_count: 7,
    rows: 2, columns: 4
  }}}};
}};
let fetchCall = null;
const fetch = async (endpoint, options) => {{
  fetchCall = {{endpoint, options}};
  return {{ok: false, json: async () => ({{error: 'inert stop'}})}};
}};
{function}
(async () => {{
  try {{ await generateFrontIdleFromSelected(); }} catch (_) {{}}
  const body = JSON.parse(fetchCall.options.body);
  const actorFields = ['direction_mode', 'target_direction', 'reference_direction', 'animation_mode', 'frame_count', 'chroma_mode'];
  process.stdout.write(JSON.stringify({{
    endpoint: fetchCall.endpoint, body, builderBase,
    leakedActorFields: actorFields.filter(key => Object.prototype.hasOwnProperty.call(body, key))
  }}));
}})().catch(error => {{ console.error(error); process.exitCode = 1; }});
""")
    assert result["endpoint"] == "/api/generate-reference"
    assert result["builderBase"]["reference_image"].startswith("data:image/png;base64,")
    assert result["body"]["asset_family"] == "sprite"
    assert result["body"]["asset_type"] == "effect"
    assert result["body"]["sprite"]["animation_mode"] == "effect_sequence"
    assert result["body"]["sprite"]["frame_count"] == 7
    assert result["leakedActorFields"] == []


@pytest.mark.parametrize(
    "effect_loop,preview_mode",
    (("one-shot", "once"), ("loop", "loop"), ("ping-pong", "pingpong")),
)
def test_selected_reference_success_preserves_effect_grid_timing_and_loop(
    effect_loop, preview_mode,
):
    """The free browser harness reaches successful fetch/addImage configuration."""
    function = _function_source("generateFrontIdleFromSelected")
    result = _run_node(f"""
const controls = Object.create(null);
const $ = id => controls[id] || null;
const reference = {{type: 'image', name: 'reference'}};
const generated = {{type: 'image', name: 'generated'}};
const selectedLayerObject = () => reference;
const isPixelActorAssetType = type => type === 'character';
const isPixelEffectAssetType = type => type === 'effect';
const effectivePixelAnimationPreset = () => controls.pixelAssetType.value === 'effect' ? 'effect_sequence' : 'idle';
const animationPresetSpec = preset => ({{key: preset, label: preset, frames: 7}});
const buildSelectedActionSpritePrompt = () => 'inert structured prompt';
const imageObjectToDataUrl = () => 'data:image/png;base64,REFERENCE';
const directionLabel = value => value;
const buildAssetGenerationPayload = base => ({{...base, asset_family: 'sprite', asset_type: 'effect'}});
const setStatus = () => {{}};
const alert = message => {{ throw new Error(message); }};
const fetch = async () => ({{ok: true, json: async () => ({{success: true, url: '/inert.png'}})}});
const withCacheBust = url => url;
const addGallery = () => {{}};
const addImageUrl = async () => generated;
const canvas = {{setActiveObject: () => {{}}}};
const rememberSelectedLayer = () => {{}};
const nameOf = object => object.name;
const removeSpriteGuideObjects = () => {{}};
const buildGridSpriteSlices = () => [];
const buildAnimationPreview = async () => [];
const recordPixelAssetResult = () => {{}};
let spriteSlices = [];
let selectedSpriteSliceId = null;
let effectDefaultsCalls = 0;
let actorDefaultsCalls = 0;
const applyPixelWorkflowGridDefaults = () => {{
  effectDefaultsCalls += 1;
  controls.gridRows.value = controls.effectRows.value;
  controls.gridCols.value = controls.effectColumns.value;
  controls.gridGapX.value = controls.effectGap.value;
  controls.gridGapY.value = controls.effectGap.value;
  controls.gridCellW.value = controls.effectEnvelopeWidth.value;
  controls.gridCellH.value = controls.effectEnvelopeHeight.value;
  controls.animFrameCount.value = controls.effectFrameCount.value;
  controls.animFps.value = controls.effectFps.value;
  controls.animMode.value = controls.effectLoop.value === 'one-shot'
    ? 'once'
    : (controls.effectLoop.value === 'ping-pong' ? 'pingpong' : 'loop');
}};
const setFrontIdleGridForImage = () => {{
  actorDefaultsCalls += 1;
  controls.gridRows.value = '1';
  controls.animFps.value = '5';
  controls.animMode.value = 'loop';
}};
{function}
function setControls(type, loop) {{
  const values = {{
    pixelAssetType: type, generateFrontIdleFromSelected: '', pixelTargetDirection: 'S',
    pixelReferenceDirection: 'S', pixelChromaMode: 'global', effectSequenceMode: 'sequence',
    effectRows: 2, effectColumns: 4, effectGap: 3, effectEnvelopeWidth: 80,
    effectEnvelopeHeight: 48, effectFrameCount: 7, effectFps: 20, effectLoop: loop,
    gridRows: 99, gridCols: 99, gridGapX: 99, gridGapY: 99,
    gridCellW: 99, gridCellH: 99, animFrameCount: 99, animFps: 99, animMode: 'poison'
  }};
  for (const [id, value] of Object.entries(values)) controls[id] = {{value: String(value), disabled: false}};
}}
(async () => {{
  setControls('effect', {json.dumps(effect_loop)});
  await generateFrontIdleFromSelected();
  const effect = Object.fromEntries([
    'effectRows', 'effectColumns', 'effectGap', 'effectEnvelopeWidth', 'effectEnvelopeHeight',
    'effectFrameCount', 'effectFps', 'effectLoop', 'gridRows', 'gridCols', 'gridGapX',
    'gridGapY', 'gridCellW', 'gridCellH', 'animFrameCount', 'animFps', 'animMode'
  ].map(id => [id, controls[id].value]));
  const afterEffect = {{effectDefaultsCalls, actorDefaultsCalls}};
  setControls('character', 'one-shot');
  await generateFrontIdleFromSelected();
  process.stdout.write(JSON.stringify({{
    effect, afterEffect, finalCalls: {{effectDefaultsCalls, actorDefaultsCalls}}
  }}));
}})().catch(error => {{ console.error(error); process.exitCode = 1; }});
""")
    assert result["afterEffect"] == {"effectDefaultsCalls": 1, "actorDefaultsCalls": 0}
    assert result["effect"] == {
        "effectRows": "2", "effectColumns": "4", "effectGap": "3",
        "effectEnvelopeWidth": "80", "effectEnvelopeHeight": "48",
        "effectFrameCount": "7", "effectFps": "20", "effectLoop": effect_loop,
        "gridRows": "2", "gridCols": "4", "gridGapX": "3", "gridGapY": "3",
        "gridCellW": "80", "gridCellH": "48", "animFrameCount": "7",
        "animFps": "20", "animMode": preview_mode,
    }
    assert result["finalCalls"] == {"effectDefaultsCalls": 1, "actorDefaultsCalls": 1}


def test_real_grid_defaults_map_all_effect_loop_modes_and_leave_actor_mode_alone():
    """Exercise the production helper rather than reproducing its mapping in a spy."""
    funcs = "\n".join(_function_source(name) for name in (
        "directionLabelsForMode", "pixelAnimationDefaultFrames", "isPixelActorAssetType",
        "isPixelEffectAssetType", "effectivePixelAnimationPreset", "requestedPixelFrameCount",
        "pixelPresetFrameCount", "applyPixelWorkflowGridDefaults",
    ))
    result = _run_node(f"""
const controls = Object.create(null);
const $ = id => controls[id] || null;
const PIXEL_ACTOR_ASSET_TYPES = new Set(['character', 'monster', 'npc']);
const PIXEL_EFFECT_ASSET_TYPES = new Set(['effect']);
{_object_constant_source('PIXEL_ANIMATION_PRESET_DEFAULT_FRAMES')}
const activeSpriteTarget = () => null;
const selectedLayerObject = () => null;
const imageDisplayedSize = () => null;
{funcs}
for (const [id, value] of Object.entries({{
  pixelAssetType: 'effect', effectSequenceMode: 'sequence', effectFrameCount: 3,
  effectRows: 1, effectColumns: 3, effectGap: 0,
  effectEnvelopeWidth: 64, effectEnvelopeHeight: 64, effectFps: 12,
  pixelDirectionMode: 'single', pixelAnimationPreset: 'idle',
  pixelFrameW: 32, pixelFrameH: 32, gridCols: 1, gridRows: 1,
  gridCellW: 32, gridCellH: 32, gridGapX: 0, gridGapY: 0,
  animFrameCount: 1, animFps: 8, animMode: 'poison'
}})) controls[id] = {{value: String(value)}};
const mapped = {{}};
for (const loop of ['one-shot', 'loop', 'ping-pong']) {{
  controls.effectLoop = {{value: loop}};
  controls.animMode.value = 'poison';
  applyPixelWorkflowGridDefaults();
  mapped[loop] = controls.animMode.value;
}}
controls.pixelAssetType.value = 'character';
controls.animMode.value = 'actor-existing-mode';
applyPixelWorkflowGridDefaults();
process.stdout.write(JSON.stringify({{mapped, actorMode: controls.animMode.value}}));
""")
    assert result == {
        "mapped": {"one-shot": "once", "loop": "loop", "ping-pong": "pingpong"},
        "actorMode": "actor-existing-mode",
    }


def test_real_animation_preview_once_draws_each_frame_once_and_stops_on_final_frame():
    """Use deterministic fake timers around the production playback function."""
    result = _run_node(f"""
const controls = {{animMode: {{value: 'once'}}, animFps: {{value: '10'}}}};
const $ = id => controls[id] || null;
const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
const draws = [];
const stages = [{{set innerHTML(value) {{ draws.push(value); }}}}];
const animationPreviewStages = () => stages;
const statuses = [];
const setStatus = value => statuses.push(value);
let animationPreviewTimer = null;
let nextTimer = 1;
const timers = new Map();
const cleared = [];
const setInterval = (callback, delay) => {{
  const id = nextTimer++;
  timers.set(id, {{callback, delay}});
  return id;
}};
const clearInterval = id => {{ cleared.push(id); timers.delete(id); }};
{_function_source('stopAnimationPreview')}
{_function_source('playAnimationPreview')}
playAnimationPreview(['frame-a', 'frame-b', 'frame-c']);
let ticks = 0;
while (timers.size && ticks < 10) {{
  const timer = timers.values().next().value;
  timer.callback();
  ticks += 1;
}}
process.stdout.write(JSON.stringify({{
  draws: draws.map(html => html.match(/src=\"([^\"]+)/)[1]),
  ticks, activeTimers: timers.size, timerState: animationPreviewTimer,
  cleared: cleared.length,
}}));
""")
    assert result == {
        "draws": ["frame-a", "frame-b", "frame-c"],
        "ticks": 2,
        "activeTimers": 0,
        "timerState": None,
        "cleared": 1,
    }


def test_server_static_and_sequence_runtime_cases_preserve_common_contract():
    static_effect = server.normalize_asset_generation_payload(
        _raw_effect(sequence_mode="static", frame_count=12)
    )["sprite"]
    sequence = server.normalize_asset_generation_payload(
        _raw_effect(sequence_mode="sequence", frame_count=11)
    )["sprite"]
    assert static_effect["sequence_mode"] == "static"
    assert static_effect["animation_mode"] == "static"
    assert static_effect["frame_count"] == 1
    assert sequence["sequence_mode"] == "sequence"
    assert sequence["animation_mode"] == "effect_sequence"
    assert sequence["frame_count"] == 11

    common_fields = EFFECT_FIELDS - {"sequence_mode", "frame_count", "columns"}
    assert {key: static_effect[key] for key in common_fields} == {
        key: sequence[key] for key in common_fields
    }
    assert static_effect["columns"] == 4
    assert sequence["columns"] == 6
    _assert_effect_timing(sequence)
    _assert_effect_timing(static_effect)


def test_server_effect_enums_accept_members_and_fallback_safely():
    allowed = {
        "sequence_mode": {"static", "sequence"},
        "loop": {"one-shot", "loop", "ping-pong"},
        "size_basis": {"pixels", "tile", "actor-relative", "world", "screen"},
    }
    for field, members in allowed.items():
        for member in members:
            assert server.normalize_asset_generation_payload(_raw_effect(**{field: member}))["sprite"][field] == member
        fallback = server.normalize_asset_generation_payload(_raw_effect(**{field: "NOT-A-MEMBER"}))["sprite"][field]
        assert fallback in members


def test_valid_ui_effect_category_survives_browser_and_server(browser_effect_runtime):
    category = "Impact"
    assert re.search(r'<option\s+value=["\']Impact["\']', HTML)
    browser_effect = browser_effect_runtime["sequence"]["payload"]["sprite"]
    assert browser_effect["effect_category"] == category
    normalized = server.normalize_asset_generation_payload(
        _raw_effect(effect_category=browser_effect["effect_category"])
    )["sprite"]
    assert normalized["effect_category"] == category

def test_server_effect_numeric_values_normalize_positive_with_zero_gap_and_clamped_pivot():
    _control_id, timing_field, _timing_value = _chosen_timing_spec()
    normalized = server.normalize_asset_generation_payload(_raw_effect(
        frame_count=-99, rows=-99, columns=-99,
        gap=-99, envelope_width=-99, envelope_height=-99,
        pivot={"preset": "source", "x": -99, "y": 99},
        **{timing_field: -99},
    ))["sprite"]
    zero_gap = server.normalize_asset_generation_payload(_raw_effect(gap=0))["sprite"]
    timing = EFFECT_TIMING_FIELDS & normalized.keys()
    assert timing == {timing_field}
    assert all(normalized[key] > 0 for key in timing)
    for key in ("frame_count", "rows", "columns", "envelope_width", "envelope_height"):
        assert normalized[key] > 0
    assert normalized["gap"] == 0 and zero_gap["gap"] == 0
    assert 0 <= normalized["pivot"]["x"] <= 1
    assert 0 <= normalized["pivot"]["y"] <= 1


def test_server_rejects_all_poisoned_actor_cleanup_state():
    raw = _raw_effect()
    raw["sprite"].update({key: {"poison": True} for key in ACTOR_ONLY_FIELDS})
    raw["sprite"]["direction_mode"] = "8-way-actor-poison"
    normalized = server.normalize_asset_generation_payload(raw)["sprite"]
    assert not (ACTOR_ONLY_FIELDS & normalized.keys())
    _assert_effect_direction_is_neutral(normalized)
    assert normalized["no_baked_vfx"] is False


@pytest.mark.parametrize("route", ["/api/generate", "/api/generate-reference"])
def test_effect_generation_routes_reach_postprocessor_with_normalized_contract(
    monkeypatch, tmp_path, route,
):
    image = Image.new("RGBA", (2, 2), (255, 0, 255, 128))
    source = io.BytesIO()
    image.save(source, format="PNG")
    raw_png = source.getvalue()
    encoded = base64.b64encode(raw_png).decode("ascii")
    provider_image = tmp_path / "inert-provider.png"
    provider_image.write_bytes(raw_png)

    def actor_cleanup_must_not_run(*args, **kwargs):
        del args, kwargs
        raise AssertionError("effect route invoked actor cleanup")

    effect_postprocess_call = {}

    def inert_effect_postprocess(*args, **kwargs):
        effect_postprocess_call["args"] = args
        effect_postprocess_call["kwargs"] = kwargs
        return args[0], {"status": "stub-effect-postprocess", "method": "stub"}

    class InertProvider:
        def generate(self, *args, **kwargs):
            del args, kwargs
            return {
                "success": True,
                "image": str(provider_image),
                "model": "stub-model",
                "provider": "stub-provider",
            }

    monkeypatch.setattr(server, "GENERATED", tmp_path)
    monkeypatch.setattr(server, "load_provider", lambda: InertProvider())
    monkeypatch.setattr(
        server,
        "collect_codex_reference_effect_b64",
        lambda *args, **kwargs: (encoded, "stub-model", "stub-quality"),
    )
    monkeypatch.setattr(server, "postprocess_pixel_generation_bytes", actor_cleanup_must_not_run)
    monkeypatch.setattr(server, "postprocess_effect_generation_bytes", inert_effect_postprocess)

    request = _raw_effect()
    request.update({"reference_image": "stub-reference", "background_mode": "none"})
    body = json.dumps(request).encode("utf-8")
    response = {}
    handler = object.__new__(server.Handler)
    handler.__dict__.update(
        path=route,
        headers={"Content-Length": str(len(body))},
        rfile=io.BytesIO(body),
        send_json=lambda code, payload: response.update(code=code, payload=payload),
    )
    handler.do_POST()

    assert response["code"] == 200
    assert Path(response["payload"]["path"]).is_file()
    normalized_effect = server.normalize_asset_generation_payload(request)["sprite"]
    _assert_effect_contract(normalized_effect, _effect_contract())
    assert normalized_effect["no_baked_vfx"] is False

    # Require normalized metadata at both existing route/postprocessor boundaries,
    # without prescribing B3 image operations or any QA response schema.
    boundary_contract = None
    candidates = list(effect_postprocess_call["args"][1:]) + [
        effect_postprocess_call["kwargs"],
        *effect_postprocess_call["kwargs"].values(),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict) and isinstance(candidate.get("sprite"), dict):
            candidate = candidate["sprite"]
        if isinstance(candidate, dict) and EFFECT_FIELDS <= candidate.keys():
            boundary_contract = candidate
            break
    assert boundary_contract is not None, (
        f"{route} effect postprocessor boundary dropped normalized contract"
    )
    _assert_effect_contract(boundary_contract, normalized_effect)
    boundary_timing = EFFECT_TIMING_FIELDS & boundary_contract.keys()
    assert {key: boundary_contract[key] for key in boundary_timing} == {
        key: normalized_effect[key] for key in boundary_timing
    }


def test_server_effect_prompt_is_semantic_and_noncontradictory():
    normalized = server.normalize_asset_generation_payload(_raw_effect())
    prompt = server.build_asset_family_prompt(normalized)
    _assert_effect_prompt(prompt)
    _assert_no_effect_sequence_contradictions(prompt)


def test_effect_contract_drives_grid_preview_and_actual_export_selection():
    """B2 wiring only; ZIP creation/download and image slicing stay inert."""
    funcs = "\n".join(_function_source(name) for name in (
        "directionLabelsForMode", "pixelAnimationDefaultFrames", "isPixelActorAssetType",
        "isPixelEffectAssetType", "effectivePixelAnimationPreset", "requestedPixelFrameCount",
        "pixelPresetFrameCount", "applyPixelWorkflowGridDefaults", "currentAnimationSpriteSlices",
        "exportGridSpriteSlicesZip",
    ))
    result = _run_node(f"""
const controls = Object.create(null);
const $ = id => controls[id] || null;
const PIXEL_ACTOR_ASSET_TYPES = new Set(['character', 'monster', 'npc']);
const PIXEL_EFFECT_ASSET_TYPES = new Set(['effect']);
{_object_constant_source('PIXEL_ANIMATION_PRESET_DEFAULT_FRAMES')}
const activeSpriteTarget = () => ({{name: 'inert-effect-sheet'}});
const selectedLayerObject = () => null;
const imageDisplayedSize = () => null;
const buildGridSpriteSlices = () => capacitySlices;
const currentGridSpriteSlices = () => capacitySlices;
const renderSpriteGuides = () => {{}};
const spriteSliceDataUrl = async slice => {{ exported.push(slice.index); return 'data:image/png;base64,'; }};
const dataUrlToBytes = () => new Uint8Array();
const spriteSliceCanvasBox = slice => ({{x: slice.x, y: slice.y}});
const buildStoredZip = () => ({{inert: true}});
const downloadBlob = () => {{}};
const spriteSummary = () => {{}};
const setStatus = () => {{}};
const alert = message => {{ throw new Error(message); }};
const capacitySlices = Array.from({{length: 8}}, (_, index) => ({{
  index, row: Math.floor(index / 4), col: index % 4,
  x: (index % 4) * 83, y: Math.floor(index / 4) * 51, width: 80, height: 48,
}}));
let spriteSlices = [];
let selectedSpriteSliceId = null;
const exported = [];
{funcs}
for (const [id, value] of Object.entries({{
  pixelAssetType: 'effect', assetSubtype: 'effect', effectSequenceMode: 'sequence',
  effectFrameCount: 7, effectRows: 2, effectColumns: 1, effectGap: 3,
  effectEnvelopeWidth: 80, effectEnvelopeHeight: 48,
  pixelDirectionMode: 'single', pixelTargetDirection: 'S', pixelAnimationPreset: 'ui_static',
  pixelFrameW: 32, pixelFrameH: 32, gridCols: 1, gridRows: 1,
  gridCellW: 32, gridCellH: 32, gridGapX: 9, gridGapY: 9,
  animFrameCount: 1, animFps: 1
}})) controls[id] = {{value: String(value)}};
(async () => {{
  const requested = requestedPixelFrameCount();
  const grid = applyPixelWorkflowGridDefaults();
  spriteSlices = capacitySlices;
  const previewCount = currentAnimationSpriteSlices().length;
  await exportGridSpriteSlicesZip();
  process.stdout.write(JSON.stringify({{
    requested, gridFrames: grid.frames, capacity: capacitySlices.length,
    gridCols: +controls.gridCols.value, gridRows: +controls.gridRows.value,
    gridGapX: +controls.gridGapX.value, gridGapY: +controls.gridGapY.value,
    gridCellW: +controls.gridCellW.value, gridCellH: +controls.gridCellH.value,
    previewControl: +controls.animFrameCount.value, previewCount,
    exportedCount: exported.length, exported,
  }}));
}})().catch(error => {{ console.error(error); process.exitCode = 1; }});
""")
    assert result == {
        "requested": 7,
        "gridFrames": 7,
        "capacity": 8,
        "gridCols": 4,
        "gridRows": 2,
        "gridGapX": 3,
        "gridGapY": 3,
        "gridCellW": 80,
        "gridCellH": 48,
        "previewControl": 7,
        "previewCount": 7,
        "exportedCount": 7,
        "exported": list(range(7)),
    }
