# Phase 13 Report — Pixel Asset Generator

## Scope
- General Photoshop-like expansion was stopped.
- Added a dedicated pixel-art/game-asset generation workflow for idle/walking/UI/icon style assets.

## Implemented
- `Pixel Asset Generator` panel under AI tool.
- Asset Type selector:
  - Character
  - Monster
  - Item
  - UI Panel
  - Button
  - Icon
  - Tile
- Animation Preset selector:
  - idle
  - walking 4-frame
  - walking 6-frame
  - attack
  - hurt
  - UI static
- Style Preset selector:
  - 32-bit refined pixel
  - 16-bit RPG
  - Dark fantasy
  - Kairosoft-like
  - Horror game asset
  - Dungeon UI
- Direction and palette inputs.
- Subject input.
- `프롬프트 조립` button.
- `도트 에셋 생성` button routed through the existing real `/api/generate` flow.
- Result slot area for generated pixel assets.

## Prompt Builder Rules
- Animated presets produce sprite-sheet wording.
- Idle/walk prompts specify frame counts and evenly spaced sprite sheet cells.
- Walk prompts explicitly request real alternating legs and arms.
- UI preset produces static reusable UI game asset wording.
- Prompt enforces:
  - refined pixel art, not chunky NES
  - transparent background
  - clean alpha edges
  - no text / no watermark / no logo

## Verification
- Added static regression tests: `tests/test_phase13_pixel_asset_generator_static.py`
- RED confirmed before implementation: 3 failed.
- After implementation:
  - `pytest tests/ -q` → 87 passed
  - `node --check src/main.js` → pass
  - `python3 -m py_compile server.py` → pass
  - `git diff --check` → pass
- Browser verification:
  - Opened `http://127.0.0.1:4184/?v=phase13-pixel-generator`
  - AI tool shows `Pixel Asset Generator`
  - Subject input tested with `tiny dungeon cleaner goblin with mop, readable 32-bit sprite`
  - `프롬프트 조립` fills the real `aiPrompt`
  - `aiPreset` becomes `pixel`
  - `aiAspect` remains `square`
  - Console JS errors: 0

## Next Phase
Phase 14 should be animation preview/export:
- Detect generated sprite-sheet cells or use grid values.
- Preview idle/walk frames as looping animation.
- FPS control.
- ping-pong / loop toggle.
- Export GIF/WebP or frame ZIP.
