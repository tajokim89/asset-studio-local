# Phase 4 Report — Selected-area AI Inpaint + Apply UX

## Verdict
Phase 4 is now complete locally: selected-area AI edit is wired, previewed, and can be applied as either a new patch layer or a replacement image layer while preserving the original.

## Applied
- `/api/inpaint` is implemented and uses the Codex/OpenAI image-generation edit path.
- The server crops the selected mask area, sends original crop + black/white mask + prompt/negative prompt, then composites the AI result through the mask.
- Results are saved as transparent patch PNGs under `assets/processed/inpaint_patch_*.png`.
- Frontend direct inpaint now creates a preview state first instead of immediately modifying the canvas.
- Added AI result preview panel with:
  - `새 레이어 적용`
  - `선택 이미지 교체`
  - `다시 생성`
  - `취소`
- `새 레이어 적용` adds the transparent AI patch as an editable layer.
- `선택 이미지 교체` creates a replacement image layer and hides/preserves the original image layer.
- AI result layer names are auto-generated as `AI Edit - <prompt> ...`.
- Applied results call `saveHistory()`, so Undo/Redo sees the canvas change.
- Frontend assets cache-busted to `phase4-complete`.

## Verification
- `python3 -m py_compile server.py` passed.
- `node --check src/main.js` passed.
- `git diff --check` passed.
- Local app loaded: `http://127.0.0.1:4184/?v=phase4-complete-verify`.
- Browser confirmed cache-busted assets:
  - `styles/app.css?v=phase4-complete`
  - `src/main.js?v=phase4-complete`
- Browser console JS errors: 0.
- UI elements exist:
  - `inpaintPreviewPanel`
  - `applyInpaintNewLayer`
  - `applyInpaintReplace`
  - `retryInpaint`
  - `cancelInpaint`
- Non-AI smoke test using existing `inpaint_patch_*.png` verified:
  - new patch layer apply works
  - replacement apply creates replacement layer
  - original image layer becomes hidden/preserved
  - pending preview state clears after apply
- Existing processed patch PNGs have real alpha, e.g. alpha range `(0, 255)`.

## Notes
- This is completed locally and not yet committed/pushed in this phase.
- High-quality model run was not repeated; current runtime remains `gpt-image-2-low` for smoke speed.
