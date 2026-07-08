# Phase 23 Report — Asset Type Smart Controls

## Scope
- Promptless directional/action generation UX cleanup.
- Show motion/direction controls only for `Character` and `Monster`.
- Static asset types (`Item`, `UI Panel`, `Button`, `Icon`, `Tile`) generate as one-frame static assets without requiring action/direction choices.
- Reduce duplicate generation buttons by moving batch/legacy directional actions under advanced/hidden controls.

## Applied
- Added asset-type gating in `src/main.js`:
  - `character`, `monster` => actor mode: motion, direction, reference direction, frame controls visible.
  - other asset types => static mode: motion/direction/reference/frame controls hidden, animation forced to `ui_static`, frames forced to `1`.
- Updated button labels dynamically:
  - actor mode: `새 캐릭터/몬스터 스프라이트 생성`, `선택 이미지 기준 방향/동작 생성`.
  - static mode: `아이템/UI/버튼/아이콘/타일 정적 에셋 생성`, `선택 이미지 스타일로 정적 에셋 생성`.
- Updated prompt construction so static assets explicitly request:
  - no animation,
  - no direction sheet,
  - no alternate poses,
  - single transparent PNG-style asset.
- Moved duplicate/advanced batch actions under `고급: 배치 생성` and hid old direct `8방향 Idle/Walk` row.
- Cache-busted script tag to `phase23-asset-type-smart-controls`.

## Verified
- `node --check src/main.js` passed.
- `git diff --check` passed.
- Browser loaded `http://127.0.0.1:4184/?v=phase23-asset-type-smart-controls`.
- Browser UI check:
  - Character/Monster show motion/direction controls and 4-frame actor defaults.
  - Item hides motion/direction/reference/frame controls, shows static notice, forces `ui_static`/1-frame workflow label.
  - Returning to Monster restores actor controls and default idle/4-frame state.
- Prompt check:
  - Item prompt contains `Static asset contract`, `no animation`, `no direction sheet`.
  - Character walk prompt still contains walk cycle and target direction.
- Browser console JS errors: 0.

## Not Done
- Did not run costly real AI generation in this pass.
- Did not commit/push yet; waiting for user confirmation after review.
