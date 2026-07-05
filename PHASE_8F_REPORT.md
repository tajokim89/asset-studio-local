# Phase 8F Report — Selection UX polish

## Scope
- 선택영역 해제 UX
- 선택영역 오버레이 이동/크기조절
- 선택영역이 이미지 레이어 선택 상태를 뺏지 않도록 보호
- Ctrl+V 반복 붙여넣기 offset 및 새 레이어 active selection

## Changes
- `Esc`로 현재 선택영역/미리보기 제거.
- 영역 선택 도구에서 사각/원형/올가미 선택 오버레이를 직접 선택, 이동, 크기조절 가능하게 변경.
- 마스크/선택 오버레이는 Layers 패널에 표시하지 않고, active object가 되어도 `selectedLayerId`를 오염시키지 않도록 수정.
- 선택영역 이동/리사이즈 후 mask region bounds를 갱신.
- `Ctrl+V` 반복 시 12px씩 offset해서 붙여넣고, 새 이미지 레이어를 즉시 선택 상태로 유지.
- cache bust label: `phase8f-selection-ux-polish`.

## Verification
- Static regression: `tests/test_phase8f_selection_ux_static.py` 추가.
- Runtime browser fixture:
  - 선택영역 오버레이 selectable/evented 확인.
  - 오버레이 active 상태에서도 원본 이미지 target 보존 확인.
  - 이동/리사이즈 후 bounds 갱신 확인.
  - 반복 paste offset 확인.
  - paste 결과 레이어 active selection 확인.
  - clear 후 positive selection overlay 0개 확인.
- Console JS errors: 0.
- `node --check src/main.js`: pass.
- `pytest -q`: 44 passed.
- `git diff --check`: pass.

## External URL
https://acdbentity-celebrities-rna-nextel.trycloudflare.com/?v=phase8f-selection-ux-polish
