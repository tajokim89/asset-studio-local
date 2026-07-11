# Phase 7B Report — Layer Panel UX

## Scope
- Clean up layer panel controls after Phase 7A.
- Make visibility and lock states explicit and clickable.
- Add direct layer actions: duplicate, merge down, delete.
- Prevent hidden/locked layers from being selected/edited accidentally.

## Changes
- Layer rows now have a two-line layout:
  - main row: icon, layer name, state badges
  - action row: Rename, Up, Down, Hide/Show, Lock/Unlock, Dup, Merge↓, Del
- Visibility button now changes label and state:
  - visible: `Hide`
  - hidden: `Show` + `Hidden` badge + dim/dashed row
- Lock button now changes label and state:
  - unlocked: `Lock`
  - locked: `Unlock` + `Locked` badge
- Added layer action helpers:
  - `toggleLayerVisibility`
  - `setLayerLocked`
  - `deleteLogicalLayer`
  - `duplicateLogicalLayer`
  - `mergeLayerDown`
  - `handleLayerAction`
- Hidden/locked regular layers are not selectable/evented on canvas.
- Locked layer actions guard destructive/editing operations.
- Added focused static regression tests for Phase 7B.
- Updated cache-busting asset versions to `phase7b-layer-ux`.

## Verification
- `node --check src/main.js` — passed
- `pytest -q` — 24 passed
- `git diff --check` — passed
- Browser external URL loaded successfully:
  - https://attempt-promotions-platform-purchases.trycloudflare.com/?v=phase7b-layer-ux
- Browser runtime checks:
  - Hide on normal layer sets `visible=false` and `selectable=false`.
  - Hidden row shows `Hidden` badge and `Show` button.
  - Lock on normal layer sets `locked=true` and `selectable=false`.
  - Locked row shows `Locked` badge and `Unlock` button.
  - Duplicate creates `Layer B copy`.
  - Merge down creates grouped layer `Layer B + Layer B copy`.
  - Delete removes merged group.
  - Console JS errors: 0.

## Notes
- Merge down currently uses Fabric group merge for normal/image/vector layers.
- Drawing Layer merge is intentionally blocked for now because strokes are logical members and need a separate flattening path.
- No commit or push performed in this phase slice.
