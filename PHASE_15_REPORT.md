# Phase 15 Report — Pixel Workflow One-Click Pipeline

## Scope
Build the first one-click pixel asset workflow so the app stops feeling like a general editor and starts behaving like a sprite/asset generator.

## Implemented
- Added `원클릭 워크플로우` block inside `Pixel Asset Generator`.
- New controls:
  - `Frame W`
  - `Frame H`
  - `생성 후 배경정리`
  - `생성 후 preview`
  - `생성→정리→미리보기`
- Added workflow helpers:
  - `pixelPresetFrameCount()`
  - `applyPixelWorkflowGridDefaults()`
  - `generateAiAsset()`
  - `runPixelWorkflow()`
- Refactored AI generation into reusable `generateAiAsset()`.
- `addImageUrl()` now returns a Promise, so the pipeline can wait until the generated image layer is actually on canvas.
- Workflow sequence:
  1. Build pixel prompt.
  2. Apply grid defaults from animation preset.
  3. Generate pixel asset through existing `/api/generate` flow.
  4. Select generated image layer.
  5. Optional sheet background cleanup via `removeBgSelected('sheet')`.
  6. Re-apply grid defaults.
  7. Detect grid slices.
  8. Optional animation preview.

## Preset Defaults
- `idle` → 4 frames
- `walking 4-frame` → 4 frames
- `walking 6-frame` → 6 frames
- `attack` → 4 frames
- `hurt` → 4 frames
- `UI static` → 1 frame

## Verification
- Added static regression tests: `tests/test_phase15_pixel_workflow_static.py`
- RED confirmed before implementation: 3 failed.
- After implementation:
  - `pytest tests/ -q` → 93 passed
  - `node --check src/main.js` → pass
  - `python3 -m py_compile server.py` → pass
  - `git diff --check` → pass
- Browser verification:
  - Opened `http://127.0.0.1:4184/?v=phase15-pixel-workflow`
  - Confirmed Phase 15 workflow UI loads.
  - Ran deterministic mocked generated 64×16 sprite sheet through `runPixelWorkflow()`.
  - Result:
    - grid cols: 4
    - grid rows: 1
    - cell width: 16
    - animation frames: 4
    - frame strip thumbnails: 4
    - preview stage: `1/4 · loop`
    - status: `도트 워크플로우 완료 · 4 frames`
  - Console JS errors: 0

## Next Phase
Phase 16 should make this production-useful:
- Real generated result QA gate.
- If generated sheet is not aligned, show warning.
- Add frame export ZIP directly from animation preview.
- Add GIF/WebP export if feasible.
- Add asset-pack mode: generate idle + walk + attack + UI/icon set with shared style prompt.
