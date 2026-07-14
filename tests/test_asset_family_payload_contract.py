"""Phase 2 normalized asset-generation payload contracts.

The suite checks family isolation statically at the builder boundary and checks that
server request parsing accepts both the new nested contract and the legacy flat
sprite request.  It deliberately makes no paid generation calls.
"""

import ast
import re
from pathlib import Path

import pytest

import server


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
SERVER = (ROOT / "server.py").read_text(encoding="utf-8")
ACTOR_PROFILE = (ROOT / "profiles" / "generic-pixel-actor-v1.json").read_text(encoding="utf-8")
FAMILIES = ("sprite", "tile", "ui", "object")


def _representative_object_contract():
    """Complete E2 witness with nested semantics and legitimate zeroes."""
    return {
        "usage": "world", "identity": {"subtype": "item", "form": "brass lever", "material": "brass", "function": "opens gate"}, "view": "three-quarter",
        "scale": {"basis": "tile-relative", "tile_relative": {"width": 2.0, "height": 1.5}, "character_relative": 0.75, "footprint": {"width": 2, "depth": 1}},
        "source": {"canvas": {"width": 160, "height": 128}, "padding": {"top": 0, "right": 7, "bottom": 11, "left": 0}},
        "placement": {"pivot": {"x": 0.0, "y": 1.0}, "ground_point": {"x": 0.0, "y": 1.0}, "y_sort_point": {"x": 0.0, "y": 0.875}, "snap_points": [{"id": "origin", "x": 0.0, "y": 0.0}]},
        "shadow": {"mode": "contact", "baked": False}, "states": [{"id": "closed"}, {"id": "open"}], "variants": [{"id": "brass", "weight": 3.0}],
        "collision": {"shape": "box", "offset": {"x": 0.0, "y": 0.0}, "size": {"width": 2.0, "depth": 1.0}}, "interaction": {"point": {"x": 0.0, "y": 0.5}, "radius": 1.25},
        "custom_properties": {"quest_gate": "cistern", "requires_power": True},
    }


def _function_body(name: str, source: str) -> str:
    """Extract a normal named function while ignoring braces inside strings."""
    match = re.search(rf"\bfunction\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", source)
    assert match, f"Expected function {name}()"
    opening = match.end() - 1
    depth = 0
    quote = None
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
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
                return source[opening + 1:index]
    raise AssertionError(f"Unclosed function {name}()")


def _has_key(source: str, key: str) -> bool:
    """Recognize both explicit properties and JS object-literal shorthand.

    The trailing comma/brace requirement keeps this from treating an arbitrary local
    variable as a serialized property (the previous helper falsely rejected
    ``{ ..., style, output }``).
    """
    explicit = rf"(?:\b{re.escape(key)}\b\s*:|['\"]{re.escape(key)}['\"]\s*:)"
    shorthand = rf"(?:[{{,]\s*{re.escape(key)}\s*(?=[,}}]))"
    return bool(re.search(rf"(?:{explicit}|{shorthand})", source))


def _assert_keys(source: str, keys: tuple[str, ...], owner: str):
    missing = [key for key in keys if not _has_key(source, key)]
    assert not missing, f"{owner} is missing payload keys: {', '.join(missing)}"


def _server_normalizer() -> tuple[str, str]:
    """Return an auditable Python payload-normalizer name and source body."""
    tree = ast.parse(SERVER)
    accepted_names = {
        "normalize_asset_generation_payload",
        "normalize_generation_payload",
        "normalize_asset_payload",
    }
    node = next(
        (
            item for item in ast.walk(tree)
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name in accepted_names
        ),
        None,
    )
    assert node is not None, (
        "Expected a named server payload normalizer for nested and legacy contracts"
    )
    return node.name, ast.get_source_segment(SERVER, node) or ""


@pytest.mark.parametrize("name", [
    "buildSpriteContract", "buildTileContract", "buildUiContract",
    "buildObjectContract", "buildAssetGenerationPayload",
])
def test_required_payload_builder_functions_exist(name):
    _function_body(name, JS)


def test_top_level_builder_sets_base_family_and_type_and_only_selected_nested_contract():
    body = _function_body("buildAssetGenerationPayload", JS)
    _assert_keys(body, ("asset_family", "asset_type"), "buildAssetGenerationPayload()")
    assert "currentAssetFamily" in body
    assert "currentAssetSubtype" in body

    # Each nested family must be guarded by equality with the selected family.  An
    # unconditional payload containing all four objects would leak irrelevant keys.
    for family, builder in (
        ("sprite", "buildSpriteContract"), ("tile", "buildTileContract"),
        ("ui", "buildUiContract"), ("object", "buildObjectContract"),
    ):
        guarded = re.search(
            rf"(?:if\s*\([^)]*family\s*===\s*['\"]{family}['\"][^)]*\)|"
            rf"['\"]{family}['\"]\s*:\s*\(\s*\)\s*=>)"
            rf"[\s\S]{{0,240}}(?:\.\s*{family}\s*=|['\"]?{family}['\"]?\s*:)"
            rf"[\s\S]{{0,120}}{builder}\s*\(",
            body,
        )
        assert guarded, f"The {family} nested object must be selected conditionally"


def test_actor_sprite_contract_contains_action_direction_and_frame_count():
    body = _function_body("buildSpriteContract", JS)
    _assert_keys(body, ("animation_mode", "direction_mode", "frame_count"), "actor sprite contract")
    for actor_type in ("character", "monster", "npc"):
        assert re.search(rf"['\"]{actor_type}['\"]", body), (
            f"buildSpriteContract() must recognize actor subtype {actor_type}"
        )


def test_effect_sprite_contract_has_effect_settings_and_an_explicit_actor_exclusion_branch():
    body = _function_body("buildSpriteContract", JS)
    assert re.search(r"['\"]effect['\"]", body)
    _assert_keys(body, ("effect_category", "loop", "frame_count", "pivot"), "effect sprite contract")
    # The implementation must make isolation explicit rather than serializing the
    # entire actor form and hoping the server ignores body/equipment/direction keys.
    effect_guard = re.search(
        r"if\s*\([^)]*(?:subtype|type)[^)]*===\s*['\"]effect['\"][^)]*\)\s*\{([\s\S]*?)\n\s*\}",
        body,
    )
    assert effect_guard, "Expected an explicit effect-only branch in buildSpriteContract()"
    effect_source = effect_guard.group(1)
    for forbidden in ("body", "equipment", "target_direction", "reference_direction"):
        assert not _has_key(effect_source, forbidden), (
            f"Effect payload must exclude actor-only key {forbidden!r}"
        )
    if _has_key(effect_source, "direction_mode"):
        assert re.search(r"\bdirection_mode\s*:\s*['\"]none['\"]", effect_source), (
            "Effect direction_mode, when serialized, must be the fixed value 'none'"
        )


def test_tile_contract_has_tile_fields_and_no_animation_or_direction_keys():
    body = _function_body("buildTileContract", JS)
    _assert_keys(body, (
        "environment", "material", "use", "tile_size", "shape", "margin", "spacing",
        "mode", "rows", "columns", "seamless", "topology", "inner_corners",
        "outer_corners", "transitions", "terrain_types", "variants", "metadata",
    ), "tile contract")
    for forbidden in ("animation_mode", "direction_mode", "target_direction", "reference_direction", "frame_count"):
        assert not _has_key(body, forbidden), f"Tile payload must exclude {forbidden!r}"


def test_ui_contract_has_ui_fields_and_fixed_static_generation_invariants():
    body = _function_body("buildUiContract", JS)
    _assert_keys(body, (
        "purpose", "information_structure", "source_size", "sizing_mode", "slice_margins",
        "content_safe_area", "padding", "border", "corner", "decor_density", "edge_mode",
        "center_mode", "opacity", "states", "target_resolution", "device_safe_area",
        "text_free", "animation_mode", "direction_mode", "frame_count",
    ), "UI contract")
    for key, value_pattern in (
        ("animation_mode", r"['\"]ui_static['\"]"),
        ("direction_mode", r"['\"]none['\"]"),
        ("frame_count", "1"),
    ):
        assert re.search(rf"\b{key}\s*:\s*{value_pattern}(?![\w'])", body), (
            f"UI payload must fix {key} to {value_pattern}"
        )
    for forbidden in (
        "chroma_mode", "sprite_cleanup", "residue_cleanup", "target_direction",
        "reference_direction", "equipment", "gait", "walk_frames",
    ):
        assert not _has_key(body, forbidden), f"UI payload must exclude sprite cleanup/direction key {forbidden!r}"


def test_object_contract_has_complete_nested_semantics_and_no_legacy_or_sprite_keys():
    body = _function_body("buildObjectContract", JS)
    _assert_keys(body, (
        "usage", "identity", "view", "scale", "source", "placement", "shadow", "states",
        "variants", "collision", "interaction", "custom_properties",
    ), "object contract")
    for forbidden in (
        "animation_mode", "direction_mode", "target_direction", "reference_direction",
        "chroma_mode", "sprite_cleanup", "residue_cleanup", "world_scale", "state", "ground_contact",
    ):
        assert not _has_key(body, forbidden), f"Object payload must exclude {forbidden!r}"


def test_generate_call_serializes_the_normalized_builder_result_not_a_second_flat_object():
    body = _function_body("generateAiAsset", JS)
    assert "buildAssetGenerationPayload" in body
    assert re.search(r"submitGenerationJob\s*\(\s*endpoint\s*,\s*payload\s*\)", body), (
        "generateAiAsset() must submit the normalized family payload to the async job API"
    )


def test_server_has_one_family_normalizer_with_nested_family_isolation():
    _name, body = _server_normalizer()
    for key in ("asset_family", "asset_type"):
        assert re.search(rf"['\"]{key}['\"]", body)
    for family in FAMILIES:
        assert re.search(rf"['\"]{family}['\"]", body), f"Server normalizer must recognize {family}"
    assert re.search(r"isinstance\s*\([^,]+,\s*dict\s*\)", body), (
        "Nested family objects must be type-checked before use"
    )


def test_server_normalizer_keeps_non_profile_legacy_flat_sprite_payload_fallbacks():
    _name, body = _server_normalizer()
    # Legacy clients currently send these at the root. New nested values may take
    # precedence, but all flat reads must remain valid during migration.
    for key in (
        "animation_mode", "direction_mode", "target_direction", "reference_direction",
        "chroma_mode",
    ):
        assert re.search(rf"\b\w+\s*\.\s*get\s*\(\s*['\"]{key}['\"]", body), (
            f"Server normalizer lost legacy flat fallback for {key!r}"
        )


def test_generation_endpoints_use_normalized_contract_and_gate_sprite_postprocessing():
    normalizer_name, _body = _server_normalizer()
    assert re.search(rf"\b{re.escape(normalizer_name)}\s*\(\s*data\s*\)", SERVER)
    assert 'path == "/api/generate"' in SERVER and 'path == "/api/generate-reference"' in SERVER

    handler = next(
        node for node in ast.walk(ast.parse(SERVER))
        if isinstance(node, ast.FunctionDef) and node.name == "do_POST"
    )

    def source(node):
        return ast.get_source_segment(SERVER, node) or ""

    endpoint_branches = [
        node for node in ast.walk(handler)
        if isinstance(node, ast.If)
        and source(node.test) in {'path == "/api/generate"', 'path == "/api/generate-reference"'}
    ]
    assert len(endpoint_branches) == 2
    for endpoint in endpoint_branches:
        endpoint_source = source(endpoint)
        normalizer_call = f"data = {normalizer_name}(data)"
        assert normalizer_call in endpoint_source
        recipe_assignment = next(
            (
                node for node in ast.walk(endpoint)
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "generation_recipe_id"
                    for target in node.targets
                )
            ),
            None,
        )
        assert recipe_assignment is not None
        recipe_call = recipe_assignment.value
        assert (
            isinstance(recipe_call, ast.Call)
            and isinstance(recipe_call.func, ast.Name)
            and recipe_call.func.id == "recipe_id_for_asset_selection"
            and [
                arg.id for arg in recipe_call.args if isinstance(arg, ast.Name)
            ] == ["asset_family", "asset_type"]
            and len(recipe_call.args) == 2
            and not recipe_call.keywords
        ), "Generation route must resolve through the canonical recipe registry"
        actor_assignment = next(
            (
                node for node in ast.walk(endpoint)
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "is_actor_sprite" for target in node.targets)
            ),
            None,
        )
        assert actor_assignment is not None
        effect_assignment = next(
            (
                node for node in ast.walk(endpoint)
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "is_effect" for target in node.targets)
            ),
            None,
        )
        assert effect_assignment is not None

        def is_recipe_gate(assignment, recipe_id):
            gate = assignment.value
            return (
                isinstance(gate, ast.Compare)
                and isinstance(gate.left, ast.Name)
                and gate.left.id == "generation_recipe_id"
                and len(gate.ops) == 1
                and isinstance(gate.ops[0], ast.Eq)
                and len(gate.comparators) == 1
                and isinstance(gate.comparators[0], ast.Constant)
                and gate.comparators[0].value == recipe_id
            )

        assert is_recipe_gate(actor_assignment, "actor-animation")
        assert is_recipe_gate(effect_assignment, "vfx-sequence")
        recipe_position = endpoint_source.index(source(recipe_assignment))
        assert endpoint_source.index(normalizer_call) < recipe_position
        assert recipe_position < endpoint_source.index(source(actor_assignment))
        assert recipe_position < endpoint_source.index(source(effect_assignment))
        effect_branch = next(
            (
                node for node in ast.walk(endpoint)
                if isinstance(node, ast.If)
                and source(node.test) == "is_effect"
                and "postprocess_effect_generation_bytes" in "\n".join(map(source, node.body))
            ),
            None,
        )
        assert effect_branch is not None, "Effects must use effect-only postprocessing"
        assert len(effect_branch.orelse) == 1 and isinstance(effect_branch.orelse[0], ast.If)
        actor_branch = effect_branch.orelse[0]
        assert source(actor_branch.test) == "is_actor_sprite"
        assert "postprocess_pixel_generation_bytes" in "\n".join(map(source, actor_branch.body))
        raw_bypass = "\n".join(map(source, actor_branch.orelse))
        assert "out, qa = raw" in raw_bypass and '"sprite_cleanup": False' in raw_bypass


def test_phase25_walk_and_action_constants_stay_present_during_payload_migration():
    # Payload normalization must wrap, not replace, the proven actor contract.
    assert "recipe.beats.join(',') !== 'N,L,N,R'" in JS
    for token in (
        "Reference Identity Lock", "Full-Frame Pose Lock", "Equipment Lock", "Direction Lock",
        "Root Lock", "Motion Read", "Loop Read", "Production Clean",
    ):
        assert token in JS and token in SERVER
    for action in ("idle", "walk", "attack", "jump", "cast", "hurt", "death"):
        assert f'"id": "{action}"' in ACTOR_PROFILE


def test_effect_client_contract_selects_static_or_sequence_mode_and_no_actor_direction():
    body = _function_body("buildSpriteContract", JS)
    effect = body[body.index("subtype === 'effect'"):body.index("const actorTypes")]
    assert re.search(
        r"animation_mode\s*:\s*sequenceMode\s*===\s*['\"]static['\"]\s*"
        r"\?\s*['\"]static['\"]\s*:\s*['\"]effect_sequence['\"]",
        effect,
    ), "Effect animation mode must map static to static and sequence to effect_sequence"
    assert not re.search(r"animation_mode\s*:[^,\n]*(?:actor|ui_static)", effect)
    for forbidden in ("target_direction", "reference_direction"):
        assert not _has_key(effect, forbidden), f"Effect payload must exclude actor direction key {forbidden!r}"
    if _has_key(effect, "direction_mode"):
        assert re.search(r"\bdirection_mode\s*:\s*['\"]none['\"]", effect)


def test_server_normalizer_builds_clean_isolated_non_sprite_payload():
    foreign_ui_keys = {
        "effect_category", "loop", "size_basis",
        "tile_size", "layout", "seamless", "connections",
        "view", "world_scale", "shadow", "usage", "ground_contact",
    }
    ui_poison: dict[str, object] = {
        key: f"poison-{key}" for key in foreign_ui_keys
    }
    ui_poison.update({
        "width": 0, "height": 999999, "decoration_density": 0,
        "background_opacity": 0,
    })
    dirty = {
        "asset_family": "ui", "asset_type": "button", "prompt": "core",
        "ui": ui_poison,
        "sprite": {"animation_mode": "walk", "equipment": "sword"},
        "tile": {"rows": 99}, "object": {"variants": 99},
        "animation_mode": "walk", "direction_mode": "8dir", "walk_frames": 8,
        "chroma_mode": "global", "equipment": "sword", "arbitrary": "leak",
        **ui_poison,
    }
    normalized = server.normalize_asset_generation_payload(dirty)
    assert set(normalized) == {
        "prompt", "asset_family", "asset_type", "style_profile", "output", "family_contract", "ui",
    }
    assert normalized["family_contract"] is normalized["ui"]
    assert normalized["ui"]["source_size"] == {"width": 320, "height": 180}
    assert normalized["ui"]["decor_density"] == "medium"
    assert normalized["ui"]["opacity"] == 1.0
    assert normalized["ui"]["states"] == ["normal"]
    assert normalized["ui"]["animation_mode"] == "ui_static"
    assert normalized["ui"]["direction_mode"] == "none"
    assert normalized["ui"]["frame_count"] == 1
    assert not (foreign_ui_keys & normalized["ui"].keys())
    assert not (foreign_ui_keys & normalized.keys())


def test_server_effect_normalization_has_no_actor_defaults_or_fields():
    normalized = server.normalize_asset_generation_payload({
        "asset_family": "sprite", "asset_type": "effect",
        "sprite": {"effect_category": "Smoke", "loop": "loop", "frame_count": 0, "pivot": "source", "equipment": "forbidden", "direction_mode": "8dir"},
        "animation_mode": "walk", "target_direction": "N", "chroma_mode": "global",
    })
    contract = normalized["sprite"]
    assert contract["animation_mode"] == "effect_sequence"
    assert contract.get("direction_mode", "none") == "none"
    assert contract["effect_category"] == "Smoke"
    assert contract["loop"] == "loop"
    assert contract["frame_count"] >= 1
    assert contract["pivot"] == {"preset": "source", "x": 0.5, "y": 0.5}
    for forbidden in ("target_direction", "reference_direction", "walk_frames", "equipment", "preservation", "chroma_mode"):
        assert forbidden not in contract
        assert forbidden not in normalized


def test_server_object_numeric_values_are_finite_bounded_and_zero_safe():
    contract = _representative_object_contract()
    normalized = server.normalize_asset_generation_payload({"asset_family": "object", "asset_type": "item", "object": contract})["object"]
    assert normalized == contract
    assert normalized["source"]["padding"]["top"] == 0
    assert normalized["placement"]["pivot"]["x"] == 0
    for mutation in ({"source": {"canvas": {"width": 0, "height": 128}, "padding": contract["source"]["padding"]}}, {"placement": {**contract["placement"], "y_sort_point": {"x": 0, "y": float("inf")}}}):
        with pytest.raises(ValueError):
            server.normalize_asset_generation_payload({"asset_family": "object", "asset_type": "item", "object": {**contract, **mutation}})


def test_server_family_prompts_include_complete_ui_and_object_contracts():
    ui = server.normalize_asset_generation_payload({"asset_family": "ui", "asset_type": "button", "ui": {}})
    ui_prompt = server.build_asset_family_prompt(ui)
    for token in ("semantic regions", "sizing=nine-slice", "decor density=medium", "opacity=1.0", "text-free", 'states=["normal"]'):
        assert token in ui_prompt
    obj = server.normalize_asset_generation_payload({"asset_family": "object", "asset_type": "item", "object": _representative_object_contract()})
    obj_prompt = server.build_asset_family_prompt(obj)
    for token in ("OBJECT_CONTRACT_CANONICAL", '"padding"', '"ground_point"', '"quest_gate"'):
        assert token in obj_prompt


def test_effect_endpoints_bypass_actor_reference_and_actor_residue_cleanup():
    handler_node = next(node for node in ast.walk(ast.parse(SERVER)) if isinstance(node, ast.FunctionDef) and node.name == "do_POST")
    effect_branches = [
        node for node in ast.walk(handler_node)
        if isinstance(node, ast.If) and ast.get_source_segment(SERVER, node.test) == "is_effect"
    ]

    def branch_source(statements):
        return "\n".join(ast.get_source_segment(SERVER, statement) or "" for statement in statements)

    collector_branch = next(
        (node for node in effect_branches if "collect_codex_reference_effect_b64" in branch_source(node.body)),
        None,
    )
    assert collector_branch, "Expected if is_effect: to select the effect-only reference collector"
    assert "collect_codex_reference_sprite_b64" not in branch_source(collector_branch.body)
    assert "collect_codex_reference_sprite_b64" in branch_source(collector_branch.orelse), (
        "Actor reference collector must remain confined to the effect branch's else/elif path"
    )

    postprocess_branches = [
        node for node in effect_branches
        if "postprocess_effect_generation_bytes" in branch_source(node.body)
    ]
    assert postprocess_branches, "Expected if is_effect: to select effect-only postprocessing"
    for branch in postprocess_branches:
        assert "postprocess_pixel_generation_bytes" not in branch_source(branch.body)
        assert "postprocess_pixel_generation_bytes" in branch_source(branch.orelse), (
            "Actor residue postprocessing must remain confined to an else/elif actor path"
        )


def test_server_checks_practical_content_length_limit_before_read():
    body = ast.get_source_segment(SERVER, next(node for node in ast.walk(ast.parse(SERVER)) if isinstance(node, ast.FunctionDef) and node.name == "do_POST")) or ""
    length_pos = body.index("Content-Length")
    read_pos = body.index("self.rfile.read")
    assert length_pos < read_pos
    before_read = body[length_pos:read_pos]
    assert "MAX_REQUEST_BYTES" in before_read
    assert "413" in before_read


@pytest.mark.parametrize("family,subtype,background", [
    ("sprite", "character", "transparent"),
    ("sprite", "effect", "transparent"),
    ("ui", "button", "transparent"),
    ("object", "item", "transparent"),
])
def test_server_normalizes_common_style_output_for_every_production_selection(
    family, subtype, background,
):
    contract = _representative_object_contract() if family == "object" else {}
    normalized = server.normalize_asset_generation_payload({
        "asset_family": family,
        "asset_type": subtype,
        family: contract,
        "style": {"preset": "hand_painted", "notes": "indigo and brass", "leak": "no"},
        "output": {"width": 99999, "height": 0, "background": background, "leak": "no"},
    })
    assert normalized["style_profile"]["schema_version"] == "asset-studio.style-profile/v1"
    assert normalized["style_profile"]["name"] == "indigo and brass"
    assert normalized["style_profile"]["pixel_density"]["mode"] == "smooth"
    assert normalized["output"] == {"width": 4096, "height": 1, "background": background}
    assert "style" not in normalized and "leak" not in normalized["style_profile"] and "leak" not in normalized["output"]
