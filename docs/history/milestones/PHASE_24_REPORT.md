# Phase 24 Report — Canvas Resize Sprite Grid Sync

## Scope
- Fix sprite grid/animation preview becoming stale after manual canvas size changes.
- Check whether tracked GitHub content contains API keys/secrets.

## Root Cause
- Sprite slices are stored in selected-image-relative coordinates, which is correct.
- However `setCanvasSize()` only changed Fabric canvas width/height and fit view.
- It did not refresh sprite grid cell inputs, guide overlays, or animation preview frames after the selected image/canvas bounds changed.
- JSON project load looked correct because the saved canvas size was restored first, so the grid was generated against the final canvas state.

## Applied
- Added `syncSpriteAfterCanvasResize()` in `src/main.js`.
- On canvas size change:
  - preserves the current sprite source layer id,
  - recalculates grid cell size from the selected image bounds,
  - rebuilds grid-mode `spriteSlices`,
  - re-renders guide overlays from image-relative coordinates,
  - rebuilds the animation preview if preview frames already exist.
- Kept existing `saveHistory()` behavior for canvas size changes.

## Verification
- `node --check src/main.js` passed.
- `git diff --check` passed.
- Browser regression fixture:
  - created 800×200 deterministic 4-frame image sheet,
  - displayed on canvas as 560×140,
  - grid before resize: 4 slices, each 140×140, relative x = 0/140/280/420,
  - resized canvas 1024×1024 → 1280×720,
  - grid after resize remained 4 slices, each 140×140, relative x = 0/140/280/420,
  - guide boxes re-rendered at selected image canvas origin,
  - animation preview rebuilt to 4 frames,
  - browser console JS errors: 0.

## Secret/API Key Scan
- Scanned current tracked files with regexes for OpenAI-style `sk-*`, GitHub `gh*_`, and generic `api_key/token/secret/password` assignments.
- Scanned all git history revisions currently in the repo.
- Findings: 0 likely secrets.
- `.env`, uploads, generated assets, processed assets, exports, and projects are ignored by `.gitignore`.
- Project root `.env` file was not present during this check.

## Not Done
- Not committed/pushed yet after this fix.
