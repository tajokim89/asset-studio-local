# Eraser Layer Behavior Fix

## Root Cause

Freehand eraser strokes were implemented as Fabric paths with:

```js
globalCompositeOperation = 'destination-out'
```

That composite mode is applied at canvas render time, so the stroke could punch through the rendered canvas/background instead of only editing the selected image layer.

The visible `Drawing Layer` wording also made the UX feel like brush/eraser were separate from the image being edited.

## Fix

- Freehand eraser no longer leaves a `destination-out` stroke on the canvas.
- Eraser path is converted into a temporary mask PNG.
- The mask is applied to the currently selected image layer only.
- Result replaces that image layer as a transparent PNG layer.
- Canvas background remains unchanged.
- If no image layer is selected, eraser stops with a clear status message.
- Layer add button copy changed from `+ 드로잉 레이어` to `+ 일반 레이어`.
- Eraser panel copy now explains: selected image pixels are made transparent.

## Verification

```bash
node --check src/main.js
python3 -m pytest -q
```

Result:
- `12 passed`
- JS syntax OK
- browser runtime check: erase mask applied to selected image, background stayed `#ffffff`, history label `Freehand erase`, no console JS errors.
