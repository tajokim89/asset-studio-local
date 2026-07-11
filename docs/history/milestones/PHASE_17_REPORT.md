# Phase 17 Report — Directional Pixel Sheets + Global Chroma QA

## Scope
- Add direct 8-direction idle/walk controls for pixel character sheets.
- Send direction/animation metadata to the reference-generation backend.
- Fix chroma-key cleanup so internal #00FF00 holes are removed, not only border-connected green.
- Add QA metadata for alpha/corner/green-pixel verification.

## Implemented

### Frontend
- Added pixel sheet controls:
  - `pixelDirectionMode`: single / 4-direction / 8-direction
  - `pixelReferenceDirection`: S, SW, W, NW, N, NE, E, SE
  - `pixelWalkFrames`: 3–8 frames
  - `pixelChromaMode`: `global` / `outer`
- Added buttons:
  - `8방향 Idle 생성`
  - `8방향 Walk 생성`
  - `8방향 Idle+Walk 통합 생성`
- Prompt builder now injects a sprite-sheet contract:
  - 8-direction row order: `N, NE, E, SE, S, SW, W, NW`
  - 4-direction row order: `S, W, E, N`
  - walk columns: `idle -> stepA -> idle -> stepB`
  - explicit reference direction preservation
- Grid defaults now follow direction mode:
  - 8-direction idle: 1 col × 8 rows
  - 8-direction walk: 4 cols × 8 rows
- One-click pixel workflow now uses `chroma_green` + `global` cleanup by default instead of sheet-edge-only cleanup.
- Pixel QA summary shows alpha/corner/green cleanup stats after remove-bg.

### Backend
- `/api/generate-reference` accepts:
  - `direction_mode`
  - `reference_direction`
  - `animation_mode`
  - `walk_frames`
- Reference prompt includes directional/animation contract.
- `/api/remove-bg` accepts `chroma_mode`:
  - `global`: remove all chroma-green pixels, including internal holes.
  - `outer`: legacy border-connected behavior.
- Chroma output now returns QA:
  - image width/height
  - alpha min/max
  - four corner alpha values
  - remaining green pixel count

## Verification
- Static/regression tests: `106 passed in 0.07s`
- JS syntax: `node --check src/main.js`
- Python syntax: `python3 -m py_compile server.py`
- Whitespace diff check: `git diff --check`
- API smoke test:
  - sent a synthetic green-background PNG with an internal green hole
  - `/api/remove-bg` returned `method: chroma-green-key-global`
  - `corner_alpha: [0,0,0,0]`
  - `green_pixels: 0`
- External page load verified:
  - `https://two-satisfy-basket-upc.trycloudflare.com/?v=phase17-directional-chroma-clean`
  - page title: `Pixel Asset Studio`
  - new controls detected: 8-dir mode, reference direction, walk frames, global chroma, 8-dir buttons.

## Notes
- This does not guarantee the image model will always draw perfect true rotations. It now forces the strongest possible prompt/API contract and gives UI/API structure to retry and QA outputs.
- Actual generated sheet quality still needs visual approval per asset.
