# Professional Audit — Asset Studio Local

점검일: 2026-07-04
대상: `/Users/tajokim/asset-studio-local`
제품 포지션: **Pixellab + Canva = 게임/픽셀 에셋용 Canva형 편집툴**

## 현재 상태 요약

현재 구현은 프로토타입 수준을 넘어서, 편집기 골격은 꽤 갖춰져 있다.

- 좌측 툴레일: Select, Pan, Crop, Brush, Pencil, Eraser, Mask, Text, Shape, Upload, AI
- 중앙 작업영역: Fabric.js 캔버스, zoom/pan, checkerboard
- 우측 패널: Properties, Style/Text, Background, Canvas/Export, AI Edit, Layers, Shortcuts
- 레이어: 기본 Drawing Layer 1, 추가, 이름 변경, 보이기/잠금, 버튼/드래그 순서 변경
- 배경 제거: 단일 피사체 AI Cutout, Asset Sheet BG 분리
- 마스크: 브러시/지우개/사각 선택, 마스크 PNG export
- AI 선택영역 편집: UI/API 계약까지 있음. 실제 backend는 아직 501로 명시적 미연결

## 검증 내용

- `python3 -m py_compile server.py` 통과
- `node --check src/main.js` 통과
- 로컬 서버: `http://127.0.0.1:4184`
- 브라우저 로드 정상
- 콘솔 JS 에러 없음
- 새 문서 기본 레이어 1개 확인
- 텍스트 추가 후 레이어 패널 반영 확인
- `/api/remove-bg` smoke test 성공: `200`, method=`preserve-mask-sheet`
- `/api/inpaint` smoke test: `501`, backend 미연결 상태를 명시적으로 반환

## 전문툴 관점 강점

1. **기본 구조가 맞다**
   - Canva/Figma류의 좌측 툴바 + 중앙 캔버스 + 우측 속성/레이어 패널 구조가 잡혀 있다.

2. **레이어 UX의 핵심 실수는 이미 피했다**
   - 브러시 stroke가 레이어 목록에 개별로 쌓이지 않고 Drawing Layer 내부에 묶이는 방향은 맞다.

3. **픽셀/게임 에셋용 배경 제거 방향이 좋다**
   - 단일 피사체용 AI Cutout과 여러 아이템 시트용 Asset Sheet BG를 분리한 점은 일반 Canva류보다 게임 에셋 제작에 더 맞다.

4. **AI 선택영역 편집의 앞단 구조가 잡혔다**
   - 마스크 브러시/지우개/사각 선택 + mask export + AI Edit 패널까지 있어 Phase 4 연결이 가능하다.

## 전문툴 관점 문제점

### P0 — 지금 바로 잡아야 할 제품성 문제

1. **중앙 캔버스가 주인공처럼 보이지 않는다**
   - 좌우 패널의 정보량이 강하고, 실제 아트보드 경계/무대감이 약하다.
   - Canva/PixelLab 계열은 사용자가 “지금 작업물을 만들고 있다”는 감각이 중요하다.

2. **우측 패널이 과밀하다**
   - Properties, Style/Text, Background, Export, AI Edit, Layers가 모두 같은 무게로 노출된다.
   - 전문툴처럼 쓰려면 섹션 접기/펼치기, Transform/Arrange/Appearance/Text 그룹화가 필요하다.

3. **용어/언어가 섞여 있다**
   - `사진 넣기`, `Export PNG`, `Save JSON`, `Load`, `Canvas`, `Apply`가 혼재한다.
   - 한국어 서비스면 한글 중심, 전문툴이면 영어 중심 중 하나로 통일해야 한다.

4. **실제 전문 편집 기능 일부가 아직 scaffold다**
   - Crop은 자리만 있음.
   - Align/distribute, snap, grid, pixel grid, nudge, zoom percentage UX가 부족하다.

5. **AI Edit는 UI는 있지만 아직 실제 편집은 안 된다**
   - `/api/inpaint`가 501을 반환하는 상태.
   - 사용자가 버튼을 누르면 “준비 중”임은 알 수 있지만, 아직 핵심 차별점은 미완성이다.

### P1 — 전문 제작툴로 가려면 필요한 핵심 개선

1. **PixelLab다운 텍스트 기능 강화**
   - font family
   - align left/center/right
   - stroke/shadow/glow
   - letter spacing/line height
   - outline preset
   - 픽셀 폰트 preset

2. **Canva다운 쉬운 편집 UX**
   - 선택 시 floating mini toolbar
   - 정렬/복제/삭제 quick action
   - 빈 캔버스 CTA
   - 드래그앤드롭 안내
   - 상태/에러를 alert 대신 toast/status로 통일

3. **게임/픽셀 에셋용 전문 기능**
   - pixel grid overlay
   - nearest-neighbor scale/export
   - 팔레트 추출/팔레트 제한
   - sprite sheet slice/export
   - transparent PNG 검증
   - asset sheet item count/cleanup quality check

4. **프로젝트 구조 개선**
   - `src/main.js`가 1175라인 단일 파일이라 장기 유지보수에 불리하다.
   - 권장 분리:
     - `state.js`
     - `layers.js`
     - `tools.js`
     - `mask.js`
     - `ai.js`
     - `export.js`
     - `ui-panels.js`

### P2 — 나중에 붙일 고급 기능

- 템플릿/프리셋 시스템
- 에셋 라이브러리
- 히스토리 패널
- 프로젝트 자동저장
- 다중 페이지/다중 아트보드
- 키보드 단축키 설정
- inpaint 결과 preview/apply/retry 비교창

## 추천 다음 Phase

기존 순서대로라면 Phase 4 inpaint backend가 다음이지만, 전문적으로 쓰게 만들려면 먼저 한 번 정리 Phase가 필요하다.

### 추천: Phase 3.5 — Professional UX Pass

범위:

1. 캔버스 작업영역 개선
   - 아트보드 border/shadow 강화
   - checker/white/transparent 상태 명확화
   - 빈 캔버스 안내/드롭존

2. 우측 패널 구조 정리
   - Transform / Arrange / Appearance / Text / Background / AI Edit / Layers로 재분류
   - 접이식 섹션 또는 우선순위 재배치

3. 용어 통일
   - 한글 UI 기준으로 정리 권장
   - Export PNG → PNG 내보내기
   - Save JSON → 프로젝트 저장
   - Load → 불러오기
   - Canvas → 캔버스 적용
   - Apply → 값 적용 / 스타일 적용

4. PixelLab+Canva 포지션 반영
   - 브랜드/배지 문구 변경: `v0.3 mask base` 대신 `Pixel Asset Canvas`류
   - AI Generate보다 `에셋 생성`, `선택영역 수정` 중심으로 라벨 정리

5. 위험/주요/보조 버튼 위계 정리
   - 삭제는 위험 버튼으로 작게
   - 주요 작업은 primary
   - 보조 작업은 compact button

## 결론

현재는 “기능이 꽤 많이 붙은 개발자용 프로토타입” 단계다.
전문적으로 쓰게 만들려면 바로 AI backend를 붙이기보다, 한 Phase 정도는 **전문툴처럼 보이고 쓰이는 UX 정리**를 먼저 하는 것이 맞다.

추천 다음 작업:

> **Phase 3.5: Professional UX Pass**

그 다음에:

> **Phase 4: Style-preserving selected-area inpaint backend**
