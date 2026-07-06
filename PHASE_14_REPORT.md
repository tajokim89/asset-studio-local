# Phase 14 Report — Animation Preview

## Scope
Add the first real animation preview loop for generated/uploaded sprite sheets so idle/walking assets can be checked before exporting.

## Implemented
- Added `애니메이션 미리보기` section under Sprite Sheet Extract.
- Uses the existing selected image layer + current grid slice values.
- Controls:
  - Frames
  - FPS
  - Mode: `loop` / `pingpong`
  - `미리보기 재생`
  - `정지`
- Builds frame PNGs from the selected sprite sheet cells.
- Displays:
  - live preview stage
  - frame strip thumbnails
- Uses `image-rendering: pixelated` for preview clarity.

## Verification
- Added static regression tests: `tests/test_phase14_animation_preview_static.py`
- RED confirmed before implementation: 3 failed.
- After implementation:
  - `pytest tests/ -q` → 90 passed
  - `node --check src/main.js` → pass
  - `python3 -m py_compile server.py` → pass
  - `git diff --check` → pass
- Browser verification:
  - Opened `http://127.0.0.1:4184/?v=phase14-animation-preview`
  - Confirmed Animation Preview UI appears.
  - Created a deterministic 64×16 transparent test sprite sheet in browser.
  - Added it as an image layer.
  - Grid: 4 cols × 1 row, cell 16×16.
  - Built animation preview.
  - Result: 4 frames, 4 thumbnails, live stage shows `1/4 · loop`.
  - Console JS errors: 0.

## Next Phase
Phase 15 should focus on actual generation/export workflow:
- Generate idle/walk sprite sheet.
- Auto-clean background.
- Auto-grid detect from selected preset.
- One-click preview.
- Export frame ZIP / GIF/WebP if supported.
