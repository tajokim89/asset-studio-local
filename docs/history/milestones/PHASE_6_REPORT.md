# Phase 6 Report — Crop / Alpha Repair / Layer Controls

## Scope

Phase 6-A/B/C까지 한 번에 진행.

### Phase 6-A — Crop / Resize / Canvas Size
- Crop 툴 옵션 패널에 좌표 입력 추가: `cropX`, `cropY`, `cropW`, `cropH`
- 캔버스 크롭 버튼 추가
- 선택 이미지 크롭 버튼 추가
- 오브젝트 bbox 기준 캔버스 맞춤 버튼 추가

### Phase 6-B — Alpha Eraser / Restore Brush Foundation
- 지우개 패널에 마스크 기반 지우기/복원 버튼 추가
- 선택 이미지 + 현재 마스크로 alpha 제거
- 선택 이미지 원본 소스가 있는 경우 마스크 영역 원본 픽셀 복원
- 선택 이미지 전체 원본 복원 버튼 추가

### Phase 6-C — Layer Controls / Export
- 레이어 패널에 opacity 슬라이더 추가
- 선택 레이어 opacity 적용
- 다중 선택 그룹화
- 그룹 해제
- 활성 레이어 PNG export 버튼 추가

## TDD / Regression Tests

추가 파일:
- `tests/test_phase6_static.py`

검증한 정적 조건:
- Phase 6-A UI ID와 JS 함수 존재
- Phase 6-B UI ID와 JS 함수 존재
- Phase 6-C UI ID와 JS 함수/CSS class 존재
- 핵심 액션 history label 존재

## Verification

자동 검증:
```bash
node --check src/main.js
python3 -m pytest -q
```

결과:
- `10 passed`
- JS syntax OK
- `git diff --check` OK

브라우저 검증:
- `http://127.0.0.1:4184/?v=phase6c` 로드 성공
- Crop 패널에 좌표/크롭/맞춤 버튼 노출 확인
- Layer 패널에 opacity/group/ungroup/export 노출 확인
- 콘솔 JS 에러 없음
- 런타임 함수 확인: `applyCanvasCrop`, `eraseSelectedByMask`, `groupSelection`
- 그룹화/그룹해제/opacity 적용 동작 확인
- 테스트 이미지 + 마스크 생성 후 `eraseSelectedByMask`, `restoreSelectedByMask` history label 확인

## Notes / Known Limits

- 선택 이미지 크롭/마스크 지우기/복원은 결과를 투명 PNG 레이어로 재생성하는 안정 우선 방식.
- 복잡한 회전/원점/비율 케이스의 픽셀 완전 일치 보정은 다음 polish 단계에서 개선 여지 있음.
