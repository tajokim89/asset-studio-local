# Phase 12 Report — Sprite Sheet Extraction

## Scope
- 투명 배경/누끼 처리된 이미지 레이어에서 떨어진 조각을 자동 탐지.
- 탐지 bbox를 캔버스 위 가이드로 표시.
- 선택 조각을 새 레이어 또는 투명 PNG로 추출.

## Changes
- cache bust label: `phase12-sprite-extract`.
- Right panel에 `스프라이트 시트 추출` 섹션 추가:
  - 최소 조각 면적 입력.
  - `조각 탐지`.
  - `박스 지우기`.
  - `선택 조각 레이어`.
  - `선택 조각 PNG`.
  - 상태 요약.
- Alpha connected-component detector 추가:
  - `extractImageDataComponents()`.
  - alpha > 12 픽셀을 4-neighbor flood fill로 탐지.
  - `minArea` 이하 노이즈 제외.
  - 위→아래, 좌→우 정렬.
- Sprite guide overlay 추가:
  - `maskRole: 'sprite-guide'`.
  - `excludeFromLayers: true`.
  - `excludeFromExport: true`.
  - 선택 조각은 초록 stroke, 나머지는 주황 dash.
- 추출 동작:
  - 선택 이미지 레이어만 대상으로 함.
  - 선택 조각 bbox를 투명 PNG dataURL로 crop.
  - 새 레이어 추가 시 원래 bbox 위치에 1:1 배치.
  - PNG 내보내기 파일명: `sprite-slice-XX.png`.

## Verification
- Verified external URL:
  - `https://later-work-totally-occurrence.trycloudflare.com/?v=phase12-sprite-extract`
  - page title: `Pixel Asset Studio`.
  - `스프라이트 시트 추출` UI visible.
- Static/full tests:
  - `pytest -q`: 80 passed.
  - `node --check src/main.js`: pass.
  - `python3 -m py_compile server.py`: pass.
  - `git diff --check`: pass.
- Browser smoke test on local URL:
  - Created transparent fixture image with 3 separated colored blocks.
  - Added it as an image layer.
  - Ran `detectSpriteSlices()`.
  - Detected slices: 3.
  - Guide boxes: 3.
  - Extracted first selected slice as new layer.
  - Extracted PNG dimensions: 28×24.
  - Layer names include: `Drawing Layer 1`, `Phase12 sprite sheet`, `Sprite Slice 1`.

## Not Done
- Grid-based slicing mode is not implemented yet.
- Batch export all slices as ZIP is not implemented yet.
- Non-transparent/dirty-background sheets still need background removal first.

## Next candidate
- Phase 12B: grid slicing + batch export.
  - fixed grid rows/cols/cell size.
  - export all detected slices.
  - ZIP download or project asset tray.
