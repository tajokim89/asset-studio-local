from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
MAIN_JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
CSS = (ROOT / "styles" / "app.css").read_text(encoding="utf-8")


def _opening_tag_with_id(element_id: str) -> str:
    match = re.search(
        rf"<[^>]+\bid\s*=\s*(['\"]){re.escape(element_id)}\1[^>]*>",
        INDEX,
        re.IGNORECASE,
    )
    assert match is not None, f"Expected an element with id={element_id!r}"
    return match.group(0)


def _class_tokens(tag: str) -> set[str]:
    match = re.search(r"\bclass\s*=\s*(['\"])(.*?)\1", tag, re.IGNORECASE)
    return set(match.group(2).split()) if match else set()


def _attribute_value(tag: str, attribute: str) -> str | None:
    match = re.search(
        rf"\b{re.escape(attribute)}\s*=\s*(['\"])(.*?)\1",
        tag,
        re.IGNORECASE | re.DOTALL,
    )
    return match.group(2) if match else None


def _button_tags_with_attribute(attribute: str) -> list[str]:
    return [
        match.group(0)
        for match in re.finditer(r"<button\b[^>]*>", INDEX, re.IGNORECASE)
        if _attribute_value(match.group(0), attribute) is not None
    ]


def _css_rule_bodies_for_class(class_name: str, css: str = CSS) -> list[str]:
    """Find declaration blocks for selectors containing an exact class token."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    class_selector = re.compile(rf"\.{re.escape(class_name)}(?![-\w])")
    return [
        match.group(2)
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css)
        if class_selector.search(match.group(1))
    ]


def _max_width_media_bodies() -> list[str]:
    """Return balanced bodies of max-width media queries, including nested rules."""
    bodies = []
    media_pattern = re.compile(
        r"@media\s*\([^)]*max-width\s*:\s*[^)]+\)\s*\{",
        re.IGNORECASE,
    )
    for match in media_pattern.finditer(CSS):
        opening_brace = match.end() - 1
        depth = 0
        for position in range(opening_brace, len(CSS)):
            if CSS[position] == "{":
                depth += 1
            elif CSS[position] == "}":
                depth -= 1
                if depth == 0:
                    bodies.append(CSS[opening_brace + 1 : position])
                    break
    return bodies


def _function_body(name: str) -> str:
    """Return a named, brace-delimited JS function body for static contracts."""
    match = re.search(rf"\bfunction\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", MAIN_JS)
    assert match is not None, f"Expected function {name} to exist"

    opening_brace = match.end() - 1
    depth = 0
    for position in range(opening_brace, len(MAIN_JS)):
        if MAIN_JS[position] == "{":
            depth += 1
        elif MAIN_JS[position] == "}":
            depth -= 1
            if depth == 0:
                return MAIN_JS[opening_brace + 1 : position]
    raise AssertionError(f"Could not find the closing brace for {name}")


def test_workspace_mode_switch_exposes_ai_and_edit_modes():
    assert 'id="workspaceModeSwitch"' in INDEX
    assert 'data-workspace-mode="ai"' in INDEX
    assert 'data-workspace-mode="edit"' in INDEX


def test_ai_workspace_mode_is_pressed_by_default():
    ai_button = re.search(
        r'<button(?=[^>]*data-workspace-mode="ai")(?=[^>]*aria-pressed="true")[^>]*>',
        INDEX,
    )
    assert ai_button is not None


def test_common_tool_group_exposes_select_pan_and_region_tools():
    assert 'id="commonToolGroup"' in INDEX
    assert 'data-tool="select"' in INDEX
    assert 'data-tool="pan"' in INDEX
    assert 'data-tool="region"' in INDEX


def test_edit_tool_group_has_a_stable_shell_hook():
    assert 'id="editToolGroup"' in INDEX


def test_javascript_workspace_mode_defaults_to_ai():
    assert re.search(
        r"\b(?:let|const|var)\s+workspaceMode\s*=\s*(['\"])ai\1",
        MAIN_JS,
    )


def test_javascript_defines_mode_setter_and_wires_the_switch():
    _function_body("setWorkspaceMode")
    assert re.search(
        r"workspaceModeSwitch[\s\S]{0,500}"
        r"(?:addEventListener\s*\(\s*(['\"])click\1|\.onclick\s*=)",
        MAIN_JS,
    ), "workspaceModeSwitch must handle clicks"
    assert len(re.findall(r"\bsetWorkspaceMode\s*\(", MAIN_JS)) >= 2, (
        "setWorkspaceMode must be invoked by the mode-switch wiring"
    )


def test_mode_setter_toggles_ai_and_edit_tool_groups():
    body = _function_body("setWorkspaceMode")
    for group_id in ("aiToolGroup", "editToolGroup"):
        assert re.search(
            rf"(?:\$\s*\(\s*(['\"]){group_id}\1\s*\)|"
            rf"getElementById\s*\(\s*(['\"]){group_id}\2\s*\))"
            rf"[\s\S]{{0,160}}classList\.toggle\s*\(\s*(['\"])hidden\3",
            body,
        ), f"setWorkspaceMode must toggle {group_id} visibility"


def test_mode_setter_updates_pressed_state_and_activates_ai_tool():
    body = _function_body("setWorkspaceMode")
    assert re.search(
        r"(?:setAttribute\s*\(\s*(['\"])aria-pressed\1|"
        r"\.ariaPressed\s*=)",
        body,
    )
    activates_ai = re.search(
        r"activateTool\s*\(\s*(['\"])ai\1\s*\)",
        body,
    ) or re.search(
        r"data-tool[^\n]{0,80}ai[\s\S]{0,160}\.click\s*\(",
        body,
    )
    assert activates_ai, "AI mode must activate the AI generation tool/panel"


def test_mode_setter_does_not_reset_canvas_or_layer_state():
    body = _function_body("setWorkspaceMode")
    destructive_calls = (
        r"\bcanvas\s*\.\s*(?:clear|loadFromJSON)\s*\(",
        r"\b(?:clear|reset|load)(?:Canvas|Project|Layers?)\s*\(",
    )
    for call_pattern in destructive_calls:
        assert not re.search(call_pattern, body, re.IGNORECASE), (
            "Changing workspace mode must preserve the current canvas and layers"
        )


def test_activate_tool_switches_to_edit_mode_for_every_edit_only_tool():
    body = _function_body("activateTool")
    edit_tools = ("crop", "brush", "pencil", "eraser", "mask", "text", "shape", "upload")
    for tool in edit_tools:
        assert re.search(rf"(['\"]){tool}\1", body), (
            f"activateTool must classify {tool} as edit-only"
        )
    assert re.search(
        r"(?:includes|\.has)\s*\(\s*tool\s*\)[\s\S]{0,160}"
        r"setWorkspaceMode\s*\(\s*(['\"])edit\1\s*,\s*false\s*\)",
        body,
    ), (
        "activateTool must switch modes before activating an edit-only tool "
        "without re-entering tool activation"
    )


def test_activate_tool_does_not_force_mode_for_common_or_ai_tools():
    body = _function_body("activateTool")
    mode_guard = re.search(
        r"(?:\[([^\]]+)\]|new\s+Set\s*\(\s*\[([^\]]+)\]\))"
        r"[\s\S]{0,120}(?:includes|\.has)\s*\(\s*tool\s*\)",
        body,
    )
    assert mode_guard is not None, "Expected an explicit edit-only tool collection"
    edit_only_source = next(group for group in mode_guard.groups() if group is not None)
    for tool in ("select", "pan", "region", "ai"):
        assert not re.search(rf"(['\"]){tool}\1", edit_only_source), (
            f"{tool} must not force the workspace into edit mode"
        )


def test_workspace_mode_switch_has_visual_component_class():
    assert "mode-switch" in _class_tokens(_opening_tag_with_id("workspaceModeSwitch"))


def test_tool_group_shells_share_a_layout_class():
    for group_id in ("commonToolGroup", "aiToolGroup", "editToolGroup"):
        assert "tool-group" in _class_tokens(_opening_tag_with_id(group_id)), (
            f"{group_id} must carry the shared tool-group class"
        )


def test_ai_generate_tool_is_the_primary_rail_action():
    ai_button = re.search(
        r"<button\b(?=[^>]*\bdata-tool\s*=\s*(['\"])ai\1)[^>]*>",
        INDEX,
        re.IGNORECASE,
    )
    assert ai_button is not None, "Expected the AI generation tool button"
    assert "ai-primary-cta" in _class_tokens(ai_button.group(0))


def test_mode_switch_has_component_and_visible_pressed_styles():
    assert _css_rule_bodies_for_class("mode-switch"), (
        "Expected a .mode-switch CSS component"
    )
    pressed_rule = re.compile(
        r"([^{}]*\.mode-switch\s+button\s*\[\s*aria-pressed\s*=\s*"
        r"(?:(['\"])true\2|true)\s*\][^{}]*)\{([^{}]*)\}",
        re.IGNORECASE,
    )
    matches = list(pressed_rule.finditer(CSS))
    assert matches, 'Expected a .mode-switch button[aria-pressed="true"] rule'
    visible_properties = r"(?:background|border(?:-color)?|color|box-shadow|font-weight)\s*:"
    assert any(re.search(visible_properties, match.group(3), re.IGNORECASE) for match in matches), (
        "The pressed mode must have a visible style, not only a selector hook"
    )


def test_tool_groups_have_shared_vertical_layout_and_gap():
    bodies = _css_rule_bodies_for_class("tool-group")
    assert bodies, "Expected a shared .tool-group CSS rule"
    vertical_body = next(
        (
            body
            for body in bodies
            if re.search(r"display\s*:\s*flex\s*;", body, re.IGNORECASE)
            and re.search(r"flex-direction\s*:\s*column\s*;", body, re.IGNORECASE)
        ),
        None,
    )
    assert vertical_body is not None, ".tool-group must stack its tools vertically"
    gap = re.search(r"(?:^|;)\s*(?:row-)?gap\s*:\s*([^;{}]+)", vertical_body, re.IGNORECASE)
    assert gap is not None and gap.group(1).strip() not in {"0", "0px", "0rem", "0em"}, (
        ".tool-group must provide one shared, non-zero gap token"
    )


def test_ai_primary_cta_has_dedicated_visual_style():
    assert _css_rule_bodies_for_class("ai-primary-cta"), (
        "Expected dedicated .ai-primary-cta styles for visual hierarchy"
    )


def test_narrow_viewport_reflows_mode_switch_or_topbar():
    responsive_layout = re.compile(
        r"(?:flex(?:-wrap|-direction)?|grid-template-columns|(?:min-|max-)?width|"
        r"height|white-space|order|position)\s*:",
        re.IGNORECASE,
    )
    for media_body in _max_width_media_bodies():
        relevant_bodies = _css_rule_bodies_for_class("mode-switch", media_body)
        relevant_bodies += _css_rule_bodies_for_class("topbar", media_body)
        if any(responsive_layout.search(body) for body in relevant_bodies):
            return
    raise AssertionError(
        "Expected a max-width media rule that reflows .mode-switch or .topbar; "
        "horizontal scrollbar styling is not a responsive layout contract"
    )


# Task 1.5: right-panel Properties / Layers / Export tab shell.


def test_right_panel_tablist_exposes_exactly_the_three_required_tabs():
    tabs = _opening_tag_with_id("rightPanelTabs")
    assert "right-panel-tabs" in _class_tokens(tabs)

    props_start_match = re.search(
        r"<aside\b[^>]*\bclass\s*=\s*(['\"])[^'\"]*\bprops\b[^'\"]*\1[^>]*>",
        INDEX,
        re.IGNORECASE,
    )
    assert props_start_match is not None, "Expected the existing right-side props panel"
    props_end = INDEX.find("</aside>", props_start_match.end())
    tabs_position = INDEX.find(tabs, props_start_match.end(), props_end)
    assert tabs_position >= 0, "rightPanelTabs must live inside the right-side props panel"

    tab_buttons = _button_tags_with_attribute("data-right-panel-tab")
    values = [_attribute_value(button, "data-right-panel-tab") for button in tab_buttons]
    assert values == ["properties", "layers", "export"], (
        "The right panel must expose Properties, Layers, and Export buttons in that order"
    )
    panel_positions = []
    for panel_id in ("propertiesPanel", "layersPanel", "exportPanel"):
        panel_match = re.search(
            rf"<[^>]+\bid\s*=\s*(['\"]){panel_id}\1[^>]*>",
            INDEX,
            re.IGNORECASE,
        )
        panel_positions.append(panel_match.start() if panel_match else -1)
    assert all(tabs_position < position < props_end for position in panel_positions), (
        "The compact tab strip must precede all three views at the top of the props panel"
    )


def test_right_panel_tabs_use_korean_product_labels():
    expected_labels = {
        "properties": "속성",
        "layers": "레이어",
        "export": "내보내기",
    }
    for tab, label in expected_labels.items():
        assert re.search(
            rf'<button\b[^>]*data-right-panel-tab="{tab}"[^>]*>\s*{label}\s*</button>',
            INDEX,
            re.IGNORECASE,
        ), f"{tab} tab must use the Korean product label {label}"


def test_properties_right_panel_tab_is_selected_initially():
    buttons = _button_tags_with_attribute("data-right-panel-tab")
    selected = [
        _attribute_value(button, "data-right-panel-tab")
        for button in buttons
        if (_attribute_value(button, "aria-selected") or "").lower() == "true"
        or (_attribute_value(button, "aria-pressed") or "").lower() == "true"
    ]
    assert selected == ["properties"], (
        "Properties must be the one initially selected right-panel tab"
    )


def test_right_panel_tabs_have_complete_tab_semantics_and_roving_tabindex():
    expected = {
        "properties": ("rightPanelPropertiesTab", "propertiesPanel", "0"),
        "layers": ("rightPanelLayersTab", "layersPanel", "-1"),
        "export": ("rightPanelExportTab", "exportPanel", "-1"),
    }
    for tab_name, (tab_id, panel_id, tabindex) in expected.items():
        button = next(
            tag
            for tag in _button_tags_with_attribute("data-right-panel-tab")
            if _attribute_value(tag, "data-right-panel-tab") == tab_name
        )
        assert _attribute_value(button, "role") == "tab"
        assert _attribute_value(button, "id") == tab_id
        assert _attribute_value(button, "aria-controls") == panel_id
        assert _attribute_value(button, "tabindex") == tabindex


def test_right_panel_views_are_labelled_tabpanels():
    expected_labels = {
        "propertiesPanel": "rightPanelPropertiesTab",
        "layersPanel": "rightPanelLayersTab",
        "exportPanel": "rightPanelExportTab",
    }
    for panel_id, tab_id in expected_labels.items():
        panel = _opening_tag_with_id(panel_id)
        assert _attribute_value(panel, "role") == "tabpanel"
        assert _attribute_value(panel, "aria-labelledby") == tab_id


def test_right_panel_has_three_stable_view_hooks_and_history_disclosure():
    for panel_id in ("propertiesPanel", "layersPanel", "exportPanel"):
        panel = _opening_tag_with_id(panel_id)
        assert "right-panel-view" in _class_tokens(panel), (
            f"{panel_id} must carry the shared right-panel-view class"
        )

    history = _opening_tag_with_id("historyDisclosure")
    assert re.match(r"<details\b", history, re.IGNORECASE), (
        "historyDisclosure must use the native details/disclosure element"
    )


def test_relocated_right_panel_controls_keep_unique_critical_ids():
    for element_id in ("selectedName", "layers", "exportPng2", "historyList"):
        occurrences = re.findall(
            rf"\bid\s*=\s*(['\"]){re.escape(element_id)}\1",
            INDEX,
            re.IGNORECASE,
        )
        assert len(occurrences) == 1, (
            f"Expected critical id={element_id!r} exactly once after panel relocation"
        )


def test_javascript_defines_right_panel_setter_and_wires_tab_clicks():
    _function_body("setRightPanelTab")
    assert re.search(
        r"rightPanelTabs[\s\S]{0,700}"
        r"(?:addEventListener\s*\(\s*(['\"])click\1|\.onclick\s*=)"
        r"[\s\S]{0,700}\bsetRightPanelTab\s*\(",
        MAIN_JS,
        re.IGNORECASE,
    ), "Click handling on rightPanelTabs must invoke setRightPanelTab"


def test_right_panel_setter_toggles_all_three_panel_views():
    body = _function_body("setRightPanelTab")
    for panel_id in ("propertiesPanel", "layersPanel", "exportPanel"):
        assert re.search(rf"(['\"]){panel_id}\1", body), (
            f"setRightPanelTab must address {panel_id}"
        )
    assert re.search(
        r"(?:classList\s*\.\s*(?:toggle|add|remove)\s*\(\s*(['\"])(?:hidden|active)\1|"
        r"\.hidden\s*=)",
        body,
        re.IGNORECASE,
    ), "setRightPanelTab must toggle hidden/active state on the panel views"


def test_right_panel_setter_updates_tab_accessibility_state():
    body = _function_body("setRightPanelTab")
    assert re.search(
        r"(?:setAttribute\s*\(\s*(['\"])aria-(?:selected|pressed)\1|"
        r"\.aria(?:Selected|Pressed)\s*=)",
        body,
        re.IGNORECASE,
    ), "setRightPanelTab must update aria-selected or aria-pressed"
    assert re.search(
        r"(?:setAttribute\s*\(\s*(['\"])tabindex\1|\.tabIndex\s*=)",
        body,
        re.IGNORECASE,
    ), "setRightPanelTab must maintain a roving tabindex"


def test_right_panel_tablist_supports_cycling_keyboard_navigation():
    keydown_wiring = re.search(
        r"rightPanelTabs[\s\S]{0,1800}"
        r"addEventListener\s*\(\s*(['\"])keydown\1[\s\S]{0,1800}",
        MAIN_JS,
        re.IGNORECASE,
    )
    assert keydown_wiring is not None, "rightPanelTabs must handle keydown events"
    handler = keydown_wiring.group(0)
    for key in ("ArrowLeft", "ArrowRight", "Home", "End"):
        assert re.search(rf"(['\"]){key}\1", handler), f"Missing {key} tab navigation"
    assert re.search(r"\.focus\s*\(", handler), "Keyboard navigation must move focus"
    assert re.search(r"\bsetRightPanelTab\s*\(", handler), (
        "Keyboard navigation must activate the newly focused tab"
    )


def test_right_panel_setter_only_switches_ui_and_preserves_project_state():
    body = _function_body("setRightPanelTab")
    destructive_patterns = (
        r"\bnew\s+(?:fabric\s*\.\s*)?Canvas\s*\(",
        r"\bcanvas\s*\.\s*(?:add|clear|dispose|insertAt|loadFromJSON|remove)\s*\(",
        r"\b(?:layers|history|objects|projectData|projectState)\s*\.\s*"
        r"(?:pop|push|reverse|shift|sort|splice|unshift)\s*\(",
        r"\b(?:projectData|projectState)\s*=",
    )
    for pattern in destructive_patterns:
        assert not re.search(pattern, body, re.IGNORECASE), (
            "Changing right-panel tabs must not recreate/remove canvas objects or mutate project data"
        )


def test_right_panel_tabs_and_views_have_accessible_visual_styles():
    tab_strip_bodies = _css_rule_bodies_for_class("right-panel-tabs")
    assert tab_strip_bodies, "Expected a .right-panel-tabs CSS component"
    assert _css_rule_bodies_for_class("right-panel-view"), (
        "Expected shared .right-panel-view styles"
    )

    selected_rule = re.compile(
        r"([^{}]*\.right-panel-tabs[^{}]*(?:"
        r"\[\s*aria-(?:selected|pressed)\s*=\s*(?:(['\"])true\2|true)\s*\]|"
        r"\.active\b)[^{}]*)\{([^{}]*)\}",
        re.IGNORECASE,
    )
    selected_matches = list(selected_rule.finditer(CSS))
    assert selected_matches, "Expected a selected-state selector for a right-panel tab"
    visible_properties = r"(?:background|border(?:-color)?|color|box-shadow|font-weight)\s*:"
    assert any(
        re.search(visible_properties, match.group(3), re.IGNORECASE)
        for match in selected_matches
    ), "The selected right-panel tab must have a visible style"

    strip_is_accessible = any(
        re.search(r"position\s*:\s*(?:sticky|fixed)\s*;", body, re.IGNORECASE)
        or (
            re.search(r"display\s*:\s*(?:flex|grid)\s*;", body, re.IGNORECASE)
            and re.search(r"(?:gap|padding(?:-block|-inline)?)\s*:", body, re.IGNORECASE)
        )
        for body in tab_strip_bodies
    )
    assert strip_is_accessible, (
        "The right-panel tab strip must stay sticky or use a compact top-strip layout"
    )


def test_gallery_rule_has_a_valid_grid_display_declaration():
    gallery_bodies = _css_rule_bodies_for_class("gallery")
    assert any(
        re.search(r"(?:^|;)\s*display\s*:\s*grid\s*;", body, re.IGNORECASE)
        for body in gallery_bodies
    ), ".gallery must contain a valid display: grid declaration"
    assert "501|" not in CSS
