import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text()
JS = (ROOT / "src" / "main.js").read_text()
SERVER = (ROOT / "server.py").read_text()


def _function_body(name: str) -> str:
    match = re.search(rf"\bfunction\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", JS)
    assert match, f"Expected JavaScript function {name}()"
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
                return JS[opening + 1:index]
    raise AssertionError(f"Unclosed JavaScript function {name}()")


def _is_sprite_subtype_gate(node: ast.AST, subtypes: set[str]) -> bool:
    if not isinstance(node, ast.BoolOp) or not isinstance(node.op, ast.And):
        return False
    family_ok = any(
        isinstance(part, ast.Compare)
        and isinstance(part.left, ast.Name)
        and part.left.id == "asset_family"
        and len(part.ops) == 1
        and isinstance(part.ops[0], ast.Eq)
        and len(part.comparators) == 1
        and isinstance(part.comparators[0], ast.Constant)
        and part.comparators[0].value == "sprite"
        for part in node.values
    )
    subtype_ok = any(
        isinstance(part, ast.Compare)
        and isinstance(part.left, ast.Name)
        and part.left.id == "asset_type"
        and len(part.ops) == 1
        and len(part.comparators) == 1
        and (
            isinstance(part.ops[0], ast.Eq)
            and isinstance(part.comparators[0], ast.Constant)
            and {part.comparators[0].value} == subtypes
            or isinstance(part.ops[0], ast.In)
            and isinstance(part.comparators[0], (ast.Set, ast.Tuple, ast.List))
            and {
                item.value
                for item in part.comparators[0].elts
                if isinstance(item, ast.Constant)
            } == subtypes
        )
        for part in node.values
    )
    return family_ok and subtype_ok


def test_generate_api_accepts_chroma_green_background_mode():
    assert 'background_mode: str = "none"' in SERVER
    assert 'background_mode = (background_mode or "none").strip()' in SERVER
    assert 'background_mode == "chroma_green"' in SERVER
    assert 'RGB(0,255,0) / #00FF00' in SERVER
    assert 'data.get("background_mode", "none")' in SERVER
    assert "postprocess_pixel_generation_bytes(" in SERVER
    assert "force_chroma_green_background(processed)" in SERVER
    assert '"background_mode": background_mode' in SERVER
    assert "def remove_chroma_green_bytes" in SERVER
    assert "subtle green spill/halo" in SERVER
    assert "green_ratio > 1.18" in SERVER
    assert "transparent_neighbors >= 5" in SERVER
    assert "chroma-green-key-" in SERVER


def test_object_generation_sends_chroma_green_background_mode():
    fn = JS.split("async function generateReplacementObject()", 1)[1].split("function fitReplacementTransform", 1)[0]
    assert "background_mode: 'chroma_green'" in fn


def test_ai_asset_generation_respects_shared_background_and_gates_sprite_postprocess():
    handler = _function_body("generateAiAsset")
    assert re.search(r"requestedBackground\s*=\s*\$\(['\"]assetBackground['\"]\)", handler)
    assert re.search(
        r"backgroundMode\s*=\s*requestedBackground\s*===\s*['\"]chroma_green['\"]"
        r"\s*\?\s*['\"]chroma_green['\"]\s*:\s*['\"]none['\"]",
        handler,
    )
    assert re.search(r"buildAssetGenerationPayload\s*\([^)]*background_mode\s*:\s*backgroundMode", handler)
    assert not re.search(r"family\s*===\s*['\"]sprite['\"]\s*\?\s*['\"]chroma_green['\"]", handler)

    tree = ast.parse(SERVER)
    do_post = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "do_POST")
    actor_gates = [
        node.value
        for node in ast.walk(do_post)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "is_actor_sprite" for target in node.targets)
    ]
    effect_gates = [
        node.value
        for node in ast.walk(do_post)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "is_effect" for target in node.targets)
    ]
    assert actor_gates and all(
        _is_sprite_subtype_gate(gate, {"character", "monster", "npc"}) for gate in actor_gates
    )
    assert effect_gates and all(_is_sprite_subtype_gate(gate, {"effect"}) for gate in effect_gates)

    postprocess_branches = [
        node for node in ast.walk(do_post)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "is_effect"
        and "postprocess_effect_generation_bytes" in (ast.get_source_segment(SERVER, node) or "")
    ]
    assert postprocess_branches
    for branch in postprocess_branches:
        effect_source = "\n".join(ast.get_source_segment(SERVER, item) or "" for item in branch.body)
        assert "postprocess_effect_generation_bytes" in effect_source
        assert "postprocess_pixel_generation_bytes" not in effect_source
        assert branch.orelse and isinstance(branch.orelse[0], ast.If)
        assert isinstance(branch.orelse[0].test, ast.Name) and branch.orelse[0].test.id == "is_actor_sprite"
        actor_source = "\n".join(ast.get_source_segment(SERVER, item) or "" for item in branch.orelse[0].body)
        assert "postprocess_pixel_generation_bytes" in actor_source
    assert "#00FF00" in INDEX
    assert "RGB(0,255,0)" in INDEX
