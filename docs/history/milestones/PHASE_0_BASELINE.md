# Asset Studio Phase 0 Baseline

## Goal

Phase 0 is not feature development. It freezes the current state, clarifies the product direction, and defines the gate for Phase 1.

## Product Direction

Asset Studio is a general AI-assisted image editing tool, not a game-themed generator.

Core requirements:

1. Standard image-editor tools that users reasonably expect.
2. One-click background removal to transparent PNG.
3. Select a specific area and ask AI to redraw/regenerate only that area.
4. AI chat/workflow assistant for editing commands.

## Current Project

Path:

```text
/Users/tajokim/asset-studio-local
```

Files:

```text
index.html
src/main.js
styles/app.css
server.py
```

Current local server:

```text
http://127.0.0.1:4184
```

## Current Implemented Baseline

The current prototype already contains early versions of:

- Fabric.js canvas
- Canvas size presets
- Image upload
- Sample gallery
- Text layer
- Shape layer
- Layer list
- Transform controls
- Full PNG export
- Selected PNG export
- Project JSON save/load
- Color-based background removal: white/black
- AI generation API scaffold
- Draw tab scaffold with pencil/brush/eraser controls

## Known Gaps

The current prototype is not yet a proper editor base. Missing or incomplete:

- Clean tool-mode architecture
- Proper left vertical toolbar
- Pan/zoom workflow
- Crop tool
- True eraser/mask model with restore brush
- Checkerboard transparency view
- Click-color removal
- Automatic background removal API
- Area selection/mask system for AI inpaint
- AI inpaint endpoint
- AI chat command workflow
- Robust undo/redo QA
- Proper layer lock/hide UX
- Text effects completeness
- Adjustment tools: brightness/contrast/saturation/blur

## Phase 1 Recommendation

Phase 1 should be **Editor Base Rework**, not AI features yet.

Phase 1 scope:

- Restructure UI into real editor layout:
  - left vertical tool bar
  - central canvas workspace
  - right properties/layers/AI panels
- Define tool modes:
  - select/move
  - pan
  - crop
  - brush
  - pencil
  - eraser
  - text
  - shape
  - mask
- Add checkerboard transparency view.
- Stabilize brush/pencil/eraser as first-class tools.
- Improve zoom/pan.
- Keep existing upload/text/shape/layer/export features working.

## Phase Gate

Do not proceed to Phase 1 implementation until the user confirms this Phase 0 baseline.

After Phase 1 is implemented, stop again for user verification before Phase 2.
