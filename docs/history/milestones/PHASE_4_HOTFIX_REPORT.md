# Phase 4 Hotfix Report — Patch-layer inpaint

## Problem from user test
- AI changed content outside the intended slime-liquid area, including the skeleton.
- The result was generated/inserted like a whole image instead of only the masked region.
- Rectangular mask produced an unwanted background/blocky patch.

## Applied
- Changed selected-area AI edit from full-canvas result insertion to **new transparent patch layer only**.
- Frontend now exports the source image with mask overlays hidden before calling `/api/inpaint`.
- `/api/inpaint` now crops to the mask bounding box with padding, sends only that crop + mask crop to the AI backend, then returns a transparent PNG patch.
- Patch PNG alpha is driven by the mask: outside the editable mask is transparent.
- Frontend places the returned patch at the server-returned bbox position.
- Removed the replace option from the UI; result mode is now always `새 패치 레이어로 추가`.
- Prompt guidance tightened: do not redesign skeleton/background/tile/whole crop; edit only white mask.
- Cache-busted assets to `phase4-patch-layer`.

## Verification
- `python3 -m py_compile server.py` passed.
- `node --check src/main.js` passed.
- `git diff --check` passed.
- Server restarted on `http://127.0.0.1:4184` with `OPENAI_IMAGE_MODEL=gpt-image-2-low`.
- Real `/api/inpaint` smoke test succeeded in 19.8s.
  - Output: `/Users/tajokim/asset-studio-local/assets/processed/inpaint_patch_1783131513_df8b3106.png`
  - bbox: `{x:441,y:441,width:144,height:144}`
  - method: `codex-crop-edit+transparent-mask-patch`
- Patch PNG alpha verification:
  - size: `144×144`
  - corner alpha: `[0,0,0,0]`
  - center alpha: `255`
- External link loaded with updated assets:
  - `https://rolled-anderson-stockholm-vintage.trycloudflare.com/?v=phase4-patch-layer-1`
- Browser UI smoke:
  - only one result mode: `새 패치 레이어로 추가`
  - prompt placeholder updated for slime-liquid use case
  - mask creation enables run button
  - console JS errors: 0

## Remaining caveat
- A rectangular mask still means the entire rectangle is editable. For “slime only”, brush mask/eraser should be used to cover only the slime pixels. The hotfix guarantees the result is a transparent patch layer and prevents whole-canvas replacement, but it cannot infer unmasked intent inside a too-large white mask.
