# Phase 18 Report — Direction-Target Postprocess QA

## Problem
The pixel generator accepted `target_direction` values such as S/SW, but the generated output could still show an entire multi-direction sheet and keep chroma green visible. Prompt-only direction control was not enough.

## Fix
- Added `postprocess_pixel_generation_bytes()` on the server.
- `/api/generate` and `/api/generate-reference` now run postprocess before returning an image to the browser.
- For `direction_mode=single` + `idle`, the server no longer returns the full AI sheet:
  1. normalize chroma green,
  2. remove green globally,
  3. select the requested target slot,
  4. crop to the selected transparent sprite,
  5. return QA metadata.
- Single-target prompt now asks for an internal extraction sheet: one horizontal row ordered `S, SW, W, NW, N, NE, E, SE`.
- Direction wording is now screen-space explicit: SW/W face screen-left, SE/E face screen-right.
- Frontend displays `direction_qa`, alpha/corner alpha, and remaining green pixel count.

## Tests
- Added `tests/test_phase18_pixel_direction_postprocess.py`.
- Synthetic 8-slot chroma sheet verifies SW extracts slot 1 only and removes green.
- Synthetic front/S sheet verifies S extracts slot 0 only.
- Non-chroma multi-component fixture verifies single-target crop still works.
- Static wiring test verifies `/api/generate`, `/api/generate-reference`, and frontend QA display are connected.

## Verification
- `python3 -m pytest tests -q`: 112 passed
- `node --check src/main.js`: pass
- `python3 -m py_compile server.py`: pass
- `git diff --check`: pass

## Real reference verification
Reference image: `/Users/tajokim/.hermes/image_cache/img_1535b5f8aa2a.png`

Generated with `/api/generate-reference` using the same goblin reference:

### SW target
- Output: `/Users/tajokim/asset-studio-local/assets/generated/reference_generated_1783391995.png`
- URL: `/assets/generated/reference_generated_1783391995.png`
- QA:
  - `target_direction`: `SW`
  - `reason`: `selected_equal_grid_slot`
  - `selected_slot`: `1`
  - `corner_alpha`: `[0,0,0,0]`
  - `green_pixels`: `0`
- Visual check: faces screen-left/front-left and keeps the goblin miner identity.

### S target
- Output: `/Users/tajokim/asset-studio-local/assets/generated/reference_generated_1783392063.png`
- URL: `/assets/generated/reference_generated_1783392063.png`
- QA:
  - `target_direction`: `S`
  - `reason`: `selected_equal_grid_slot`
  - `selected_slot`: `0`
  - `corner_alpha`: `[0,0,0,0]`
  - `green_pixels`: `0`
- Visual check: front-facing, transparent background, keeps the goblin miner identity.

## Remaining caveat
The model can still draw a poor internal sheet in some attempts, but the browser will now receive the cropped target slot with transparent background and QA instead of showing the whole green sheet directly.
