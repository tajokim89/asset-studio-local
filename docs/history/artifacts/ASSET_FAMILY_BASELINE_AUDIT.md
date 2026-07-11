# Asset Family Live Baseline Audit

- Audit task: A1 — visible UI → payload → prompt → postprocess → preview → QA → export baseline
- Repository: `/Users/tajokim/asset-studio-local`
- Audit date: 2026-07-10
- Scope read: `SESSION_HANDOFF_2026-07-10.md`, `index.html`, `src/main.js`, `server.py`, `tests/test_asset_family_ui_static.py`, `tests/test_asset_family_payload_contract.py`
- Production code changes made by this task: **none**

## 1. Verdict rules

| Verdict | Meaning in this audit |
|---|---|
| **DONE** | The live code has an explicit, connected implementation for this stage and no in-scope contradictory path was found. |
| **PARTIAL** | A useful implementation exists, but it does not satisfy the family-specific production loop or omits required metadata/validation. |
| **MISSING** | No family-specific implementation was found in the allowed files. |
| **CONTRADICTORY** | Two live paths or contracts assign incompatible semantics to the same request/result. |

`DONE` is stage-local. A family is not complete merely because its UI, payload, or prompt stage is DONE. Under the anti-facade gate in `SESSION_HANDOFF_2026-07-10.md` §§18–22, all stages through family-specific preview, QA, and engine-usable export are required.

## 2. Dirty-tree baseline recorded before this audit

### 2.1 Commands and results

Commands run before creating this file:

```text
git status --short
git diff --stat
git diff --check
git diff -- SESSION_HANDOFF_2026-07-10.md index.html src/main.js server.py \
  tests/test_asset_family_ui_static.py tests/test_asset_family_payload_contract.py
git diff --numstat -- <same six files>
```

Observed baseline:

- `git diff --stat`: **63 files changed, 1471 insertions(+), 2691 deletions(-)**.
- `git diff --check`: **PASS** (no output, exit 0).
- Tracked bulk deletions of historical root reports and many tracked modifications were already present.
- Tracked major modifications include `README.md`, `index.html`, `server.py`, `src/main.js`, `styles/app.css`, and many tests.
- Untracked content already includes `SESSION_HANDOFF_2026-07-10.md`, `docs/`, nested `asset-studio-local/`, scripts, and tests.
- This pre-existing dirty tree is baseline context, **not an A1 change**.

### 2.2 In-scope file status/diff review

| File | Baseline status | Diff review result |
|---|---:|---|
| `SESSION_HANDOFF_2026-07-10.md` | `??` | Untracked; therefore ordinary `git diff --` is empty. Read in full. It explicitly records the facade/effect blockers and required production loop. |
| `index.html` | `M` | `+55/-20`; reviewed. Adds family tabs, shared request/style/output shell, actor/effect split, tile/UI/object controls, and shared Generate button while retaining legacy hidden sprite hooks/tools. |
| `src/main.js` | `M` | `+572/-110`; reviewed. Adds family state/builders/prompts/generation path, but still routes results into generic canvas/gallery/thumbnail and legacy sprite tools. |
| `server.py` | `M` | `+482/-69`; reviewed. Adds family allow-list normalizer/prompt branches and actor/effect postprocess gating; tile/UI/object remain raw bypasses. |
| `tests/test_asset_family_ui_static.py` | `??` | Untracked; ordinary `git diff --` is empty. Read in full. Tests UI shell/state/prompt builder wiring, not the full family preview/QA/export loop. |
| `tests/test_asset_family_payload_contract.py` | `??` | Untracked; ordinary `git diff --` is empty. Read in full. Contains expectations ahead of live server code for normalized shared style/output/background handling. |

## 3. Executive baseline

| Representative type | Core request | Visible controls | Nested payload | Prompt branch | Server normalizer | Postprocess | Preview | QA | Export | Overall |
|---|---|---|---|---|---|---|---|---|---|---|
| `sprite/character` | DONE | DONE | DONE | DONE | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | **PARTIAL** |
| `sprite/effect` | DONE | DONE | DONE | DONE | PARTIAL | PARTIAL | **CONTRADICTORY** | PARTIAL | **CONTRADICTORY** | **CONTRADICTORY** |
| `tile/terrain` or `tile/tileset` | DONE | DONE | DONE | DONE | PARTIAL | MISSING | MISSING | MISSING | MISSING | **PARTIAL** |
| `ui/button` or `ui/main_panel` | DONE | DONE | DONE | DONE | PARTIAL | MISSING | MISSING | MISSING | MISSING | **PARTIAL** |
| `object/interactable` or `object/prop` | DONE | DONE | DONE | DONE | PARTIAL | MISSING | MISSING | MISSING | MISSING | **PARTIAL** |

Cross-cutting qualification: the browser payload does include `style` and `output` at runtime, but `server.normalize_asset_generation_payload()` drops both objects. The current result can still be influenced by these controls because `generateAiAsset()` sends the already assembled browser prompt as top-level `prompt`; this is an accidental text-path dependency, not a normalized server contract. The focused payload suite exposes this mismatch.

## 4. Representative trace 1 — `sprite/character`

| Stage | Verdict | Live code evidence | Consequence / minimum next edit |
|---|---|---|---|
| Core request | **DONE** | `index.html` `#assetCorePrompt`; `src/main.js` `ASSET_FAMILY_CREATION_COPY.sprite`, `saveAssetCreationDraft()`, `restoreAssetCreationDraft()`; `generateAiAsset()` rejects an empty core request. | No minimum structural edit at this stage. |
| Visible controls | **DONE** | `index.html` `#spriteSettings`: `#pixelAnimationPreset`, `#pixelDirectionMode`, `#pixelTargetDirection`, `#pixelReferenceDirection`, `#pixelChromaMode`, `#pixelWalkFrames`; shared style/output controls. `updateAssetFamilyUi()` shows actor groups for character/monster/NPC. | Add explicit FPS/cell/pivot/root controls only when implementing engine contract; current action/direction controls are live. |
| Nested payload | **DONE** | `buildSpriteContract()` returns action/direction/frame/reference/chroma/no-VFX fields; `buildAssetGenerationPayload()` adds only `payload.sprite`; `generateAiAsset()` adds temporary actor-only flat compatibility fields. | Retire duplicate flat compatibility only after all actor callers use nested contract. |
| Prompt branch | **DONE** | Browser: `buildAssetFamilyPrompt()` → `buildPixelAssetPrompt()` → `buildDirectionalSpriteSheetContract()` and `actionVisualAcceptanceGate()`. Server: `build_asset_family_prompt()` actor branch. Phase-25 locks and action beats are present. | Avoid double-appending browser and server family contract in a later cleanup, but actor semantics are explicit now. |
| Server normalizer | **PARTIAL** | `normalize_asset_generation_payload()` actor branch allow-lists animation, direction, target/reference, frame count, chroma and defaults legacy actor fields only, but drops common `style`/`output`. | Preserve actor-only legacy fallback boundary and add common style/output normalization. |
| Postprocess | **PARTIAL** | `/api/generate` and `/api/generate-reference` gate `postprocess_pixel_generation_bytes()` with `is_actor_sprite`. It performs chroma cleanup, residue cleanup, alpha QA, and single-direction trim only when normalized action is idle. | Define behavior for non-idle single-direction candidate errors and guarantee sheet geometry/frame validation; current postprocess is cleanup-focused, not a complete actor validator. |
| Preview | **PARTIAL** | Generated image is adopted to Fabric canvas (`addImageUrl()`), gallery, and `recordPixelAssetResult()`. Actor reference generation can call `setFrontIdleGridForImage()`, build grid slices, and `buildAnimationPreview()`. Generic family Generate does not automatically establish actor slices/preview. Preview uses `buildAnimationFramesFromGrid()` and per-slice canvases. | Connect the primary family Generate result to explicit actor sheet geometry, fixed-cell playback, direction comparison, and root/pivot/foot overlays. |
| QA | **PARTIAL** | Server returns `chroma_green_report`, `cleanup_qa`, and `direction_qa`; browser writes a generic `#pixelQaSummary`. Prompt contains 8 locks/action visual gates, but no code here executes motion-read visual QA. | Implement actor QA result schema and actual frame-count/root/pivot/motion-read gate; do not present alpha/green metrics as production PASS. |
| Export | **PARTIAL** | Generic full/selected PNG: `exportFull()`, selected export. Sprite tools: `exportSpriteSlicePng()`, `exportAllSpriteSlicesZip()`, grid ZIP. Existing manifests hold crop/grid geometry, but no family schema version, action tag, FPS/duration, pivot/root, or coordinate convention. | Extend actor export manifest with family/type/action/frame order/FPS/cell/gap/pivot/root/schema version; bind it to the accepted generation result. |

### Character-specific fallback blocker

**Blocker B1 — character/idle fallback**

- `currentAssetFamily()` falls back to `sprite`; `currentAssetSubtype()` falls back to the first sprite subtype (`character`).
- Server `normalize_asset_generation_payload()` defaults invalid/missing family to `sprite`, invalid/missing sprite type to `character`, and actor action to `idle` (`server.py` `normalize_asset_generation_payload()`).
- `animationPresetSpec()` returns `specs.idle` for an unknown preset.
- This is acceptable only for legacy actor compatibility. It is dangerous if any family/type context is omitted, because malformed tile/UI/object requests silently become `character/idle` instead of failing closed.

**Minimum fix:** make new family API requests require valid `asset_family` and `asset_type` (400 on invalid/missing), and confine character/idle fallback to an explicitly detected legacy actor payload adapter.

## 5. Representative trace 2 — `sprite/effect`

| Stage | Verdict | Live code evidence | Consequence / minimum next edit |
|---|---|---|---|
| Core request | **DONE** | Shared `#assetCorePrompt`, sprite-specific copy, and draft preservation are used. | No minimum shell edit. |
| Visible controls | **DONE** | `index.html` `#effectControls`: `#effectCategory`, `#effectLoop`, `#effectFrameCount`, `#effectPivot`, `#effectSizeReference`. `updateAssetFamilyUi()` hides actor groups and shows effect controls. | Add rows/cols/gap/FPS/envelope and normalized pivot coordinates for a complete sequence contract. |
| Nested payload | **DONE** | `buildSpriteContract('effect')` sends `animation_mode: effect_sequence`, category, loop, frame count, pivot, size reference, and no actor direction fields. Server effect normalizer enforces `direction_mode: none`. | Expand one source of truth with layout, envelope, FPS/duration, padding, trim mode, anchor coordinates. |
| Prompt branch | **DONE** | Browser `buildAssetFamilyPrompt()` has isolated effect sequence language; server `build_asset_family_prompt()` has an effect-only branch; reference collector `collect_codex_reference_effect_b64()` uses context-only reference semantics. | Include full sequence layout/envelope/gutter contract, not just frame count and pivot. |
| Server normalizer | **PARTIAL** | The explicit effect branch in `normalize_asset_generation_payload()` excludes actor direction/equipment defaults and bounds frame count 1–16, but common `style`/`output` is dropped. | Extend the family schema and normalize the common contract; do not reuse actor defaults. |
| Postprocess | **PARTIAL** | `postprocess_effect_generation_bytes()` is selected by both generation endpoints and bypasses actor residue/direction collapse. It only performs raw/outer chroma cleanup plus generic chroma report. | Add effect sequence boundary/count/gutter/glow/pivot validation and preserve sequence metadata. |
| Preview | **CONTRADICTORY** | Effect payload requests (default) 6 frames, but `effectivePixelAnimationPreset()` returns `ui_static` for every non-actor, `requestedPixelFrameCount()` returns 1, `syncPixelAssetWorkflowUi()` writes `pixelWalkFrames=1`, and `applyPixelWorkflowGridDefaults()` therefore configures a one-frame grid. `recordPixelAssetResult()` is only a thumbnail. `buildAnimationFramesFromGrid()` uses each slice's own dimensions with no common envelope/pivot restoration. | Create `effectSequenceSpec()` as the sole frame/layout source and an effect common-envelope preview. Never route effect sequence through `ui_static`/actor helpers. |
| QA | **PARTIAL** | Server reports alpha/green and `status: effect-isolated`, but does not validate actual frame count, empty cells, gutter alpha, detached particle preservation, low-alpha glow, common pivot drift, or loop transition. Browser summary is actor-shaped (`direction`, alpha/corners/green). | Add effect-specific QA schema and UI with frame/layout/envelope/pivot/glow metrics and fail reasons. |
| Export | **CONTRADICTORY** | Generic sprite ZIP can cut cells, but effect downstream may have been configured as one frame. Manifest lacks `sourceSize`, `trimRect`/offset, normalized pivot, playback/FPS/duration, effect kind, layout/gap. Connected-component export can split particles as assets. | Implement effect-grid untrimmed sequence export first; then optional trim + restoration metadata. Do not use connected components as animation frame detection. |

### Effect-specific blocker

**Blocker B2 — effect → `ui_static` / 1 frame**

The live request contract says `effect_sequence` and sends `effectFrameCount`, while legacy downstream helpers say `ui_static`, one frame, single static asset/no sprite sheet. Specific identifiers: `buildSpriteContract()`, `effectivePixelAnimationPreset()`, `requestedPixelFrameCount()`, `syncPixelAssetWorkflowUi()`, `applyPixelWorkflowGridDefaults()`, `buildPixelAssetPrompt()` legacy non-actor branch, `generateFrontIdleFromSelected()` status/result labels. This is a direct contradiction from generation through preview/export.

## 6. Representative trace 3 — `tile/terrain` and `tile/tileset`

| Stage | Verdict | Live code evidence | Consequence / minimum next edit |
|---|---|---|---|
| Core request | **DONE** | Dynamic tile label/placeholder/help in `ASSET_FAMILY_CREATION_COPY.tile`; family draft preservation. | No shell edit. |
| Visible controls | **DONE** | `#tileSettings`: size, single/tileset, rows/cols, seamless, connections, variants, gap. Subtypes include terrain and tileset. | For product completion add topology/transition, atlas margin/spacing, collision/navigation and variant frequency. |
| Nested payload | **DONE** | `buildTileContract()` and selected-only `payload.tile`; no actor keys. | Extend schema rather than reusing sprite grid globals. |
| Prompt branch | **DONE** | Browser and server tile branches consume all current tile controls and exclude actor/action/UI language. | Add terrain topology/rule coverage semantics. |
| Server normalizer | **PARTIAL** | `normalize_asset_generation_payload()` has a dedicated bounded tile allow-list, but drops common `style`/`output`. | Add normalized common style/output and validate booleans robustly. |
| Postprocess | **MISSING** | Both generation endpoints use raw bypass for non-actor/non-effect: `qa={status:'bypassed', method:'tile-raw'}`. No tile seam/edge/atlas preservation validator. | Add `postprocess_tile_generation_bytes()` (or explicit no-transform + tile validator) and carry tile contract to it. |
| Preview | **MISSING** | Result goes to generic Fabric canvas/gallery and `recordPixelAssetResult()` thumbnail. No 3×3 repeat, random repeat, seam zoom, terrain brush, transition/rule, or collision overlay exists in the allowed live path. | Add tile result model and repeat/topology/collision preview panel keyed by generation ID. |
| QA | **MISSING** | Raw bypass is labeled QA but performs no tile-specific checks. | Add dimensions/grid divisibility, seam delta, empty-cell, rule coverage, variant repetition and metadata validation. |
| Export | **MISSING** | Only generic PNG and generic sprite slice ZIP are present; no tile atlas/index/rules/collision/navigation/schema export. | Add tile atlas + tile ZIP + family manifest (rules, coordinates, margin/gap, collision/navigation). |

## 7. Representative trace 4 — `ui/button` and `ui/main_panel`

| Stage | Verdict | Live code evidence | Consequence / minimum next edit |
|---|---|---|---|
| Core request | **DONE** | Dynamic UI function/structure/concept copy and draft preservation. | No shell edit. |
| Visible controls | **DONE** | `#uiSettings`: source width/height, nine-slice, margin, safe area, border, corner, decoration density, background opacity, text-free, states. | Replace scalar 9-slice margin with four sides if needed; add stretch/tile mode and internal padding. |
| Nested payload | **DONE** | `buildUiContract()` selected-only `payload.ui`, with explicit static/none/1 invariants. | Keep static invariants UI-local; add validated state array rather than free text eventually. |
| Prompt branch | **DONE** | In the combined browser→server route, current UI settings are consumed: the browser prompt directly includes dimensions, nine-slice, margin, safe area, density, opacity, text-free, and states, while `border_weight`/`corner_style` travel in the nested UI payload and are added by the server branch. The resulting prompt demands static reusable/text-free UI, no actor or scene. | Ensure state request means actual separate deliverables, not merely prompt prose. |
| Server normalizer | **PARTIAL** | The dedicated UI allow-list and bounds retain the nested UI fields, including zero-preserving opacity/density, but drop common `style`/`output`. | Normalize shared style/output and preserve requested actual dimensions beyond prose. |
| Postprocess | **MISSING** | Server raw bypass (`ui-raw`); no source-size enforcement, corner/alpha preservation, state splitting, or 9-slice validation. | Add UI-specific postprocess/validator that does not sprite-trim corners. |
| Preview | **MISSING** | Generic canvas/gallery/thumbnail only; no 1:1 preview, nine-slice/safe-area guides, resize comparison, temporary content assembly, or state comparison. | Add actual-size and 3-size nine-slice preview with guides/states. |
| QA | **MISSING** | No corner-preservation, safe-area, resize artifact, text-free, dimensions, or state-count QA. | Add family QA with per-state and resize test results. |
| Export | **MISSING** | Generic PNG only; no state ZIP or nine-slice/safe-area/stretch metadata. | Add text-free state files + UI manifest with source size, four margins, safe area, stretch/tile modes, schema version. |

## 8. Representative trace 5 — `object/interactable` and `object/prop`

| Stage | Verdict | Live code evidence | Consequence / minimum next edit |
|---|---|---|---|
| Core request | **DONE** | Dynamic object form/material/use copy and family draft preservation. | No shell edit. |
| Visible controls | **DONE** | `#objectSettings`: view, world scale, pivot, shadow, variants, state, usage, padding, ground contact. | Add collision shape, interaction point, Y-sort/ground point, footprint/snap, state set, optional separate shadow/icon derivative. |
| Nested payload | **DONE** | `buildObjectContract()` and selected-only `payload.object`; no actor animation/direction/cleanup keys. | Extend object contract with placement/interaction metadata. |
| Prompt branch | **DONE** | Browser/server object branches consume all current controls and exclude actor/UI/scene semantics. | Clarify interactable state set and derivative outputs. |
| Server normalizer | **PARTIAL** | The dedicated object allow-list has bounded variants/padding and enumerated view/scale/pivot/shadow/usage, but drops common `style`/`output`. | Add common style/output normalization and expanded object schema. |
| Postprocess | **MISSING** | Raw bypass (`object-raw`); no alpha padding/pivot/shadow/state preservation validator. | Add object-specific preserve/validate path and compute explicit source canvas/pivot/ground metadata. |
| Preview | **MISSING** | Generic canvas/gallery/thumbnail only; no tile grid placement, character scale comparison, pivot/ground/collision/interaction overlay, state/variant scene, or world/icon comparison. | Add object placement preview and overlays keyed to object metadata. |
| QA | **MISSING** | No world scale, padding, pivot, ground, collision, state, variant, or shadow QA. | Add object-specific placement and metadata checks. |
| Export | **MISSING** | Generic PNG only; no state/variant atlas/ZIP or pivot/ground/collision/interaction/scale manifest. | Add object files + engine-oriented manifest and optional icon/shadow derivatives. |

## 9. Cross-cutting blockers

### B3 — Partly effective prompt controls, but incomplete shared server/output contract

The shared controls are visibly live and the browser runtime object has `style` and `output` (`buildAssetGenerationPayload()` uses object shorthand), but:

1. `normalize_asset_generation_payload()` does not allow-list or retain `style` or `output`.
2. `build_asset_family_prompt()` cannot consume normalized style/output.
3. No `asset_background_mode()` helper exists even though the payload tests require one.
4. Endpoints instead read top-level compatibility `background_mode`; requested output width/height is prompt prose only and no resize/export enforcement occurs.
5. Current generation often still sees style/output because the browser sends a preassembled `prompt`; the server then appends another family section. This makes server correctness dependent on client prose and duplicates responsibility.

The controls are therefore not wholly dead: browser prompt prose carries style and requested background into the generation prompt. What is ineffective is the normalized server contract for both shared objects; requested output dimensions and the nested output background are not enforced by family postprocess/export, so those output semantics are dead beyond prompt guidance (apart from the separate top-level compatibility `background_mode` path). This normalized-boundary contract is **CONTRADICTORY**, directly proven by the focused test failures in §11.

**Minimum fix:** retain bounded `style` and `output` objects in the server normalizer; add safe background mapping; make the server the canonical prompt assembler from core request + normalized contracts; use output contract in postprocess/export or clearly label it as export target only.

### B4 — Generic thumbnail-only result flow

`generateAiAsset()` treats all families alike after the response:

```text
addGallery(url, ...)
addImageUrl(url, ...)
recordPixelAssetResult(url, ...)
```

`recordPixelAssetResult()` creates only `<img>` plus a legacy type/animation text line. There is no durable result object carrying family contract, generation ID, normalized payload, family QA, preview mode, or export manifest. This prevents tile/UI/object from reaching family-specific review and causes effect to inherit actor/static helper semantics.

**Minimum fix:** introduce a normalized `AssetGenerationResult`/result-store record containing family, subtype, normalized contract, output URL/source size, postprocess report, QA report, preview strategy, and export metadata; render family-specific result cards/actions from that record.

### B5 — Generic QA text can overstate readiness

`#pixelQaSummary` is updated for every family with actor-shaped direction/alpha/corner/green fields. Tile/UI/object raw bypass responses are not family QA, and effect `effect-isolated` is not sequence validation. The UI must distinguish `transport/alpha diagnostics` from `family production QA` and fail closed when family QA is absent.

### B6 — Generic export is not family export

`exportFull()`/selected PNG and the sprite slicer ZIP prove that pixels can be downloaded. They do not prove engine usability for any representative type. Existing manifests are crop-oriented and lack a common `schema_version`, family/type, source size convention, and family-specific data. Effect additionally lacks source envelope/trim restoration/pivot/playback.

## 10. Minimum next-task edit map

The audit can be used as an edit map without rediscovery:

1. **Shared normalized contract (first):**
   - `src/main.js`: keep `buildAssetGenerationPayload()` as runtime source; adjust static test parsing if shorthand remains.
   - `server.py`: extend `normalize_asset_generation_payload()` with allow-listed `style`/`output`; add `asset_background_mode()`; update `build_asset_family_prompt()` and both generation endpoints.
   - `tests/test_asset_family_payload_contract.py`: retain runtime assertions and avoid a false negative for JS object shorthand.
2. **Effect contradiction (before generic result tray):**
   - `src/main.js`: split effect sequence helpers from `effectivePixelAnimationPreset()`, `requestedPixelFrameCount()`, `applyPixelWorkflowGridDefaults()`, `buildPixelAssetPrompt()`, `generateFrontIdleFromSelected()`, and `runPixelWorkflow()`.
   - Preserve `effectFrameCount`/layout/envelope/pivot from request to preview/export.
3. **Result model and preview dispatch:**
   - Replace thumbnail-only `recordPixelAssetResult()` behavior with a family-aware result record and dispatch.
   - Actor → fixed-cell/root preview; effect → common-envelope/pivot preview; tile → repeat/topology preview; UI → nine-slice/state preview; object → placement/scale/pivot preview.
4. **Postprocess/QA dispatch in `server.py`:**
   - Keep `postprocess_pixel_generation_bytes()` actor-only.
   - Extend effect validation beyond chroma.
   - Add explicit tile/UI/object preserve + validator branches instead of `*-raw` pseudo-QA.
5. **Family export:**
   - Extend/replace generic slice manifests with family schema version and coordinate convention.
   - Implement the minimum metadata listed in each representative trace before calling that family DONE.
6. **Fail-closed routing:**
   - Reject malformed new family requests instead of silently normalizing to `sprite/character/idle`; maintain a narrow explicit legacy actor adapter.

## 11. Verification baseline

Commands run after code review and before writing this audit:

```text
PY=/Users/tajokim/.hermes/hermes-agent/venv/bin/python
[ -x .venv/bin/python ] && PY=.venv/bin/python
"$PY" -m pytest \
  tests/test_asset_family_ui_static.py \
  tests/test_asset_family_payload_contract.py -q
node --check src/main.js
python3 -m py_compile server.py
git diff --check
```

Results:

- Focused tests: **58 passed, 9 failed**.
- All 9 failures are in the tail of `tests/test_asset_family_payload_contract.py`:
  - one static helper does not recognize the valid JS shorthand `{ ..., style, output }` as keys;
  - server normalizer does not retain shared `style`/`output` (four parameterized failures);
  - server family prompt cannot use normalized style/dimensions/background (three failures);
  - `server.asset_background_mode` is missing (one failure).
- `node --check src/main.js`: **PASS**.
- `python3 -m py_compile server.py`: **PASS**.
- Pre-write `git diff --check`: **PASS**.

No paid generation, browser smoke test, server startup, or external provider request was performed: A1 is a code-grounded baseline audit, and the allowed task scope permits only this document to be created.

## 12. Final conclusion

The live baseline has a substantially implemented **family selection/UI/payload/prompt facade** and a real actor/effect server routing split. It does **not** yet have a complete asset-family production loop:

- `character`: useful actor pipeline, but production preview/visual QA/engine metadata remain partial.
- `effect`: request and server isolation exist, but downstream `ui_static`/one-frame assumptions directly contradict the sequence contract.
- `terrain/tileset`, `button/main_panel`, `interactable/prop`: inputs, nested payloads, prompt branches, and normalizers exist; postprocess, use-context preview, family QA, and engine export are missing.
- Shared style/output normalization is incomplete at the server boundary.
- All families converge on a generic canvas/gallery/thumbnail result path, generic diagnostics, and generic PNG/sprite-slice export.

Therefore no audited family is fully DONE end-to-end. The next task should begin with shared server normalization and the effect frame-source contradiction, then introduce the family-aware result/preview/QA/export contract rather than adding more controls to the current facade.
