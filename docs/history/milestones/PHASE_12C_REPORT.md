# Phase 12C Report — Grid Slice Export

## Scope
- Add grid-based slicing for uniform sprite sheets.
- Preview grid slice boxes on the canvas.
- Export all grid cells as a ZIP with metadata.

## Changes
- Cache bust label: `phase12c-grid-slice`.
- Sprite Sheet Extraction panel now includes `그리드 슬라이스` controls:
  - `gridCols` / `gridRows`
  - `gridCellW` / `gridCellH`
  - `gridGapX` / `gridGapY`
  - `그리드 미리보기`
  - `그리드 ZIP`
- Added grid slice logic:
  - `buildGridSpriteSlices()` builds row/col slices from the selected image layer origin.
  - `detectGridSpriteSlices()` previews grid boxes using the existing sprite guide overlay.
  - `exportGridSpriteSlicesZip()` exports all cells as `grid-sprite-001.png`, ... plus `grid-manifest.json`.

## Verification
- Committed/pushed Phase 12B before starting Phase 12C:
  - Commit: `cb20441` / `Phase 12B sprite batch zip export`
- Static/full tests:
  - `pytest -q`: 84 passed.
  - `node --check src/main.js`: pass.
  - `python3 -m py_compile server.py`: pass.
  - `git diff --check`: pass.
- Browser UI verification:
  - URL: `https://later-work-totally-occurrence.trycloudflare.com/?v=phase12c-grid-slice`
  - `그리드 슬라이스` UI visible.
  - Uploaded deterministic 64×32 transparent grid fixture.
  - Set grid values: cols 4, rows 2, cell 16×16, gap 0×0.
  - Clicked real UI buttons:
    - `그리드 미리보기`
    - `그리드 ZIP`
  - UI summary: `그리드 ZIP 내보내기 · 8개 + grid-manifest.json`.
  - Captured web UI ZIP download: `/Users/tajokim/.hermes/media_cache/phase12c_grid_zip/web-downloaded-grid-sprite-slices.zip`.
  - Console JS errors: 0.
- ZIP content verification:
  - 8 PNG files + `grid-manifest.json`.
  - Manifest: cols 4, rows 2, cell 16×16, count 8.
  - All PNG dimensions: 16×16.
  - Sample corner alpha: `[0,0,0,0]`.

## Not Done
- Empty-cell skipping is not implemented yet.
- Padding/start offset controls are not implemented yet.
- ZIP filename customization is not implemented yet.

## Next candidate
- Phase 12D: grid quality-of-life controls.
  - Start X/Y padding.
  - Skip empty cells.
  - Filename prefix.
  - Optional row/col subfolders.
