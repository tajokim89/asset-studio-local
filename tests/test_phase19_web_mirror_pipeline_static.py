import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "server.py").read_text()
MAIN = (ROOT / "src" / "main.js").read_text()


def _function_body(name: str) -> str:
    match = re.search(rf"\bfunction\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", MAIN)
    assert match, f"Expected JavaScript function {name}()"
    opening = match.end() - 1
    depth = 0
    quote = None
    escaped = False
    for index in range(opening, len(MAIN)):
        char = MAIN[index]
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
                return MAIN[opening + 1:index]
    raise AssertionError(f"Unclosed JavaScript function {name}()")


def test_phase19_reference_8dir_route_uses_mirror_pipeline():
    required = [
        'direction_mode = str(data.get("direction_mode", "single"))',
        'generate_reference_8dir_mirror_sheet',
        'build_8dir_mirror_sheet_from_source_pngs',
        '"method": f"reference-image-8dir-mirror+{qa.get(\'method\', \'postprocess\')}"',
    ]
    for token in required:
        assert token in SERVER
    assert re.search(
        r'if\s+is_actor_sprite\s+and\s+direction_mode\s*==\s*["\']8dir["\']'
        r'\s+and\s+animation_mode\s+in\s+\{["\']idle["\'],\s*["\']static["\']\}\s*:',
        SERVER,
    )


def test_phase19_frontend_keeps_8dir_request_on_reference_generate():
    generate = _function_body("generateAiAsset")
    required = [
        "const sprite = payload.sprite;",
        "direction_mode: sprite.direction_mode",
        "reference_direction: sprite.reference_direction",
        "target_direction: sprite.target_direction",
        "'/api/generate-reference'",
    ]
    for token in required:
        assert token in generate
    actor_branch = generate.split("if (family === 'sprite' && ['character', 'monster', 'npc'].includes(subtype))", 1)[1].split("else if", 1)[0]
    assert "Object.assign(payload" in actor_branch
