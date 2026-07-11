# Phase 7C Report — Selected-layer-only background removal fix

## Issue
- `AI 배경 제거` / `에셋 시트 배경 제거`는 선택된 이미지 레이어만 처리해야 한다.
- 기존 코드에서 처리 대상 이미지는 선택 레이어에서 가져오고 있었지만, 결과 적용 시 전역 캔버스 배경을 `null`로 바꾸고 checker를 켜서 전체 캔버스가 바뀐 것처럼 보이는 부작용이 있었다.

## Fix
- `removeBgSelected(mode)`에서 `/api/remove-bg` 입력은 계속 `imageObjectToDataUrl(obj)`로 선택 이미지 원본만 전달.
- 결과 cutout은 선택 레이어 바로 위에 새 레이어로 삽입.
- 원본 선택 레이어만 숨김 처리.
- 다른 레이어 visibility/geometry 유지.
- 전역 `canvas.backgroundColor = null` 제거.
- 전역 checker 자동 활성화 제거.
- data URL 응답에는 cache-bust query를 붙이지 않도록 보정.

## Regression tests
- Added `tests/test_remove_bg_selected_layer_static.py`.
- Checks:
  - selected-layer source only: `imageObjectToDataUrl(obj)`.
  - no `canvas.toDataURL` full-canvas export inside `removeBgSelected`.
  - no global canvas background/checker mutation.
  - cutout keeps target transform and inserts above selected layer.

## Verification
- `node --check src/main.js` passed.
- `pytest -q` passed: 27 tests.
- `git diff --check` passed.
- Browser verification with deterministic fixture:
  - target layer before bounds: left 190.86, top 220, width 128.25, height 89.07.
  - cutout after bounds: left 190.86, top 220, width 128.25, height 89.07.
  - canvas background stayed `#ffffff`.
  - checker stayed `false`.
  - non-target layer stayed visible.
  - original selected layer became hidden.
  - new cutout layer became active.
  - console JS errors: 0.

## External verification URL
- https://attempt-promotions-platform-purchases.trycloudflare.com/?v=phase7c-selected-bg-remove-2
