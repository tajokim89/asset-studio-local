# Phase 3A Report — Rectangular Mask Selection

## Scope

Phase 3A implemented the first usable selection/mask foundation for later AI inpainting.

This phase deliberately does **not** implement AI regeneration yet. It only creates, displays, clears, and exports mask regions.

## Implemented

- `Mask` tool panel is now active, not a placeholder.
- Dragging on the canvas in Mask mode creates a red translucent rectangular mask overlay.
- Mask overlays are excluded from the normal Layers panel.
- Mask overlays are excluded from normal full-canvas PNG export.
- Right-side AI Edit panel now shows whether a mask is ready for Phase 4.
- `Clear Mask` removes all mask overlays.
- `Invert` provides a Phase 3A visual inverse preview.
- `Export Mask PNG` exports a black/white mask image:
  - white = selected/edit area
  - black = protected area
- Project JSON/history now preserves mask metadata fields:
  - `isMaskOverlay`
  - `maskRegionId`
  - `maskRole`
  - `targetLayerId`

## Verification

Verified locally on:

- `http://127.0.0.1:4184/?v=phase3a-mask-rect`

Verified external tunnel:

- `https://clusters-preliminary-premiere-essay.trycloudflare.com/?v=phase3a-mask-rect`

Checks performed:

- Page loads with `v0.3 mask base` badge.
- Mask tool opens the new Mask / Selection panel.
- Simulated canvas drag creates one `Mask Rectangle` overlay.
- UI updates to `Mask regions: 1`.
- AI Edit summary updates to `1 mask region(s) ready for Phase 4 inpaint.`
- Mask overlay does not appear as a normal layer row; Layers panel still only shows `Drawing Layer 1` in a fresh document.
- `Clear Mask` returns mask count to `0`.
- Browser console errors: `0`.
- JS syntax check: `node --check src/main.js` passes.

## Not Done Yet

Reserved for later phases:

- Brush/lasso mask painting.
- True pixel mask editing with restore/erase brush.
- Sending image + mask + prompt to `/api/inpaint`.
- AI preview / apply / retry flow.

## Next Recommended Step

Phase 3B should add brush-based mask painting and mask erasing, because rectangular selection alone is too coarse for real object-part editing.
