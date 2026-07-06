# Phase 12B Report — Sprite Batch ZIP Export

## Scope
- Add one-click batch export for all detected sprite slices.
- Package all slices into a browser-generated ZIP.
- Include `manifest.json` with bbox/size/area metadata.

## Changes
- Cache bust label: `phase12b-sprite-batch-zip`.
- Sprite Sheet Extraction panel:
  - Added `전체 조각 ZIP` button (`#exportAllSpritesZip`).
- Added browser-side ZIP builder without external dependency:
  - `buildStoredZip()` creates a valid stored/no-compression ZIP.
  - `crc32Bytes()` calculates per-file CRC32.
  - `downloadBlob()` downloads `sprite-slices.zip`.
- Added batch export flow:
  - `exportAllSpriteSlicesZip()` auto-runs detection if no slices exist.
  - Exports files as `sprite-001.png`, `sprite-002.png`, ...
  - Adds `manifest.json` with source layer, count, and slice metadata.

## Verification
- Static/full tests:
  - `pytest -q`: 82 passed.
  - `node --check src/main.js`: pass.
  - `python3 -m py_compile server.py`: pass.
  - `git diff --check`: pass.
- Browser UI verification:
  - URL: `https://later-work-totally-occurrence.trycloudflare.com/?v=phase12b-sprite-batch-zip`
  - `전체 조각 ZIP` button visible.
  - Uploaded deterministic transparent sprite fixture through `#topPhotoInput`.
  - Clicked real UI buttons:
    - `조각 탐지`
    - `전체 조각 ZIP`
  - UI summary: `전체 조각 ZIP 내보내기 · 3개 + manifest.json`.
  - Captured web UI ZIP download: `/Users/tajokim/.hermes/media_cache/phase12b_web_zip/web-downloaded-sprite-slices.zip`.
  - Console JS errors: 0.
- ZIP content verification:
  - `sprite-001.png`: 32×48, corner alpha `[0,0,0,0]`
  - `sprite-002.png`: 28×24, corner alpha `[0,0,0,0]`
  - `sprite-003.png`: 27×40, corner alpha `[0,0,0,0]`
  - `manifest.json`: count 3.

## Not Done
- Grid slicing mode is not implemented yet.
- ZIP filename customization is not implemented yet.
- Empty-cell filtering for grid sheets is not implemented yet.

## Next candidate
- Phase 12C: Grid Slice mode.
  - rows/cols/cell size/gap/padding controls.
  - preview grid overlay.
  - export grid cells as ZIP with optional empty-cell skip.
