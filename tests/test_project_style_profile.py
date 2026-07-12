"""H1 RED contract for the canonical project style profile.

This test deliberately executes declarations extracted from ``src/main.js``.  It
must not contain a shadow implementation of the normalizer or resolver.  Until
H2 supplies those declarations the three declaration tests are the expected RED
and runtime cases are skipped rather than failing because of a broken harness.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

import server

ROOT = Path(__file__).resolve().parents[1]
JS_PATH = ROOT / "src" / "main.js"
JS = JS_PATH.read_text(encoding="utf-8")
REQUIRED_DECLARATIONS = (
    "DEFAULT_STYLE_PROFILE",
    "normalizeStyleProfile",
    "resolveStyleProfileForFamily",
)
FAMILIES = ("sprite", "tile", "ui", "object")
STYLE_FIELDS = {
    "palette", "outline", "shading", "material_treatment", "pixel_density",
    "silhouette", "contrast", "anti_aliasing",
}
TOP_LEVEL_FIELDS = {
    "schema_version", "id", "name", "version", "created_at", "updated_at",
    *STYLE_FIELDS, "reference_assets", "forbidden_elements", "family_overrides",
}


def _declaration_source(name: str) -> str | None:
    """Extract one complete production const/function declaration."""
    match = re.search(
        rf"\b(?:const\s+{re.escape(name)}\s*=|function\s+{re.escape(name)}\s*\([^)]*\)\s*)",
        JS,
    )
    if not match:
        return None
    depths = {"(": 0, "[": 0, "{": 0}
    closing = {")": "(", "]": "[", "}": "{"}
    quote = None
    escaped = False
    saw_body = False
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
            saw_body = saw_body or char == "{"
        elif char in closing:
            opener = closing[char]
            depths[opener] -= 1
            if min(depths.values()) < 0:
                raise AssertionError(f"unbalanced production declaration: {name}")
            if name.startswith("resolve") or name.startswith("normalize"):
                if saw_body and char == "}" and not any(depths.values()):
                    end = index + 1
                    if JS[end:end + 1] == ";":
                        end += 1
                    return JS[match.start():end]
        elif char == ";" and not any(depths.values()):
            return JS[match.start():index + 1]
    raise AssertionError(f"unterminated production declaration: {name}")


@pytest.mark.parametrize("name", REQUIRED_DECLARATIONS)
def test_h1_production_style_profile_declaration_exists(name):
    assert _declaration_source(name) is not None, (
        f"H1 expected RED: production declaration {name} is missing from src/main.js"
    )


def _valid_profile():
    return {
        "schema_version": "asset-studio.style-profile/v1",
        "id": "dungeon-cleanup",
        "name": "Dungeon Cleanup",
        "version": 1,
        "created_at": "2026-07-11T00:00:00.000Z",
        "updated_at": "2026-07-11T00:00:00.000Z",
        "palette": {"colors": ["#102030", "#AABBCC", "#ffffff00"], "mode": "limited"},
        "outline": {"mode": "dark", "width": 1, "color": "#101010"},
        "shading": {"mode": "cel", "steps": 3, "light_direction": "top-left"},
        "material_treatment": {"mode": "matte", "detail": "medium"},
        "pixel_density": {"mode": "pixel-art", "scale": 2},
        "silhouette": {"mode": "readable", "complexity": "medium"},
        "contrast": {"mode": "high", "value": 0.8},
        "anti_aliasing": {"mode": "off"},
        "reference_assets": [{"asset_id": "layer-1", "weight": 1}],
        "forbidden_elements": ["text", "logo", "watermark"],
        "family_overrides": {family: {} for family in FAMILIES},
    }


def _runtime_source() -> str:
    missing = [name for name in REQUIRED_DECLARATIONS if _declaration_source(name) is None]
    if missing:
        pytest.skip("runtime contracts await production declarations: " + ", ".join(missing))
    declarations = [_declaration_source(name) for name in REQUIRED_DECLARATIONS]
    assert all(source is not None for source in declarations)
    return "\n".join(source for source in declarations if source is not None)


def _run_node(script: str):
    completed = subprocess.run(
        ["node", "-e", _runtime_source() + "\n" + script],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(completed.stdout)


def _normalize(profile):
    encoded = json.dumps(profile, ensure_ascii=False, allow_nan=True)
    return _run_node(f"""
const input = {encoded};
try {{ console.log(JSON.stringify({{ok:true, value:normalizeStyleProfile(input)}})); }}
catch (error) {{ console.log(JSON.stringify({{ok:false, error:String(error && error.message || error)}})); }}
""")


def test_canonical_default_and_valid_normalization_are_exact_and_detached():
    profile = _valid_profile()
    result = _run_node(f"""
const input = {json.dumps(profile)};
const before = JSON.stringify(input);
const value = normalizeStyleProfile(input);
value.palette.colors[0] = '#000000';
console.log(JSON.stringify({{
  defaultValue: DEFAULT_STYLE_PROFILE,
  keys: Object.keys(normalizeStyleProfile(input)).sort(),
  familyKeys: Object.keys(normalizeStyleProfile(input).family_overrides).sort(),
  unmutated: before === JSON.stringify(input),
  detached: input.palette.colors[0] === '#102030'
}}));
""")
    assert set(result["keys"]) == TOP_LEVEL_FIELDS
    assert result["familyKeys"] == sorted(FAMILIES)
    assert result["unmutated"] and result["detached"]
    default = result["defaultValue"]
    assert default["schema_version"] == "asset-studio.style-profile/v1"
    assert set(default) == TOP_LEVEL_FIELDS


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(extra=True),
    lambda p: p.update(schema_version="v1"),
    lambda p: p.update(id=""),
    lambda p: p.update(name="x" * 10000),
    lambda p: p.update(version=0),
    lambda p: p.update(version=1.5),
    lambda p: p.update(created_at="2026-07-11"),
    lambda p: p.update(updated_at="not-a-date"),
    lambda p: p["palette"].update(colors=["red"]),
    lambda p: p["outline"].update(mode="unknown"),
    lambda p: p["outline"].update(width=-1),
    lambda p: p["shading"].update(steps=0),
    lambda p: p["contrast"].update(value=float("nan")),
    lambda p: p["pixel_density"].update(scale=float("inf")),
    lambda p: p.update(reference_assets=[{}] * 10000),
    lambda p: p.update(forbidden_elements=["x"] * 10000),
    lambda p: p["family_overrides"].update(effect={}),
    lambda p: p["family_overrides"]["sprite"].update(tile_size=32),
    lambda p: p["family_overrides"]["ui"].update(prompt="production field"),
    lambda p: p["family_overrides"]["object"].update(output={}),
])
def test_malformed_profiles_fail_closed(mutation):
    profile = _valid_profile()
    mutation(profile)
    assert _normalize(profile)["ok"] is False


def test_json_prototype_cycle_depth_node_string_array_and_utf8_budgets_fail_closed():
    result = _run_node("""
const base = JSON.parse(process.argv[1] || '{}');
const attacks = [];
attacks.push(JSON.parse(JSON.stringify(base).replace(/}$/, ',"__proto__":{"polluted":true}}')));
const cycle = structuredClone(base); cycle.palette.cycle = cycle; attacks.push(cycle);
let deep = {}; let cursor = deep; for (let i=0;i<1000;i++){cursor.x={};cursor=cursor.x;}
const depth = structuredClone(base); depth.palette.deep=deep; attacks.push(depth);
const nodes = structuredClone(base); nodes.palette.nodes=Array.from({length:100000},()=>({x:1})); attacks.push(nodes);
const string = structuredClone(base); string.name='x'.repeat(1000000); attacks.push(string);
const array = structuredClone(base); array.forbidden_elements=Array(100000).fill('x'); attacks.push(array);
const utf8 = structuredClone(base); utf8.name='😀'.repeat(1000000); attacks.push(utf8);
console.log(JSON.stringify(attacks.map(value => {try{normalizeStyleProfile(value);return false}catch{return true}})));
""".replace("process.argv[1] || '{}'", json.dumps(json.dumps(_valid_profile()))))
    # The production attack list above contains seven entries.
    assert result == [True] * 7


def test_family_resolver_applies_only_selected_override_without_mutation_or_aliasing():
    profile = _valid_profile()
    profile["family_overrides"]["sprite"] = {"outline": {"mode": "none", "width": 0, "color": "#000000"}}
    profile["family_overrides"]["tile"] = {"contrast": {"mode": "low", "value": 0.2}}
    result = _run_node(f"""
const input={json.dumps(profile)}; const before=JSON.stringify(input);
const sprite=resolveStyleProfileForFamily(input,'sprite');
const tile=resolveStyleProfileForFamily(input,'tile');
sprite.palette.colors[0]='#000000';
console.log(JSON.stringify({{
  sprite, tile, unmutated:before===JSON.stringify(input),
  detached:input.palette.colors[0]==='#102030'
}}));
""")
    assert result["sprite"]["outline"]["mode"] == "none"
    assert result["sprite"]["contrast"]["value"] == 0.8
    assert result["tile"]["contrast"]["value"] == 0.2
    assert result["tile"]["outline"]["mode"] == "dark"
    assert result["unmutated"] and result["detached"]


def test_resolver_rejects_unknown_family_and_prompt_payload_has_one_canonical_profile():
    profile = _valid_profile()
    result = _run_node(f"""
const input={json.dumps(profile)};
let rejected=false; try{{resolveStyleProfileForFamily(input,'effect')}}catch{{rejected=true}}
const payload={{style_profile:resolveStyleProfileForFamily(input,'ui')}};
console.log(JSON.stringify({{rejected, keys:Object.keys(payload), profile:payload.style_profile}}));
""")
    assert result["rejected"] is True
    assert result["keys"] == ["style_profile"]
    assert result["profile"]["schema_version"] == "asset-studio.style-profile/v1"
    assert not ({"style_preset", "style_notes", "preset", "notes"} & set(result["keys"]))


@pytest.mark.parametrize("family", FAMILIES)
def test_server_accepts_canonical_profile_and_resolves_only_selected_family(family):
    profile = _valid_profile()
    profile["family_overrides"] = {
        "sprite": {"outline": {"mode": "none", "width": 0, "color": "#000000"}},
        "tile": {"shading": {"mode": "flat", "steps": 1, "light_direction": "ambient"}},
        "ui": {"material_treatment": {"mode": "glossy", "detail": "high"}},
        "object": {"silhouette": {"mode": "geometric", "complexity": "low"}},
    }
    before = json.loads(json.dumps(profile))
    resolved = server.normalize_style_profile(profile, family)
    changed_field = {
        "sprite": "outline", "tile": "shading", "ui": "material_treatment", "object": "silhouette",
    }[family]
    assert resolved[changed_field] == profile["family_overrides"][family][changed_field]
    assert resolved["family_overrides"] == {item: {} for item in FAMILIES}
    assert profile == before


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(version=2147483648),
    lambda p: p.update(created_at="2026-02-29T00:00:00.000Z"),
    lambda p: p.update(updated_at="2026-07-10T23:59:59.999Z"),
    lambda p: p["outline"].update(color="transparent"),
    lambda p: p["shading"].update(light_direction="center"),
    lambda p: p["material_treatment"].update(detail="ultra"),
    lambda p: p["silhouette"].update(complexity="extreme"),
    lambda p: p["anti_aliasing"].update(mode="auto"),
    lambda p: p["reference_assets"][0].update(asset_id="x" * 201),
    lambda p: p["family_overrides"]["sprite"].update(
        outline={"mode": "dark", "width": 1, "color": "not-a-color"}
    ),
    lambda p: p["family_overrides"]["tile"].update(
        shading={"mode": "cel", "steps": 3, "light_direction": "center"}
    ),
])
def test_server_rejects_malformed_canonical_profiles(mutation):
    profile = _valid_profile()
    mutation(profile)
    with pytest.raises(ValueError, match="Invalid style_profile"):
        server.normalize_style_profile(profile, "sprite")


def test_server_style_profile_structure_budgets_and_unknown_family_fail_closed():
    profile = _valid_profile()
    profile["palette"]["constructor"] = {}
    with pytest.raises(ValueError, match="Invalid style_profile"):
        server.normalize_style_profile(profile, "sprite")

    profile = _valid_profile()
    profile["name"] = "😀" * 4097  # 8,194 JS UTF-16 code units.
    with pytest.raises(ValueError, match="Invalid style_profile"):
        server.normalize_style_profile(profile, "sprite")

    with pytest.raises(ValueError, match="Invalid style_profile"):
        server.normalize_style_profile(_valid_profile(), "effect")
