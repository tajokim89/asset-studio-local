"""Phase 2 asset-family UI contracts.

These tests intentionally describe the completed Phase 2 DOM/state boundary rather
than the legacy flat pixelAssetType form.  They are static so RED does not require a
browser or an image-provider request.
"""

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")

FAMILY_SUBTYPES = {
    "sprite": ["character", "monster", "npc", "effect"],
    "tile": ["floor", "wall", "corner", "door", "terrain", "decal", "autotile", "tileset"],
    "ui": ["main_panel", "inner_panel", "popup", "card", "button", "slot", "badge", "hud_chip", "gauge", "icon", "cursor"],
    "object": ["item", "equipment", "weapon", "loot", "furniture", "machine", "prop", "interactable", "destructible"],
}

UI_EDGE_NUMBER_IDS = (
    "uiSliceTop", "uiSliceRight", "uiSliceBottom", "uiSliceLeft",
    "uiContentSafeTop", "uiContentSafeRight", "uiContentSafeBottom", "uiContentSafeLeft",
    "uiPaddingTop", "uiPaddingRight", "uiPaddingBottom", "uiPaddingLeft",
    "uiBorderWidth", "uiCornerRadius",
    "uiDeviceSafeTop", "uiDeviceSafeRight", "uiDeviceSafeBottom", "uiDeviceSafeLeft",
)


class _DomInventory(HTMLParser):
    """Small, dependency-free DOM inventory with ancestry and visible text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[dict[str, str]] = []
        self.by_id: dict[str, dict[str, Any]] = {}
        self.family_tabs: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs):
        node = {key: (value or "") for key, value in attrs}
        node["__tag"] = tag
        ancestors = [entry.get("id", "") for entry in self.stack]
        if node.get("id"):
            self.by_id[node["id"]] = {"tag": tag, "attrs": node, "ancestors": ancestors}
        if node.get("data-asset-family") is not None and "assetFamilyTabs" in ancestors:
            record: dict[str, Any] = {"attrs": node, "text": []}
            self.family_tabs.append(record)
            node["__family_record"] = str(len(self.family_tabs) - 1)
        self.stack.append(node)

    def handle_data(self, data: str):
        for node in reversed(self.stack):
            marker = node.get("__family_record")
            if marker is not None:
                self.family_tabs[int(marker)]["text"].append(data)
                break

    def handle_endtag(self, tag: str):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].get("__tag") == tag:
                del self.stack[index:]
                return


DOM = _DomInventory()
DOM.feed(HTML)


def _function_body(name: str, source: str = JS) -> str:
    match = re.search(rf"\bfunction\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", source)
    assert match, f"Expected JavaScript function {name}()"
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
    raise AssertionError(f"Unclosed JavaScript function {name}()")


def _configured_subtypes(family: str) -> list[str]:
    """Read a family array from the declarative subtype map, formatting agnostic."""
    declaration = re.search(
        r"\b(?:const|let|var)\s+(?:ASSET_FAMILY_SUBTYPES|ASSET_SUBTYPES|assetFamilySubtypes)\s*=",
        JS,
    )
    assert declaration, "Expected one declarative asset-family subtype map"
    tail = JS[declaration.end():]
    block = re.search(
        rf"(?:['\"]{family}['\"]|\b{family}\b)\s*:\s*\[([^\]]*)\]",
        tail,
        re.DOTALL,
    )
    assert block, f"Expected a subtype array for {family}"
    return re.findall(r"['\"]([a-z][a-z0-9_]*)['\"]", block.group(1))


def _assert_ids_inside(container_id: str, expected_ids: tuple[str, ...]):
    assert container_id in DOM.by_id, f"Missing family settings container #{container_id}"
    for element_id in expected_ids:
        assert element_id in DOM.by_id, f"Missing #{element_id}"
        assert container_id in DOM.by_id[element_id]["ancestors"], (
            f"#{element_id} must be structurally contained by #{container_id}"
        )


def test_ai_family_menu_has_exact_order_and_visible_korean_labels():
    assert "assetFamilyTabs" in DOM.by_id
    values = [record["attrs"]["data-asset-family"] for record in DOM.family_tabs]
    labels = [re.sub(r"\s+", " ", "".join(record["text"]).strip()) for record in DOM.family_tabs]
    assert values == ["sprite", "tile", "ui", "object"]
    assert labels[0] == "스프라이트"
    assert labels[1] in {"타일·맵", "타일/맵"}
    assert labels[2:] == ["UI", "오브젝트"]


def test_family_shell_hooks_exist_and_legacy_selector_is_preserved_for_migration():
    for element_id in (
        "assetSubtype", "spriteSettings", "tileSettings", "uiSettings", "objectSettings",
    ):
        assert element_id in DOM.by_id, f"Missing Phase 2 hook #{element_id}"
    assert "pixelAssetType" in DOM.by_id, (
        "The legacy #pixelAssetType hook must remain during payload/API migration"
    )


@pytest.mark.parametrize("family", ["sprite", "tile", "ui", "object"])
def test_declarative_subtype_map_is_exact_and_ordered(family):
    assert _configured_subtypes(family) == FAMILY_SUBTYPES[family]


def test_actor_sprite_controls_remain_grouped_under_sprite_settings():
    _assert_ids_inside("spriteSettings", (
        "pixelMotionControls", "pixelDirectionControls", "pixelFrameControls",
        "pixelReferenceControls",
    ))


def test_effect_sprite_has_dedicated_controls_separate_from_actor_controls():
    _assert_ids_inside("spriteSettings", (
        "effectCategory", "effectLoop", "effectFrameCount", "effectPivot",
    ))
    body = _function_body("updateAssetFamilyUi")
    assert re.search(r"['\"]effect['\"]", body)
    for actor_group in ("pixelMotionControls", "pixelDirectionControls", "pixelReferenceControls"):
        assert actor_group in body, f"Effect switching must explicitly hide #{actor_group}"


def test_tile_settings_have_the_complete_product_spec_control_set():
    _assert_ids_inside("tileSettings", (
        "tileEnvironment", "tileMaterial", "tileUse", "tileWidth", "tileHeight",
        "tileShape", "tileMargin", "tileSpacing", "tileMode", "tileRows",
        "tileColumns", "tileSeamless", "tileTopology", "tileInnerCorners",
        "tileOuterCorners", "tileTransitions", "tileTerrainTypes", "tileVariants",
        "tileCollision", "tileOcclusion", "tileNavigation", "tileCustomMetadata",
    ))


def test_ui_settings_have_authoritative_d1_controls_and_static_invariants():
    _assert_ids_inside("uiSettings", (
        "uiPurpose", "uiInformationStructure", "uiSourceWidth", "uiSourceHeight", "uiSizingMode",
        "uiSliceTop", "uiSliceRight", "uiSliceBottom", "uiSliceLeft",
        "uiContentSafeTop", "uiContentSafeRight", "uiContentSafeBottom", "uiContentSafeLeft",
        "uiPaddingTop", "uiPaddingRight", "uiPaddingBottom", "uiPaddingLeft",
        "uiBorderStyle", "uiBorderWidth", "uiCornerStyle", "uiCornerRadius",
        "uiDecorDensity", "uiEdgeMode", "uiCenterMode", "uiOpacity", "uiStates",
        "uiTargetWidth", "uiTargetHeight", "uiDeviceSafeTop", "uiDeviceSafeRight",
        "uiDeviceSafeBottom", "uiDeviceSafeLeft",
    ))
    assert "text_free=true" in HTML and "animation_mode=ui_static" in HTML


def test_ui_edge_number_controls_declare_server_parity_maximum():
    for element_id in UI_EDGE_NUMBER_IDS:
        attrs = DOM.by_id[element_id]["attrs"]
        assert attrs.get("type") == "number", f"#{element_id} must remain a number input"
        assert attrs.get("max") == "16384", f"#{element_id} must declare max=16384"


def test_object_settings_expose_complete_nested_semantic_contract_controls():
    _assert_ids_inside("objectSettings", (
        "objectUsage", "objectIdentitySubtype", "objectForm", "objectMaterial", "objectFunction",
        "objectView", "objectScaleBasis", "objectTileRelativeWidth", "objectTileRelativeHeight",
        "objectCharacterRelative", "objectFootprintWidth", "objectFootprintDepth",
        "objectSourceWidth", "objectSourceHeight", "objectPaddingTop", "objectPaddingRight",
        "objectPaddingBottom", "objectPaddingLeft", "objectPivotX", "objectPivotY",
        "objectGroundX", "objectGroundY", "objectYSortX", "objectYSortY", "objectSnapPoints",
        "objectShadowMode", "objectShadowBaked", "objectStates", "objectVariantDefinitions",
        "objectCollision", "objectInteraction", "objectCustomProperties",
    ))
    for element_id in ("objectPivotX", "objectGroundX", "objectYSortX", "objectSnapPoints", "objectCollision"):
        node = DOM.by_id[element_id]
        assert node["attrs"].get("aria-label") or re.search(rf'<label[^>]+for="{element_id}"', HTML)


@pytest.mark.parametrize("name", [
    "currentAssetFamily", "currentAssetSubtype", "setAssetFamily",
    "renderAssetSubtypeOptions", "updateAssetFamilyUi",
])
def test_asset_family_state_and_render_functions_exist(name):
    _function_body(name)


def test_family_ui_updater_addresses_every_family_panel_and_actor_effect_split():
    body = _function_body("updateAssetFamilyUi")
    for token in (
        "spriteSettings", "tileSettings", "uiSettings", "objectSettings",
        "character", "monster", "npc", "effect",
    ):
        assert re.search(rf"['\"]{re.escape(token)}['\"]", body), (
            f"updateAssetFamilyUi() must represent {token!r}"
        )
    assert re.search(r"classList\s*\.\s*(?:toggle|add|remove)|\.hidden\s*=", body), (
        "Family switching must actually change conditional visibility"
    )


def test_family_tabs_and_subtype_changes_are_wired_to_the_state_setters():
    assert re.search(
        r"assetFamilyTabs[\s\S]{0,1400}(?:addEventListener\s*\(\s*['\"]click['\"]|\.onclick\s*=)"
        r"[\s\S]{0,1000}\bsetAssetFamily\s*\(", JS,
    )
    assert re.search(
        r"assetSubtype[\s\S]{0,800}(?:addEventListener\s*\(\s*['\"]change['\"]|\.onchange\s*=)"
        r"[\s\S]{0,500}\bupdateAssetFamilyUi\s*\(", JS,
    )


def test_recipe_registry_initialization_runs_after_actor_state_and_tool_wiring():
    """Async recipe initialization must start only after its UI dependencies exist."""
    state = re.search(
        r"\blet\s+lastActorAnimationPreset\s*=\s*['\"]idle['\"]\s*;", JS
    )
    registry_load = re.search(
        r"^\s*loadAssetRecipeRegistry\s*\(\s*\)\s*;",
        JS,
        re.MULTILINE,
    )
    tool_wiring = re.search(
        r"for\s*\([^)]*document\.querySelectorAll\s*\(\s*['\"]\.tool-button['\"]\s*\)[\s\S]{0,300}"
        r"\.onclick\s*=\s*\(\)\s*=>\s*activateTool\b",
        JS,
    )
    assert state, "Expected actor-animation state used by syncPixelAssetWorkflowUi()"
    assert tool_wiring, "Expected toolbar buttons, including AI, to remain wired"
    assert registry_load, "Expected async recipe-registry initialization"
    initial_gate = next(
        (
            match
            for match in re.finditer(
                r"^\s*applyRecipeRegistryToGenerationUi\s*\(\s*\)\s*;",
                JS,
                re.MULTILINE,
            )
            if tool_wiring.start() < match.start() < registry_load.start()
        ),
        None,
    )
    assert initial_gate, "Generation controls must be gated before loading recipes"
    assert state.start() < tool_wiring.start() < initial_gate.start() < registry_load.start(), (
        "Initialize actor state and toolbar handlers, disable unvalidated generation, then "
        "start the asynchronous recipe-registry load"
    )


def test_canonical_walk_and_phase25_action_lock_source_contracts_remain_represented():
    # Guardrails for Phase 2 migration: classification must not rewrite sprite QA.
    for token in (
        "recipe.beats.join(',') !== 'N,L,N,R'",
        "Reference Identity Lock", "Full-Frame Pose Lock", "Equipment Lock",
        "Direction Lock", "Root Lock", "Motion Read", "Loop Read", "Production Clean",
    ):
        assert token in JS
    for action in ("idle", "walk", "attack", "jump", "cast", "hurt", "death"):
        assert re.search(rf"\b{action}\s*:", JS), f"Missing Phase25 action constant {action}"


def test_family_tabs_are_complete_roving_aria_tabs_with_keyboard_navigation():
    panel_by_family = {"sprite": "spriteSettings", "tile": "tileSettings", "ui": "uiSettings", "object": "objectSettings"}
    for index, record in enumerate(DOM.family_tabs):
        family = record["attrs"]["data-asset-family"]
        attrs = record["attrs"]
        assert attrs.get("id") == f"assetFamilyTab-{family}"
        assert attrs.get("aria-controls") == panel_by_family[family]
        assert attrs.get("tabindex") == ("0" if index == 0 else "-1")
        panel = DOM.by_id[panel_by_family[family]]["attrs"]
        assert panel.get("role") == "tabpanel"
        assert panel.get("aria-labelledby") == attrs["id"]
    assert "keydown" in JS
    for key in ("ArrowLeft", "ArrowRight", "Home", "End"):
        assert key in JS


def test_effect_hides_every_legacy_actor_only_workflow_and_syncs_helper():
    body = _function_body("updateAssetFamilyUi")
    for actor_group in ("pixelMotionControls", "pixelDirectionControls", "pixelFrameControls", "pixelReferenceControls", "pixelLegacyDirectionControls", "pixelAdvancedBatch"):
        assert actor_group in body
    assert "syncPixelAssetWorkflowUi" in body


def test_effect_workflow_help_has_stable_hooks_and_dynamic_effect_copy():
    for element_id in (
        "pixelStaticModeNotice", "pixelReferenceGenerationHint", "pixelWorkflowHint",
    ):
        assert element_id in DOM.by_id, f"Missing dynamic workflow copy hook #{element_id}"

    body = _function_body("syncPixelAssetWorkflowUi")
    for element_id in (
        "pixelStaticModeNotice", "pixelReferenceGenerationHint", "pixelWorkflowHint",
    ):
        assert element_id in body, f"Workflow sync must update #{element_id}"
    for phrase in (
        "이펙트 시퀀스", "1회/반복", "프레임 수", "피벗",
        "캐릭터 방향/장비 설정 없음", "배경 제거 후 프레임 시퀀스 유지",
    ):
        assert phrase in body, f"Effect workflow help must explain {phrase!r}"

    # The same updater must restore actor reference/action/direction guidance.
    for phrase in ("선택한 이미지 레이어", "동작", "방향", "프레임 수"):
        assert phrase in body, f"Actor workflow help must restore {phrase!r} guidance"


def test_legacy_type_mapping_is_total_and_product_korean_labels_are_exact():
    body = _function_body("updateAssetFamilyUi")
    assert "legacyAssetTypeForFamily" in body
    assert re.search(r"function\s+legacyAssetTypeForFamily\b", JS)
    for label in ("문/통로", "상태 배지", "커서/선택 표시", "기계/도구", "환경 소품", "상호작용 오브젝트", "파괴 상태 오브젝트"):
        assert label in JS


def test_server_authoritative_prompt_builder_is_not_duplicated_in_provider_request():
    body = _function_body("generateAiAsset")
    assert "buildAssetFamilyPrompt" not in body
    assert re.search(r"const\s+prompt\s*=\s*corePrompt", body)
    assert "pixelAssetType" not in body
    prompt_body = _function_body("buildAssetFamilyPrompt")
    for family in ("sprite", "tile", "ui", "object"):
        assert re.search(rf"['\"]{family}['\"]", prompt_body)
    assert "buildPixelAssetPrompt" in prompt_body


def test_family_generate_button_has_shared_inflight_guard_catch_and_finally_restore():
    assert re.search(r"(?:let|const)\s+assetGenerationInFlight\b", JS)
    body = _function_body("generateAiAsset")
    assert "assetGenerationInFlight" in body
    assert "familyGenerateAi" in body
    assert "finally" in body
    wiring = re.search(r"familyGenerateAi[\s\S]{0,500}addEventListener[\s\S]{0,500}", JS)
    assert wiring and ".catch" in wiring.group(0)


def test_generation_progress_reports_real_stage_and_elapsed_time_without_fake_percent():
    for element_id in ("assetGenerationProgress", "assetGenerationProgressBar", "assetGenerationProgressText"):
        assert element_id in JS
    assert "beginGenerationProgress" in JS
    assert "updateGenerationProgress" in JS
    assert "finishGenerationProgress" in JS
    body = _function_body("generateAiAsset")
    for stage in ("1/3", "2/3", "3/3"):
        assert stage in body
    assert "elapsed" in JS.lower() or "경과" in JS


def test_asset_result_omits_embedded_reference_bytes_and_retry_rehydrates_them():
    assert "compactAssetResultPayload" in JS
    assert "reference_asset_url" in JS
    retry = _function_body("retryAssetResult")
    assert "srcToDataUrl" in retry


def test_reference_direction_and_chroma_strategy_are_advanced_but_still_wired():
    assert "pixelAdvancedReference" in JS
    assert "ensureAdvancedReferenceUi" in JS
    sprite = _function_body("buildSpriteContract")
    assert "inferReferenceDirection" in JS
    assert "reference_direction: inferReferenceDirection()" in sprite
    assert "pixelReferenceDirection" not in sprite
    assert "pixelChromaMode" in sprite


def test_number_reader_preserves_zero_and_structured_family_values_are_validated():
    assert re.search(r"controlNumber[\s\S]{0,250}Number\.isFinite", JS)
    obj = _function_body("buildObjectContract")
    # Every numeric semantic is read through the local zero-safe finite-number adapter;
    # open array/object fields must be parsed and shape-checked, not blindly copied.
    for element_id in (
        "objectPaddingTop", "objectPaddingLeft", "objectPivotX", "objectGroundX",
        "objectYSortX", "objectSourceWidth", "objectSourceHeight",
    ):
        assert re.search(rf"\bn\(\s*['\"]{element_id}['\"]", obj)
    assert re.search(r"const\s+n[\s\S]{0,220}Number\.isFinite", obj)
    assert "JSON.parse" in obj and "Array.isArray" in obj and "throw new Error" in obj
    for element_id in ("objectSnapPoints", "objectStates", "objectVariantDefinitions", "objectCollision", "objectInteraction", "objectCustomProperties"):
        assert element_id in obj
    tile = _function_body("buildTileContract")
    assert "Array.isArray" in tile and "throw new Error" in tile
    ui = _function_body("buildUiContract")
    assert "JSON.parse" in ui and "throw new Error" in ui
    assert "uiDecorDensity" in ui and "uiOpacity" in ui


def test_actual_ui_state_default_is_authoritative_state_array_source():
    assert DOM.by_id["uiStates"]["attrs"].get("value") == "normal,hover,pressed,disabled"


def test_shared_creation_controls_are_in_ai_panel_and_outside_family_panels_in_product_order():
    shared_ids = (
        "assetCorePrompt", "assetStylePreset", "assetStyleNotes",
        "assetOutputWidth", "assetOutputHeight", "assetBackground",
    )
    for element_id in shared_ids:
        assert element_id in DOM.by_id, f"Missing shared creation control #{element_id}"
        ancestors = DOM.by_id[element_id]["ancestors"]
        assert "assetAiPanel" in ancestors
        assert not set(ancestors) & {"spriteSettings", "tileSettings", "uiSettings", "objectSettings"}
    positions = [HTML.index(f'id="{element_id}"') for element_id in (
        "assetFamilyTabs", "assetSubtype", "assetCorePrompt", "assetStylePreset",
        "spriteSettings", "assetOutputWidth", "familyGenerateAi",
    )]
    assert positions == sorted(positions), "Required product order is tabs → subtype → request → style → details → output → generate"


def test_shared_request_has_dynamic_family_specific_korean_copy_and_drafts():
    assert DOM.by_id["assetCorePrompt"]["tag"] == "textarea"
    for label in (
        "생성할 캐릭터·몬스터·NPC·이펙트",
        "생성할 타일·맵의 재질·환경·용도",
        "생성할 UI의 기능·구조·시각 콘셉트",
        "생성할 오브젝트의 형태·재질·용도",
    ):
        assert label in JS
    for example in ("해골 기사", "이끼 낀 석조", "인벤토리", "황동 보물 상자"):
        assert example in JS
    assert re.search(r"asset(?:Family|Creation)Drafts", JS)
    set_body = _function_body("setAssetFamily")
    assert "saveAssetCreationDraft" in set_body and "restoreAssetCreationDraft" in set_body


def test_shared_style_is_primary_and_legacy_sprite_primary_controls_are_hidden_compatibility_only():
    for element_id in ("pixelSubject", "pixelStylePreset", "pixelPalette"):
        assert element_id in DOM.by_id
        attrs = DOM.by_id[element_id]["attrs"]
        assert "hidden" in attrs.get("class", "").split() or "hidden" in attrs or attrs.get("type") == "hidden"
    pixel_prompt = _function_body("buildPixelAssetPrompt")
    assert "assetCorePrompt" in pixel_prompt
    assert "assetStylePreset" in pixel_prompt
    assert "assetStyleNotes" in pixel_prompt


def test_output_controls_are_bounded_and_explain_target_not_provider_guarantee():
    for element_id in ("assetOutputWidth", "assetOutputHeight"):
        attrs = DOM.by_id[element_id]["attrs"]
        assert attrs.get("type") == "number"
        assert int(attrs.get("min", 0)) >= 1
        assert int(attrs.get("max", 999999)) <= 4096
    assert "요청 대상·내보내기 크기" in HTML
    assert "모델 원본 크기를 보장하지 않습니다" in HTML


def test_generation_reads_shared_core_rejects_empty_and_debug_exposes_prompt_builder():
    body = _function_body("generateAiAsset")
    assert "assetCorePrompt" in body
    assert "aiPrompt" not in body and "pixelSubject" not in body
    assert re.search(r"if\s*\(\s*!corePrompt", body)
    debug = JS[JS.index("window.__assetStudioDebug"):JS.index("window.__assetStudioDebug") + 500]
    assert "buildAssetFamilyPrompt" in debug


def test_non_sprite_prompt_branches_never_use_actor_builder_or_hidden_subject_fallback():
    body = _function_body("buildAssetFamilyPrompt")
    assert "pixelSubject" not in body
    assert "Reusable game asset" not in body
    actor_call = body.index("buildPixelAssetPrompt")
    tile_branch = body.index("family === 'tile'")
    assert actor_call < tile_branch
    assert "buildPixelAssetPrompt" not in body[tile_branch:]
