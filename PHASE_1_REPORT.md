# Asset Studio Phase 1 Report

## Phase 1 Goal

Rework the prototype into a clearer editor base before adding advanced AI features.

## Implemented

- Replaced horizontal tab UI with a left vertical tool rail.
- Added explicit tool modes:
  - Select
  - Pan
  - Crop scaffold
  - Brush
  - Pencil
  - Eraser
  - Mask scaffold
  - Text
  - Shape
  - Upload
  - AI
- Reorganized left sidebar into per-tool option panels.
- Left/right side panels are resizable with draggable handles; widths persist in localStorage.
- Reorganized right sidebar into:
  - Properties
  - Style/Text
  - Background
  - Canvas/Export
  - AI Edit scaffold
  - Layers
  - Shortcuts
- Added checkerboard canvas shell for transparent-background work.
- Added zoom controls with visible zoom percentage.
- Added pan mode scaffold using workspace drag/scroll.
- Preserved existing features:
  - image upload
  - gallery
  - text creation
  - shapes
  - transform properties
  - layers
  - color-based background removal
  - selected/full PNG export
  - project JSON save/load
  - AI generation endpoint/UI

## Fixes After User Verification

### Drawing stroke layer spam

User caught a critical UX issue: every brush/pencil/eraser stroke was appearing as its own layer.

Fix applied:

- Drawing strokes are still rendered on canvas.
- Drawing strokes are marked as internal drawing strokes.
- Drawing strokes are excluded from the Layers panel.
- Drawing strokes are not individually selectable.
- Real content layers such as image/text/shape still appear in Layers.
- Save/undo JSON preserves the drawing-stroke metadata.

### Initial layer, Add Layer, and layer ordering

User corrected that the editor should not start with 0 layers, should support adding layers, and should support changing layer order.

Fix applied:

- New documents now start with `Drawing Layer 1`.
- Layers panel has `+ Layer` and `+ Image` buttons.
- `+ Layer` creates a new drawing layer and makes it the active drawing target.
- Brush/pencil/eraser strokes are assigned to the active drawing layer.
- Strokes do not create extra layer rows.
- `+ Image` creates a placeholder blank image layer.
- Layer rows now include rename `✎`, `↑` / `↓` order controls and support drag-and-drop reordering.
- Layer names can be changed with the `✎` button or by double-clicking the layer name.
- Drawing layers move together with their internal strokes whether reordered by buttons or drag.
- Drawing layer metadata is preserved in save/undo JSON.

## Verified

External URL checked:

```text
https://troubleshooting-floors-strongly-remembered.trycloudflare.com/?v=phase1-resizable-panels-restore
```

Manual/browser checks:

- Page loads as `Asset Studio Local`.
- Left tool rail appears.
- Fresh document starts with 1 visible layer row.
- `+ Layer` increases visible layer rows from 1 to 2.
- Simulated drawing stroke after adding layer keeps visible layer rows at 2.
- `+ Image` adds a visible placeholder layer, rows become 3.
- Layer `↑` / `↓` changes logical layer order.
- Drag-and-drop layer rows change logical layer order.
- Layer names can be changed and persist in project JSON.
- Drawing/text/image-style layers can all be renamed.
- Left/right side panel widths can be changed and restored after reload.
- Drawing layer ordering preserves its internal brush stroke children.
- Browser console has no JS errors.

## Known Limitations

- Crop is only a scaffold in Phase 1.
- Mask is only a scaffold in Phase 1.
- Eraser is still path/composite based and needs proper mask/restore architecture later.
- Drawing layer is a logical layer with hidden stroke children; deeper per-layer editing/merge can be added later.
- Pan mode is workspace scroll based, not a full canvas viewport transform.
- Automatic one-click background removal is not Phase 1; it belongs to Phase 2.
- Selected-area AI inpainting is not Phase 1; it belongs to Phase 3/4.

## Phase Gate

Stop here until the user verifies Phase 1.

Recommended next phase:

```text
Phase 2: One-click transparent background removal + manual edge/mask correction foundation.
```
