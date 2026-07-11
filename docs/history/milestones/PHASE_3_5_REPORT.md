# Phase 3.5 Report — Professional UX Pass

완료일: 2026-07-04
대상: `/Users/tajokim/asset-studio-local`
목표: Pixellab + Canva 방향에 맞게 “기능 많은 프로토타입”에서 “전문 게임/픽셀 에셋 편집툴”처럼 보이고 쓰이는 UX로 정리.

## 변경 파일

- `index.html`
- `styles/app.css`
- `src/main.js`
- `PROFESSIONAL_AUDIT.md` 신규 추가
- `PHASE_3_5_REPORT.md` 신규 추가

## 주요 변경

### 1. 브랜드/제품 포지션 정리

- 타이틀 변경: `Asset Studio Local` → `Pixel Asset Studio`
- 상단 브랜드 변경: `Pixel Asset Studio`
- 배지 변경: `Game Asset Canvas`
- 개발자용 버전 문구 `v0.3 mask base` 제거

### 2. 한글 중심 라벨 정리

- `Canvas` → `캔버스 적용`
- `Save JSON` → `프로젝트 저장`
- `Load` → `불러오기`
- `Export PNG` → `PNG 내보내기`
- `Add Text` → `텍스트 추가`
- `AI Cutout` → `AI 배경 제거`
- `Asset Sheet BG` → `에셋 시트 배경 제거`
- 툴바: 선택/이동/크롭/브러시/펜슬/지우개/마스크/텍스트/도형/업로드/AI 생성

### 3. 캔버스 작업영역 전문툴화

- 중앙 workspace에 어두운 제작툴형 배경 적용
- 미세 그리드 배경 추가
- 아트보드 shell에 border/shadow 강화
- `ARTBOARD` 라벨 추가
- 빈 캔버스 안내/drop hint 추가
  - “이미지를 끌어오거나 사진 넣기”
  - “투명 PNG 게임 에셋을 만들 캔버스입니다.”
- 사용자가 텍스트/이미지/도형 등 실제 오브젝트를 추가하면 빈 캔버스 안내가 자동 숨김 처리됨

### 4. 패널 위계/시각 정리

- 패널 카드 스타일 정리
- 버튼/입력/레이어 row 여백 개선
- 주요 버튼/위험 버튼 시각 구분 강화
- 상단 버튼 줄바꿈 방지 및 overflow-x 처리
- 프리셋 select 최소 너비 보정

### 5. JS 상태문구 정리

- 도구 상태 문구 한글화
- 선택 없음 문구 정리
- 마스크 상태 문구 한글화
- Phase 3.5 완료 상태문구 반영
- 빈 캔버스 hint 표시/숨김 로직 추가

## 검증

### 정적 검증

```bash
python3 -m py_compile server.py
node --check src/main.js
```

결과: 통과

### 브라우저 검증

검증 URL:

```text
http://127.0.0.1:4184/?v=phase35-professional-ux-5
```

확인 항목:

- 페이지 타이틀 `Pixel Asset Studio` 로드 확인
- 상단 브랜드/배지 표시 확인
- 툴바 한글 라벨 표시 확인
- 기본 레이어 1개 유지 확인
- 빈 캔버스 안내 표시 확인
- 텍스트 도구 클릭 → 옵션 패널 전환 확인
- `텍스트 추가` 클릭 → Text 레이어 추가 확인
- 실제 오브젝트 추가 후 빈 캔버스 안내 자동 숨김 확인
- checkerboard가 Fabric lower canvas에만 적용되고 upper canvas는 transparent인 것 확인
- 브라우저 console JS error 없음

### 독립 코드 리뷰

`requesting-code-review` 절차에 맞춰 별도 reviewer로 현재 diff를 재검토함.

- 최초 리뷰에서 checkerboard CSS가 Fabric upper canvas를 가릴 수 있다는 회귀 위험이 발견됨
- 수정: `.canvas-shell.checker .lower-canvas`에만 checkerboard 적용, `.upper-canvas`는 transparent 강제
- 재리뷰 결과: `passed: true`, security concern 없음, logic error 없음

### API smoke 상태

이 Phase에서는 API 코드를 바꾸지 않음. 이전 점검 기준:

- `/api/remove-bg` 정상
- `/api/inpaint`는 아직 backend 미연결 상태를 명시적으로 `501` 반환

## 의도적으로 하지 않은 것

다음은 Phase 3.5 범위를 넘기므로 아직 하지 않음:

- 실제 Crop 구현
- 실제 선택영역 inpaint backend 연결
- 텍스트 shadow/glow/font preset 강화
- pixel grid/sprite sheet/palette 기능
- 전체 코드 모듈 분리
- Git commit/push

## 남은 개선 후보

다음 Phase 후보:

1. **Phase 3.6 — 전문툴 기능 보강**
   - Transform 입력 비활성 상태 처리
   - Align/Distribute
   - snap/grid/pixel grid
   - 텍스트 shadow/stroke/pixel font preset

2. **Phase 4 — Style-preserving selected-area inpaint backend**
   - 마스크 + 원본 이미지 + 프롬프트 전송
   - 결과 preview
   - 새 레이어/교체/retry
   - 픽셀/게임 에셋 스타일 유지 프롬프트 자동 주입

## 현재 결론

Phase 3.5로 제품 인상이 다음처럼 바뀜:

> 기능 많은 내부 프로토타입 → PixelLab + Canva 방향의 게임/픽셀 에셋 편집툴 베타 UI

다음은 사용자 확인 후 Phase 3.6 또는 Phase 4로 진행.
