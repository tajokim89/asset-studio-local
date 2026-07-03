# Asset Studio Phase 2 Report

## Phase 2 Goal

Add real one-click background removal while preserving the original image layer.

## Implemented

- Added `Remove BG` primary button to the Background panel.
- Added backend endpoint:

```text
POST /api/remove-bg
```

- Endpoint accepts a selected image as a data URL.
- Uses `rembg` when available.
- Includes a conservative PIL corner-flood fallback if rembg fails.
- Saves processed transparent PNG files under:

```text
assets/processed/
```

- Frontend behavior:
  - selected image is sent to `/api/remove-bg`
  - result is added as a new `Cutout - <original name>` image layer
  - original image layer is preserved and hidden
  - canvas background is set to transparent
  - checkerboard remains visible for transparency inspection
  - cutout is selected after completion
  - cutout is added to the gallery

## Dependencies

Added:

```text
requirements.txt
```

with:

```text
pillow
numpy
rembg[cpu]
```

Local venv was prepared with `rembg[cpu]` and `onnxruntime`.

## Verified

External URL checked:

```text
https://troubleshooting-floors-strongly-remembered.trycloudflare.com/?v=phase2-remove-bg
```

Backend API test:

- Synthetic 256×256 PNG
- White background
- Blue circle subject
- `/api/remove-bg` returned success
- method: `rembg`
- output corner alpha: `0`
- subject center alpha: `255`

Browser UI test:

- Added a synthetic image to the canvas.
- Ran `Remove BG` through frontend function.
- Layers after operation:
  - `Drawing Layer 1` visible
  - original `Test Circle` hidden
  - `Cutout - Test Circle` visible and selected
- Canvas background: transparent/null
- Checkerboard: enabled
- Cutout image alpha check:
  - corner alpha: `0`
  - center alpha: `255`
- Console JS errors: none

## Notes

Phase 2 intentionally does not include full restore-brush/mask editing. Manual cutout repair belongs in Phase 3 with the mask/selection system.
