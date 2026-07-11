# Phase 7D Report — Layer eye toggle + selected-layer merge

## Change
- Layer visibility button now uses eye icons instead of `Hide` / `Show` text.
  - Visible: `👁️`
  - Hidden: `👁️‍🗨️`
  - Keeps `aria-label` / `aria-pressed` for accessibility.
- Merge no longer means “merge down”.
- Merge now requires 2+ selected mergeable layers.
- Layer panel supports multi-select with `Shift` / `Cmd` / `Ctrl` click.
- If only one layer is selected and Merge is clicked, it refuses with guidance instead of merging with the layer below.

## Behavior
- Click eye icon: toggles visible/hidden.
- Shift/Cmd/Ctrl-click layer rows: builds multi-selection.
- Click `Merge`: groups/merges the currently selected layers only.
- Drawing layers, hidden layers, and locked layers are excluded from merge selection.

## Regression tests
- Added `tests/test_layer_eye_merge_static.py`.
- Updated older layer action tests to match selected-layer merge.

## Verification
- `node --check src/main.js` passed.
- `pytest -q` passed: 30 tests.
- `git diff --check` passed.
- Browser verification:
  - Eye button visible state: `👁️`, `aria-pressed=true`.
  - After click: target layer hidden, active selection cleared, icon becomes `👁️‍🗨️`, label `Show layer`.
  - Single selected layer + Merge: object count unchanged, status says two or more layers are required.
  - Ctrl-click two layers: active selection contains `Red`, `Blue`.
  - Merge after multi-select: active object becomes group `Red + Blue`; object list becomes `Drawing Layer 1`, `Red + Blue`.
  - Console JS errors: 0.

## External verification URL
- https://attempt-promotions-platform-purchases.trycloudflare.com/?v=phase7d-layer-eye-merge-selected
