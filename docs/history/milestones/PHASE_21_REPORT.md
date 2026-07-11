# Phase 21 Report — Sprite Action Matrix + Prompt Templates

## Scope

Phase 21 locks the sprite-production contract before expanding into action sheets.

Implemented:

- Canonical 8-direction order: `N, NE, E, SE, S, SW, W, NW`
- Source-only direction set: `S, N, W, SW, NW`
- Right-facing mirror map: `E <- W`, `SE <- SW`, `NE <- NW`
- Static direction reference prompt template
- Action prompt template
- Fixed action matrix:
  - `idle`: 1 frame, `idle`
  - `walk`: 4 frames, `idle, stepA, idle, stepB`
  - `attack`: 4 frames, `ready, windup, strike, recover`
  - `hit`: 2 frames, `normal, recoil`
  - `death`: 6 frames, `alive, collapse1, collapse2, down, settle, dead`
- Existing 8-dir generation now uses the shared source-direction contract instead of duplicating local prompt text.
- Existing reference prompt generation now supports the fixed matrix for `idle/walk/attack/hit/death` contracts.

## Key Decision

Do not ask the model to create clean right-facing directions independently.

Generate only:

```txt
S, N, W, SW, NW
```

Then derive:

```txt
E  = flip(W)
SE = flip(SW)
NE = flip(NW)
```

This keeps mirror pairs mechanically identical and reduces final sprite-set QA failures.

## Files Changed

- `server.py`
  - Added `CANONICAL_8DIR_ORDER`
  - Added `MIRRORED_8DIR_SOURCE_DIRECTIONS`
  - Added `SPRITE_MIRROR_MAP`
  - Added `DIRECTION_PROMPT_CONTRACTS`
  - Added `SPRITE_ACTION_MATRIX`
  - Added `sprite_action_matrix_for_ui()`
  - Added `build_static_direction_reference_prompt()`
  - Added `build_sprite_action_prompt()`
  - Updated reference prompt action contracts
  - Updated 8-dir mirror generation to use the shared source-direction template
- `tests/test_phase21_sprite_action_matrix.py`
  - Added regression tests for direction source policy, action matrix, action prompt, and UI payload shape.

- Direction/action generation contract tightened after user correction: **directions are generated one-by-one only**. Walk/attack/idle/etc. may have multiple frames, but only for one selected direction per request. Templates explicitly forbid all-8-direction sheets/contact sheets for direction source generation and action generation.
- Follow-up correction: the old `single` path still asked for an internal multi-candidate extraction sheet and cropped a selected slot. That is now removed. `single` mode requests exactly one target direction, and postprocess trims/preserves the result without slot-picking.

## Verification

RED:

```txt
pytest tests/test_phase21_sprite_action_matrix.py -q
ImportError: cannot import name 'CANONICAL_8DIR_ORDER'
```

GREEN / regression:

```txt
pytest tests/test_phase21_sprite_action_matrix.py -q
4 passed
```

Phase 21 subset:

```txt
pytest tests/test_phase21_*.py -q
9 passed
```

Full suite:

```txt
pytest -q
128 passed, 9 warnings
```

Syntax / whitespace:

```txt
python3 -m py_compile server.py
git diff --check
```

Passed.

## Remaining Caveat

This phase fixes the production contract and prompt/action matrix. It does not yet guarantee a visually accepted final sprite image. The next hardening step is candidate-pool + pivot-normalized action sheet generation per accepted static direction.
