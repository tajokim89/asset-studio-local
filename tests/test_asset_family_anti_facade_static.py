"""Task A2 contracts for the family-neutral generation shell.

The family tabpanels own only family-specific settings.  The request, style, output,
and primary action are a common shell that remains available alongside whichever
family panel is active.
"""

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
FAMILIES = ("sprite", "tile", "ui", "object")
FAMILY_PANEL_IDS = tuple(f"{family}Settings" for family in FAMILIES)
SHARED_CONTROL_IDS = (
    "assetCorePrompt",
    "assetStylePreset",
    "assetStyleNotes",
    "assetOutputWidth",
    "assetOutputHeight",
    "assetBackground",
)
SHARED_SHELL_IDS = (
    "assetCoreSection",
    "assetStyleSection",
    "assetOutputSection",
    "familyGenerateAi",
)
CONTRACT_IDS = (
    "assetAiPanel",
    "assetFamilyTabs",
    *(f"assetFamilyTab-{family}" for family in FAMILIES),
    *FAMILY_PANEL_IDS,
    "assetCorePrompt",
    "assetCorePromptLabel",
    "assetCorePromptHelp",
    *SHARED_SHELL_IDS,
    *SHARED_CONTROL_IDS,
)


class _Dom(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[dict[str, Any]] = []
        self.by_id: dict[str, dict[str, Any]] = {}
        self.nodes_by_id: dict[str, list[dict[str, Any]]] = {}
        self.nodes: list[dict[str, Any]] = []
        self.tabs: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        node = {key: (value or "") for key, value in attrs}
        node["__tag"] = tag
        ancestors = tuple(self.stack)
        record = {
            "tag": tag,
            "attrs": node,
            "ancestors": ancestors,
            "text": [],
            "order": len(self.nodes),
        }
        self.nodes.append(record)
        if node.get("id"):
            self.nodes_by_id.setdefault(node["id"], []).append(record)
            self.by_id.setdefault(node["id"], record)
        if node.get("data-asset-family") is not None:
            self.tabs.append(node)
        if tag not in self.VOID_TAGS:
            self.stack.append(record)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID_TAGS:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        for record in self.stack:
            if record["attrs"].get("id"):
                record["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                return


DOM = _Dom()
DOM.feed(HTML)


def _code_mask(source: str, *, mask_strings: bool = True) -> str:
    """Blank JS comments/strings while preserving offsets and newlines."""
    output = list(source)
    index = 0
    state = "code"
    quote = ""
    while index < len(source):
        char = source[index]
        nxt = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == "/" and nxt == "/":
                output[index] = output[index + 1] = " "
                index += 2
                state = "line_comment"
                continue
            if char == "/" and nxt == "*":
                output[index] = output[index + 1] = " "
                index += 2
                state = "block_comment"
                continue
            if char in "'\"`":
                quote = char
                if mask_strings:
                    output[index] = " "
                state = "string"
        elif state == "line_comment":
            if char == "\n":
                state = "code"
            else:
                output[index] = " "
        elif state == "block_comment":
            if char == "*" and nxt == "/":
                output[index] = output[index + 1] = " "
                index += 2
                state = "code"
                continue
            if char != "\n":
                output[index] = " "
        else:
            if char == "\\":
                if mask_strings:
                    output[index] = " "
                    if index + 1 < len(source) and source[index + 1] != "\n":
                        output[index + 1] = " "
                index += 2
                continue
            if mask_strings and char != "\n":
                output[index] = " "
            if char == quote:
                state = "code"
        index += 1
    return "".join(output)


def _balanced_body(source: str, opening: int, masked: str | None = None) -> str:
    masked = masked if masked is not None else _code_mask(source)
    depth = 0
    for index in range(opening, len(source)):
        char = masked[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise AssertionError(f"Unclosed JavaScript block beginning at offset {opening}")


def _callable_bodies(source: str = JS) -> dict[str, str]:
    """Extract declarations, function expressions, arrows, and object methods."""
    masked = _code_mask(source)
    bodies: dict[str, str] = {}

    patterns = (
        r"\bfunction\s+([A-Za-z_$][\w$]*)\b[^{};]*\{",
        r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*function\b[^{};]*\{",
        r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, masked):
            bodies.setdefault(match.group(1), _balanced_body(source, match.end() - 1, masked))

    object_pattern = re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*\{")
    for object_match in object_pattern.finditer(masked):
        object_name = object_match.group(1)
        opening = object_match.end() - 1
        object_body = _balanced_body(source, opening, masked)
        object_mask = _code_mask(object_body)
        method_patterns = (
            r"\b([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{",
            r"\b([A-Za-z_$][\w$]*)\s*:\s*function(?:\s+[\w$]+)?\s*\([^)]*\)\s*\{",
            r"\b([A-Za-z_$][\w$]*)\s*:\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{",
        )
        for pattern in method_patterns:
            for match in re.finditer(pattern, object_mask):
                absolute_opening = opening + 1 + match.end() - 1
                bodies.setdefault(
                    f"{object_name}.{match.group(1)}",
                    _balanced_body(source, absolute_opening, masked),
                )
    return bodies


def _function_body(name: str, source: str = JS) -> str:
    bodies = _callable_bodies(source)
    assert name in bodies, f"Expected JavaScript callable {name}()"
    return bodies[name]


def _classes(element_id: str) -> set[str]:
    return set(DOM.by_id[element_id]["attrs"].get("class", "").split())


def _ancestor_ids(element_id: str) -> tuple[str, ...]:
    return tuple(
        ancestor["attrs"].get("id", "")
        for ancestor in DOM.by_id[element_id]["ancestors"]
        if ancestor["attrs"].get("id")
    )


def _is_hidden(record: dict[str, Any]) -> bool:
    attrs = record["attrs"]
    style = re.sub(r"\s+", "", attrs.get("style", "").lower())
    return (
        "hidden" in attrs
        or "hidden" in attrs.get("class", "").split()
        or attrs.get("aria-hidden", "").lower() == "true"
        or "display:none" in style
        or "visibility:hidden" in style
    )


def _assert_visible_in_markup(element_id: str) -> None:
    record = DOM.by_id[element_id]
    assert not _is_hidden(record), f"Shared contract node #{element_id} must not be hidden"
    hidden_ancestor = next((node for node in record["ancestors"] if _is_hidden(node)), None)
    assert hidden_ancestor is None, (
        f"Shared contract node #{element_id} is inside hidden ancestor "
        f"#{hidden_ancestor['attrs'].get('id', '<no-id>')}"
    )


def _text(element_id: str) -> str:
    return re.sub(r"\s+", " ", "".join(DOM.by_id[element_id]["text"])).strip()


def _creation_copy() -> dict[str, dict[str, str]]:
    declaration = re.search(
        r"\bASSET_FAMILY_CREATION_COPY\s*=\s*\{([\s\S]*?)\n\};",
        JS,
    )
    assert declaration, "Expected declarative family-specific creation copy"
    result: dict[str, dict[str, str]] = {}
    for family in FAMILIES:
        branch = re.search(rf"\b{family}\s*:\s*\{{([^}}]+)\}}", declaration.group(1))
        assert branch, f"Missing creation copy for {family}"
        result[family] = {}
        for field in ("label", "placeholder", "help"):
            value = re.search(rf"\b{field}\s*:\s*(['\"])(.*?)\1", branch.group(1))
            assert value and value.group(2).strip(), f"Missing {family} {field} copy"
            result[family][field] = value.group(2)
    return result


def _reachable_switch_helpers(source: str = JS) -> dict[str, str]:
    """Trace local callable helpers reachable from the family switch.

    This deliberately follows behavior rather than enforcing a brittle exact call
    list, so harmless extraction/renaming of intermediate helpers remains possible.
    """
    declarations = _callable_bodies(source)
    pending = ["setAssetFamily"]
    bodies: dict[str, str] = {}
    while pending:
        name = pending.pop()
        if name in bodies:
            continue
        assert name in declarations, f"Expected JavaScript callable {name}()"
        body = declarations[name]
        bodies[name] = body
        calls = set(
            re.findall(
                r"(?<![\w$])([A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)*)\s*\(",
                _code_mask(body),
            )
        )
        normalized_calls = {re.sub(r"\s+", "", call) for call in calls}
        pending.extend(sorted((normalized_calls & declarations.keys()) - bodies.keys()))
    return bodies


def _keyboard_handler_body(source: str = JS) -> str:
    uncommented = _code_mask(source, mask_strings=False)
    listener = re.search(
        r"\$\s*\(\s*(['\"])assetFamilyTabs\1\s*\)\s*\?\.\s*"
        r"addEventListener\s*\(\s*(['\"])keydown\2\s*,",
        uncommented,
    )
    assert listener, "#assetFamilyTabs must register a keydown handler"
    callback_source = source[listener.end():]
    callback = re.search(
        r"(?:function\s*\([^)]*\)|(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>)\s*\{",
        _code_mask(callback_source),
    )
    assert callback, "The family-tab keydown listener must have an inspectable callback body"
    opening = listener.end() + callback.end() - 1
    return _balanced_body(source, opening)


def _state_reset_matches(source: str = JS) -> dict[str, re.Match[str] | None]:
    reachable = _reachable_switch_helpers(source)
    combined = "\n".join(f"/* {name} */\n{body}" for name, body in reachable.items())
    code = _code_mask(combined)
    owner = r"(?:[A-Za-z_$][\w$]*\s*\.\s*)*"
    assignment = r"\s*(?:(?<![=!<>])=(?!=)|\+=|-=|\+\+|--)"
    return {
        "canvas": re.search(
            rf"\b{owner}(?:canvas|editorCanvas)\s*\.\s*"
            r"(?:clear|remove|dispose|loadFromJSON|add|insertAt|moveTo|"
            r"sendToBack|bringToFront|setDimensions)\s*\(",
            code,
            re.IGNORECASE,
        ),
        "history": re.search(
            rf"\b{owner}(?:history|historyIndex)(?:{assignment}|\s*\.\s*"
            r"(?:clear|push|pop|shift|unshift|splice)\s*\()",
            code,
        ),
        "layers": re.search(
            rf"\b{owner}(?:layers|layerCollection)(?:{assignment}|\s*\.\s*"
            rf"(?:length{assignment}|clear\s*\(|splice\s*\(|removeAll\s*\())",
            code,
            re.IGNORECASE,
        ),
    }


def test_contract_ids_are_unique_in_the_actual_dom():
    duplicates = {
        element_id: len(DOM.nodes_by_id.get(element_id, ()))
        for element_id in CONTRACT_IDS
        if len(DOM.nodes_by_id.get(element_id, ())) != 1
    }
    assert not duplicates, f"Every A2 contract ID must occur exactly once; bad counts: {duplicates}"


def test_one_common_core_request_is_available_with_all_four_families():
    assert [tab["data-asset-family"] for tab in DOM.tabs] == list(FAMILIES)
    assert DOM.by_id["assetCorePrompt"]["tag"] == "textarea"
    assert "assetAiPanel" in _ancestor_ids("assetCorePrompt")
    assert not any(
        panel_id in _ancestor_ids("assetCorePrompt")
        for panel_id in FAMILY_PANEL_IDS
    ), "The core request belongs to the common shell, not one sibling tabpanel"
    _assert_visible_in_markup("assetCoreSection")


def test_family_copy_is_distinct_and_connected_to_label_placeholder_and_help_dom():
    copy = _creation_copy()
    assert len({tuple(fields.values()) for fields in copy.values()}) == len(FAMILIES)
    for field in ("label", "placeholder", "help"):
        assert len({copy[family][field] for family in FAMILIES}) == len(FAMILIES), (
            f"Each family needs distinguishable {field} copy"
        )

    label_attrs = DOM.by_id["assetCorePromptLabel"]["attrs"]
    assert label_attrs.get("for") == "assetCorePrompt"
    assert _text("assetCorePromptLabel")
    assert DOM.by_id["assetCorePrompt"]["attrs"].get("placeholder")
    assert _text("assetCorePromptHelp")

    restore = _function_body("restoreAssetCreationDraft")
    for element_id, dom_property, copy_field in (
        ("assetCorePromptLabel", "textContent", "label"),
        ("assetCorePrompt", "placeholder", "placeholder"),
        ("assetCorePromptHelp", "textContent", "help"),
    ):
        assert re.search(
            rf"\$\(\s*['\"]{element_id}['\"]\s*\)\s*\.{dom_property}\s*=\s*copy\.{copy_field}\b",
            restore,
        ), f"Family {copy_field} copy must update #{element_id}.{dom_property}"


def test_core_request_draft_is_saved_under_the_old_family_and_restored_for_the_new_family():
    assert re.search(r"\bassetFamilyDrafts\s*=\s*new\s+Map\s*\(", JS)
    save = _function_body("saveAssetCreationDraft")
    restore = _function_body("restoreAssetCreationDraft")
    switch = _function_body("setAssetFamily")

    # The requirement is specifically the core-request draft.  Output/subtype/style
    # may also be persisted, but are intentionally not mandatory here.
    assert re.search(r"assetFamilyDrafts\.set\s*\(\s*family\s*,", save)
    assert re.search(
        r"\bcore\s*:\s*controlValue\s*\(\s*['\"]assetCorePrompt['\"]",
        save,
    )
    assert re.search(r"assetFamilyDrafts\.get\s*\(\s*family\s*\)", restore)
    assert re.search(
        r"\$\(\s*['\"]assetCorePrompt['\"]\s*\)\.value\s*=\s*draft\.core\b",
        restore,
    )

    save_call = re.search(
        r"saveAssetCreationDraft\s*\(\s*currentAssetFamily\s*\(\s*\)\s*\)", switch
    )
    selection = re.search(r"\bselectedAssetFamily\s*=\s*family\b", switch)
    restore_call = re.search(r"restoreAssetCreationDraft\s*\(\s*family\s*\)", switch)
    assert save_call and selection and restore_call
    assert save_call.start() < selection.start() < restore_call.start(), (
        "Switching must save the outgoing family's core before selecting and restoring "
        "the incoming family's core"
    )


def test_shared_style_output_and_background_stay_outside_family_hidden_state():
    for element_id in (*SHARED_SHELL_IDS, *SHARED_CONTROL_IDS):
        assert element_id in DOM.by_id, f"Missing shared contract node #{element_id}"
        ancestors = _ancestor_ids(element_id)
        assert "assetAiPanel" in ancestors, f"#{element_id} must remain in #assetAiPanel"
        assert not any(panel_id in ancestors for panel_id in FAMILY_PANEL_IDS), (
            f"Shared node #{element_id} must not be owned by a family tabpanel"
        )
        _assert_visible_in_markup(element_id)

    for panel_id in FAMILY_PANEL_IDS:
        assert "assetAiPanel" in _ancestor_ids(panel_id)

    updater = _function_body("updateAssetFamilyUi")
    for shared_id in (*SHARED_SHELL_IDS, *SHARED_CONTROL_IDS):
        touching_statements = [part for part in updater.split(";") if shared_id in part]
        assert all(
            "classList" not in statement and ".hidden" not in statement
            for statement in touching_statements
        ), f"Family updater must not hide shared #{shared_id}"
    assert "asset-shared-section" not in updater
    assert re.search(
        r"classList\.toggle\s*\(\s*['\"]hidden['\"]\s*,\s*"
        r"id\s*!==\s*`\$\{family\}Settings`",
        updater,
    ), "Only inactive family settings panels should be hidden by family selection"


@pytest.mark.parametrize("family", FAMILIES)
def test_primary_generate_follows_request_style_active_family_settings_and_output(family):
    ordered_ids = (
        "assetCoreSection",
        "assetStyleSection",
        f"{family}Settings",
        "assetOutputSection",
        "familyGenerateAi",
    )
    positions = [DOM.by_id[element_id]["order"] for element_id in ordered_ids]
    assert positions == sorted(positions), (
        f"The {family} shell must read request/style -> family settings -> output -> Generate"
    )
    assert all("assetAiPanel" in _ancestor_ids(element_id) for element_id in ordered_ids)
    assert "primary" in _classes("familyGenerateAi")


def test_tabs_have_matching_tabpanels_and_roving_tabindex():
    assert DOM.by_id["assetFamilyTabs"]["attrs"].get("role") == "tablist", (
        "The family-tab container must expose role=tablist"
    )
    assert len(DOM.tabs) == 4
    for index, tab in enumerate(DOM.tabs):
        family = tab["data-asset-family"]
        assert "assetFamilyTabs" in _ancestor_ids(tab["id"]), (
            f"Family tab #{tab['id']} must be a descendant of #assetFamilyTabs"
        )
        assert tab.get("role") == "tab"
        assert tab.get("tabindex") == ("0" if index == 0 else "-1")
        panel_id = tab.get("aria-controls")
        assert panel_id in DOM.by_id
        panel = DOM.by_id[panel_id]["attrs"]
        assert panel.get("role") == "tabpanel"
        assert panel.get("aria-labelledby") == tab.get("id")
        assert panel_id == f"{family}Settings"

    updater = _function_body("updateAssetFamilyUi")
    assert "aria-selected" in updater and "tabindex" in updater, (
        "Family UI updates must maintain selected state and the roving tabindex"
    )


def test_tab_keyboard_navigation_computes_selects_and_focuses_the_same_destination():
    keyboard_wiring = _keyboard_handler_body()
    normalized = re.sub(r"\s+", " ", _code_mask(keyboard_wiring, mask_strings=False)).strip()
    for key in ("ArrowLeft", "ArrowRight", "Home", "End"):
        assert re.search(rf"(['\"]){key}\1", normalized), (
            f"Family-tab keyboard handler must recognize {key}"
        )
    assert re.search(r"tabs\s*\.\s*indexOf\s*\(\s*document\s*\.\s*activeElement\s*\)", normalized), (
        "Keyboard navigation must derive its current index from the focused tab"
    )
    assert re.search(r"key\s*===?\s*(['\"])Home\1\s*\?\s*0\b", normalized)
    assert re.search(r"key\s*===?\s*(['\"])End\1\s*\?\s*tabs\s*\.\s*length\s*-\s*1", normalized)
    assert re.search(r"(['\"])ArrowRight\1\s*\?\s*1\s*:\s*-\s*1", normalized), (
        "Left/right navigation must move backward/forward"
    )
    assert re.search(r"%\s*tabs\s*\.\s*length", normalized), (
        "Left/right tab navigation must wrap within the tab count"
    )
    prevent = re.search(r"event\s*\.\s*preventDefault\s*\(\s*\)", normalized)
    select = re.search(
        r"setAssetFamily\s*\(\s*tabs\s*\[\s*next\s*\]\s*\.\s*dataset\s*\.\s*assetFamily\s*\)",
        normalized,
    )
    focus = re.search(r"tabs\s*\[\s*next\s*\]\s*\.\s*focus\s*\(\s*\)", normalized)
    assert prevent, "Handled family-tab keys must call preventDefault()"
    assert select, "Keyboard navigation must select tabs[next]'s asset family"
    assert focus, "Keyboard navigation must move focus to the same tabs[next] destination"
    assert prevent.start() < select.start() < focus.start(), (
        "The handler must prevent default, select the computed family, then focus that tab"
    )


def test_family_change_helpers_do_not_mutate_canvas_layers_or_history_state():
    mutations = _state_reset_matches()
    found = {
        state: match.group(0)
        for state, match in mutations.items()
        if match is not None
    }
    assert not found, (
        "Family switching must preserve the current canvas, layer collection, and undo "
        f"history; reachable reset mutations: {found}"
    )
