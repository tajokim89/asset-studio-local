# Phase 16 Report — Page-native Reference Pixel Asset Pack Generation

## Scope
Fix the pixel workflow so idle/walking/UI outputs are generated inside the page from a selected reference image/layer, not as external/manual artifacts and not as blind text-only generation.

## Implemented
- Added `선택 이미지/레이어를 기준 이미지로 사용` checkbox, default ON.
- `생성→정리→미리보기` now works as:
  1. selected image layer = reference image
  2. send prompt + reference image to `/api/generate-reference`
  3. create generated sprite-sheet image layer
  4. optional sheet background cleanup
  5. grid slice
  6. animation preview
- `idle / walking / UI 샘플팩 생성` now keeps the originally selected image layer as the reference for every pack job.
  - It does not accidentally use the previous generated result as the next reference.
- Added backend `/api/generate-reference` endpoint.
  - Sends `input_image` reference to Codex image generation.
  - Prompt contract preserves identity/style/palette/outline/pixel scale.
  - Requests chroma-green background for cleanup.
- Fixed `removeBgSelected()` to return a real Promise result `{ url, cutout, data }` after the cutout image layer is loaded.
- Fixed data URL cache-busting bug.

## Verification
- Static regression tests:
  - `tests/test_phase16_page_asset_pack_static.py`
  - `tests/test_phase16_reference_generation_static.py`
- Commands:
  - `pytest tests/test_phase16_page_asset_pack_static.py tests/test_phase16_reference_generation_static.py -q` → 7 passed
  - `node --check src/main.js` → pass
  - `python3 -m py_compile server.py` → pass
  - `git diff --check` → pass
- Browser verification on external URL:
  - `https://two-satisfy-basket-upc.trycloudflare.com/?v=phase16-reference-asset-pack`
  - Confirmed reference checkbox exists and is checked by default.
  - Ran mocked browser workflow with an actual in-canvas reference image layer selected.
  - Verified frontend called `/api/generate-reference`.
  - Verified request body included `reference_image: data:image/png...`.
  - Verified result layer was added, background cleanup ran, grid/preview completed.
  - Result slots showed:
    - `character · idle · reference-image-sprite-generation`
    - `character · idle · cleaned · mock_sheet_bg`
  - Status: `도트 워크플로우 완료 · 4 frames`

## Not Done
- Real paid AI reference-generation batch was not executed during verification; app-side browser path was mocked to avoid burning generation calls while validating the workflow wiring.
- Commit/push not done yet.
