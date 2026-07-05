# Phase 7-A Report — Undo/Redo + Canvas Navigation

## Verdict
Phase 7-A 완료: 히스토리/Undo-Redo 경로와 캔버스 줌/팬 조작감을 정리했습니다.

## Applied
- Undo/Redo를 `undoHistory()` / `redoHistory()`로 분리하고 버튼/단축키가 같은 경로를 쓰도록 정리.
- 히스토리/프로젝트 저장 serialization을 `SERIALIZED_PROPS`로 통일하고 `excludeFromExport` 보존을 명시.
- Mask anchor / Clear mask / Invert mask history label 추가.
- Zoom helper `zoomBy()` 추가, 상단 +/-와 wheel zoom을 같은 배율 로직으로 통일.
- Space 임시 Pan이 이전 도구로 정확히 복귀하도록 `temporaryPanPreviousTool` 추가.
- Middle mouse pan 지원 및 panning CSS 상태 추가.
- Tool shortcut 추가: `V` 선택, `C` 크롭, `B` 브러시/펜슬 토글, `E` 지우개, `M` 마스크, `T` 텍스트, `R` 도형.
- Crop 도구에서 마스크/도형처럼 캔버스 드래그로 크롭 영역을 지정하고 좌표 입력칸에 반영.
- cache bust를 `phase7a-crop-select`로 갱신.

## Verification
자동 검증:
```bash
node --check src/main.js
python3 -m pytest -q
git diff --check
```
결과:
- `19 passed`
- JS syntax OK
- diff whitespace OK

브라우저 검증:
- `http://127.0.0.1:4184/?v=phase7a-crop-select` 로드 성공.
- 외부 URL `https://attempt-promotions-platform-purchases.trycloudflare.com/?v=phase7a-crop-select` 로드 성공.
- Text 추가 후 `undoHistory()` → object 수 2→1, Redo 활성화 확인.
- `redoHistory()` → object 수 1→2, Undo 활성화 확인.
- `zoomBy(1.12)` → zoom label 46%→51% 확인.
- Brush 도구 상태에서 임시 Pan 시작/종료 → `brush → pan → brush` 복귀 확인.
- 단축키 경로 확인: `C→crop`, `V→select`, `B→brush→pencil`, `E→eraser`, `M→mask`, `T→text`, `R→shape`.
- Crop 드래그 선택 확인: preview 생성, 좌표 입력 `x/y/w/h` 갱신, crop mode에서 object selection 비활성 확인.
- 콘솔 JS 에러 없음.

## Notes / Known Limits
- 실제 키보드 입력 경로는 코드/정적 검증 기준으로 확인했고, 브라우저 툴에서는 함수 호출로 Undo/Redo 상태 변화를 검증했습니다.
- 다음 UX polish에서는 alert/toast 정리와 우측 패널 접기 구조를 진행하는 것이 좋습니다.
