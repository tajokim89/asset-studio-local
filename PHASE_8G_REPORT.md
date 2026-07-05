# Phase 8G Report — Region action polish

## Scope
- 영역 선택 패널 액션 UX 정리
- `선택영역 PNG`가 마스크 PNG가 아니라 실제 선택 이미지 crop PNG를 내보내도록 수정
- 키보드 `Ctrl/Cmd+V`만 있던 붙여넣기를 버튼으로 노출
- `선택영역 지우기`의 의미를 전체 마스크 삭제가 아닌 선택 오버레이 해제로 정리

## Changes
- cache bust label: `phase8g-region-action-polish`.
- 영역 패널 버튼 구성 변경:
  - `선택영역 복사`
  - `선택영역 잘라내기`
  - `선택영역 붙여넣기`
  - `선택영역 PNG`
  - `선택 해제`
- `pasteRegionSelection` 버튼 추가: 내부 region clipboard를 새 이미지 레이어로 붙여넣음.
- `exportRegionSelectionPng()` 추가:
  - 선택 이미지 레이어 + 현재 영역 마스크를 사용.
  - 투명 배경의 선택영역 crop PNG를 다운로드.
  - 파일명: `asset-studio-region-selection.png`.
- `clearRegionSelectionOnly()` 추가:
  - 사각/원형/올가미 선택 오버레이만 해제.
  - 손/앞가림 occlusion mask 등 다른 mask overlay는 유지.
  - 전체 mask clear history를 만들지 않음.

## Verification
- RED static regression: `tests/test_phase8g_region_actions_static.py`가 구현 전 4 failures 확인.
- Static/full tests:
  - `node --check src/main.js`: pass.
  - `pytest -q`: 48 passed.
  - `git diff --check`: pass.
- Browser verification on external URL:
  - 영역 툴 패널에서 `선택영역 붙여넣기`, `선택 해제`, `선택영역 PNG` 표시 확인.
  - runtime fixture:
    - `exportRegionSelectionPng()` 다운로드 파일명 `asset-studio-region-selection.png` 확인.
    - PNG data URL 확인.
    - export 후 selection overlay 보존 확인.
    - copy 후 selection overlay clear 확인.
    - paste 1/2회 모두 즉시 active object가 됨.
    - 반복 paste offset `[12, 12]` 확인.
    - `clearRegionSelectionOnly()`는 positive selection overlay만 제거하고 occlusion mask는 유지 확인.
  - Console JS errors: 0.

## External URL
https://moral-suse-wine-varieties.trycloudflare.com/?v=phase8g-region-action-polish
