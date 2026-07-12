---
title: "Asset Studio 저장소 감사 및 개선 백로그"
tags: ["asset-studio", "repository-audit", "improvement-backlog", "frontend", "backend", "cleanup", "sprite", "dungeon-cleanup-inc"]
created: 2026-07-11T14:01:00.265Z
updated: 2026-07-11T23:58:55+09:00
sources: []
links: ["asset-studio-제품-목적과-스프라이트-합격-기준.md", "asset-studio-최신-제품-방향-및-생성-검증-재설계.md", "asset-studio-기존-문서-통합-및-정리-판정.md"]
category: architecture
confidence: medium
schemaVersion: 1
---

# Asset Studio 저장소 감사 및 개선 백로그

> 기준일: 2026-07-11
> 조사 방식: 브라우저나 서버 실행 없이 저장소 코드, 정적 구조, 테스트를 읽고 검증했다.
> 상태: 분석 시점 작업 트리는 깨끗했으며 제품 코드는 수정하지 않았다.
>
> **정정:** 이 문서의 코드 감사 근거는 유지하지만 “`dungeon-cleanup-inc` 전용 도구”라는 제품 전제와 그에 따른 완료 기준·실행 순서는 폐기한다. `dungeon-cleanup-inc`는 프로토타입 출력 프로필과 회귀 fixture로만 취급한다. 현재 정본은 [[asset-studio-최신-제품-방향-및-생성-검증-재설계]]이며, 문서별 유지·폐기 판단은 [[asset-studio-기존-문서-통합-및-정리-판정]]에 있다.

## 제품 전제

Asset Studio는 범용 도트 게임 에셋 생성·경량 편집 도구다. UI, 생성 프롬프트, 후처리, QA와 내보내기는 공통 생성 레시피와 교체 가능한 출력 프로필을 기준으로 설계한다.

스프라이트 동작 품질과 범용·프로필별 계약의 경계는 [[asset-studio-제품-목적과-스프라이트-합격-기준]]에 별도로 기록한다.

## 저장소가 현재 하는 일

AI 생성 중심의 게임 에셋 제작 도구다. sprite, tile/map, UI, object 네 계열을 만들고 Fabric.js 기반 수동 편집 기능을 보조적으로 제공한다.

현재 구현은 다음과 같이 구성된다.

- 프론트엔드: 빌드 단계 없는 단일 페이지 Vanilla JavaScript와 Fabric.js
- 주요 파일: `index.html`, 약 6,950줄의 `src/main.js`
- 백엔드: 약 3,307줄의 Python `SimpleHTTPRequestHandler` 기반 `server.py`
- 생성 공급자: Hermes 및 OpenAI Codex 연동
- 운영 형태: 로컬 서버와 선택적 터널
- 프로젝트 기반: 패키지 잠금 파일, 정식 프론트 빌드 시스템, CI가 없다

근거: `README.md:1-14`, `docs/plans/asset-studio-product-spec.md:10-35`, `index.html`, `src/main.js`, `server.py`.

## 우선순위가 가장 높은 문제

### P0-1. 스프라이트 액션이 실제 동작 시퀀스로 보장되지 않는다

UI와 프롬프트에 idle, walk, attack 등의 이름은 있으나 결과가 일관된 캐릭터 애니메이션 시트 계약을 충족하지 않는다. 정지 포즈 모음이나 스프라이트처럼 보이는 이미지가 출력되는 것은 기능 성공이 아니다.

필요한 해결 방향:

- 액션별 포즈 단계와 프레임 순서를 명시적인 데이터 계약으로 정의
- 캐릭터 정체성, 방향, 장비, 팔레트, 피벗과 발 위치를 프레임 전체에서 고정
- idle과 walk의 루프, attack의 준비·타격·회수 단계를 자동 검수
- 액션과 방향별 미리보기 재생 및 부분 재생성 지원
- `dungeon-cleanup-inc`의 실제 로더 규격에 맞춘 시트 배치와 내보내기
- 외관 유사도와 동작 연속성을 분리해 평가하는 QA

확신도: 높음. 사용자가 실제 결과 실패를 확인했으며 현재 코드는 액션 명칭과 정적 규칙은 다루지만 게임 런타임 수준의 동작 검증을 강제하지 않는다.

### P0-2. 픽셀 워크플로의 반환 계약이 깨져 후처리가 조용히 생략된다

`generateAiAsset()`는 `src/main.js:6417`에서 `{url, result, data, referenceObj}`를 반환한다. 그러나 `runPixelWorkflow()`는 `src/main.js:6654-6655`에서 `result.img`를 요구하고 없으면 종료한다.

따라서 화면에 노출된 “생성 → 배경 제거 → 그리드 값 맞춤” 흐름은 생성과 자동 채택 뒤에 배경 제거와 그리드 처리를 건너뛸 가능성이 높다. 이 계약을 공유하는 배치 흐름도 같은 위험이 있다.

추가로 `runPixelSamplePack()`은 숨겨진 레거시 컨트롤 값을 바꾸지만 현재 에셋 family 상태 전환을 보장하지 않아 다른 유형의 작업을 생성할 수 있다.

해결 방향:

- 단일 생성 결과 타입을 정의하고 생성, 후처리, 채택, 내보내기 전체에서 공유
- 내부 함수 반환값을 직접 검증하는 통합 테스트 추가
- 숨겨진 DOM 값을 통한 파이프라인 제어 제거

확신도: 높음. 호출부와 반환부의 직접적인 구조 불일치다.

### P0-3. 선택 가능한 subtype과 내보내기 라우팅이 불일치한다

`src/main.js:562-567`의 `ASSET_FAMILY_SUBTYPES`는 32개 subtype을 노출한다. `src/main.js:6200-6222`의 `familyExportDescriptor`는 그중 12개만 명시적으로 지원한다.

명시 라우팅이 빠진 항목:

- tile: floor, wall, corner, door, decal
- UI: main_panel, inner_panel, popup, card, slot, badge, hud_chip, gauge, cursor
- object: equipment, weapon, loot, furniture, machine, destructible

반대로 실제 선택지와 맞지 않는 과거 alias인 `tile/map`, `ui/panel`, `ui/ui_panel`, `object/decoration`이 남아 있다.

해결 방향:

- UI, 서버, QA, 저장, 내보내기가 하나의 정규 taxonomy를 공유
- 모든 family/subtype 조합을 순회하는 계약 테스트 추가
- 과거 alias는 명시적 마이그레이션 경계에서만 처리

확신도: 높음. 열거형 집합을 직접 비교한 결과다.

### P0-4. 출력 크기, 종횡비, 배경 옵션이 실제 생성 계약이 아니다

프론트엔드는 출력 너비, 높이, 배경 값을 payload에 포함하지만 서버의 `server.py:1227-1251`은 값을 정규화할 뿐 `build_asset_family_prompt()`인 `server.py:1265`에서 실질적으로 사용하지 않는다.

`#aiAspect` 요소가 없어 `generateAiAsset()`은 사실상 정사각형 기본값으로 흐른다. UI는 여러 family에 크로마 그린을 강제하지만 서버는 `server.py:3256`에서 non-sprite의 `background_mode`을 none으로 바꾸고, `server.py:1973-2034`의 tile/UI/object 후처리는 배경 제거 없이 원본 바이트를 유지한다.

해결 방향:

- 크기와 종횡비가 공급자 요청, 검증, 후처리, 최종 파일에 실제 반영되도록 연결
- family별 배경 정책을 UI와 서버에서 동일하게 표현
- 요청값과 실제 출력 규격 불일치를 실패로 처리

확신도: 높음. 값의 수집과 실제 소비 경로가 분리되어 있다.

### P0-5. 결과 비교·채택 모델과 자동 채택 동작이 충돌한다

제품 명세는 생성 결과를 비교한 뒤 채택하는 흐름을 제시한다. 그러나 `generateAiAsset()`는 `src/main.js:6416`에서 새 레이어로 자동 채택한다.

Result Tray에는 거절 동작이 남아 있지만 상태 전이는 `src/main.js:199-209`에서 adopted 결과의 rejected 전환을 막는다. 그래서 이미 자동 채택된 결과를 사용자가 거절하면 오류가 날 수 있다. `library`, `replace-source` 모드도 코드에는 있으나 현재 UI에서 접근하기 어렵다.

결과 표면도 Result Tray, gallery, pixelResultSlots 세 군데로 나뉘어 상태와 책임이 중복된다.

결정 필요:

- 자동 채택을 제품 원칙으로 삼을지
- preview → compare → adopt를 원칙으로 삼을지

현재 목적에는 액션과 방향별 품질 비교가 필요하므로 명시적 검수 후 채택 모델이 더 자연스럽다는 것이 분석상 제안이다. 최종 결정 전에는 두 모델을 동시에 유지하지 않는다.

확신도: 높음. 명세, 상태 머신, 실제 호출 흐름이 상충한다.

## P1 구조와 운영 문제

### QA 하위 시스템이 실제 생성 경로를 보호하지 않는다

`server.py:383`의 `route_family_qa`와 연관된 약 400줄은 테스트에서만 참조되고 API나 생성 경로에서는 호출되지 않는다. 이 계층의 taxonomy는 effect/sequence를 사용하지만 실제 생성은 sprite/effect를 사용해 개념도 어긋난다.

`slice_effect_sequence`, `sprite_action_matrix_for_ui`, `build_sprite_action_prompt` 등도 런타임 연결이 확인되지 않았다.

해결 방향은 둘 중 하나다.

- 실제 생성과 채택 전 QA gate로 연결하고 정규 taxonomy를 사용
- 독립 실험 모듈이나 문서로 이동한 뒤 제품 코드에서는 제거

확신도: 높음. 런타임 호출 참조가 없다.

### 정적 파일 제공 범위와 터널 정책이 위험하다

Handler는 `SimpleHTTPRequestHandler`를 상속하고 `server.py:3045-3048`에서 일반 GET을 상위 구현에 넘긴다. 프로세스는 `server.py:3303`에서 저장소 루트를 현재 디렉터리로 사용한다.

동시에 외부 trycloudflare origin을 허용한다. 이 조합은 터널 사용 시 저장소 내부 파일까지 정적 경로로 노출될 가능성이 있다. 일부 API 응답은 `server.py:3084` 등에서 절대 로컬 경로인 `path`도 반환하며 프론트에서는 이를 사용하지 않는다.

해결 방향:

- 정적 공개 루트를 별도 `public/`으로 제한하거나 allowlist 라우팅
- API 응답에서 절대 로컬 경로 제거
- CORS와 터널 origin을 최소 권한으로 재설계
- 오류 응답 형식과 민감 정보 필터링 통일

확신도: 중간 이상. 경로 제공 가능성은 코드상 명확하나 실제 터널 배포 설정별 노출은 별도 검증이 필요하다.

### 실행 환경이 특정 사용자 경로에 묶여 있다

`server.py:33`과 `scripts/run_server.sh:11-12`에 `/Users/tajokim/.hermes/hermes-agent`가 하드코딩되어 있다. 실행 스크립트가 Hermes 가상환경에 요구사항을 설치할 가능성도 있다.

pytest는 문서화된 개발 의존성에 없고 requirements에는 Pillow, Numpy, rembg, httpx 정도만 있다.

해결 방향:

- 경로를 환경 변수와 설정 파일로 이동
- 프로젝트 전용 가상환경과 잠금된 런타임·개발 의존성 분리
- 재현 가능한 테스트 명령과 CI 추가

확신도: 높음.

## UI와 사용 흐름 감사

### 실제 반응형 레이아웃이 아니다

`.app`은 `src/styles.css:77-83`에서 64 + 310 + 7 + min 420 + 7 + 336 구조를 사용한다. 1100px 이하 규칙에서도 최소 폭이 약 878px이라 `index.html:107`의 iPad/iPhone 안내와 실제 레이아웃이 맞지 않는다.

해결 방향:

- 좁은 화면에서는 단일 컬럼 또는 편집 캔버스 중심의 탭·드로어 구조
- 고정 폭 패널 대신 축소 가능한 panel contract
- 모바일에서 생성, 검수, 채택, 내보내기의 핵심 경로만 우선 제공

### Result Tray의 위치와 정보 구조가 명세와 다르다

Result Tray는 `index.html:161-168`에서 긴 AI 폼 아래 왼쪽 스크롤 영역에 있다. 제품 명세의 하단 drawer 개념과 다르며 결과 비교가 핵심 작업인데 접근성이 낮다.

스프라이트 액션과 방향별 결과를 다루려면 결과 영역을 단일 검수 작업대로 통합하고, 애니메이션 재생과 차이 비교를 중심에 두어야 한다.

### 명칭과 실제 기능이 어긋난다

한국어와 영어 레이블이 혼재한다. “AI 대화형 편집”은 실제 대화형 모델보다는 `server.py:2886`의 `classify_chat_command` 기반 결정적 키워드 라우터에 가깝다.

기능이 하는 일을 정확히 설명하는 이름으로 바꾸거나 실제 대화형 편집으로 구현해야 한다.

### 오프라인 로컬 도구인데 핵심 라이브러리가 CDN 전용이다

Fabric.js는 `index.html:212`의 CDN 한 곳에서만 로드한다. 네트워크가 없으면 로컬 앱의 핵심 편집기가 동작하지 않는다.

로컬 번들 또는 vendored asset으로 전환하는 편이 제품 목적에 맞는다.

### 데모와 과거 상태 문구가 제품 상태에 남아 있다

`src/main.js:6936-6949`에 seed demo ICON/CARD와 “B안 오브젝트 치환 UI 적용됨” 같은 개발 상태 메시지가 남아 있다.

빈 상태 UX와 실제 작업 안내로 교체한다.

## 삭제 또는 격리가 필요한 코드 후보

삭제 전에는 행동을 고정하는 회귀 테스트를 먼저 작성한다.

### 백엔드

강한 삭제 후보:

- 프론트와 테스트에서 사용하지 않는 `/api/upload-data-url`
- 해당 API에서만 사용하는 `UPLOADS`
- mkdir 외 의미가 없는 `PROJECTS`
- 사용하지 않는 `shutil` import
- 호출되지 않는 `_crop_single_direction_candidate`
- 그 함수에서만 사용하는 `_direction_slot_index`

연결 또는 격리 판단 후보:

- `route_family_qa`
- `slice_effect_sequence`
- `sprite_action_matrix_for_ui`
- `build_sprite_action_prompt`

후자는 의도 자체는 중요할 수 있어 즉시 삭제하기보다 실제 파이프라인에 연결할지 실험 코드로 분리할지를 먼저 결정한다.

### 프론트엔드

정의만 있고 실제 호출이 확인되지 않은 함수:

- `deriveWalkBeatLabels`
- `resultWalkQaGate`
- `addReplacementImageUrl`
- `exportCanvasWithoutMaskOverlays`
- `copySelectedRegionToLayer`

`resultWalkReviews` 맵은 기록만 하고 소비하지 않는다. 관련 walk QA UI가 실제 액션 검수기로 재설계되지 않는다면 함께 제거한다.

사용 흔적이 없는 강한 CSS 후보:

- `.asset-result-adopt`
- `.result-walk-qa`
- `.result-walk-beats`
- `.workflow-preview-box`
- `.workflow-preview-title`
- `.disabled-note`
- `button.good`

Fabric.js가 동적으로 쓰는 `.lower-canvas`, `.upper-canvas` 같은 클래스는 정적 검색 결과만으로 삭제하면 안 된다.

### 숨겨진 레거시 DOM

`pixelAssetType`, `pixelStylePreset`, `pixelDirection`, `pixelPalette`, `pixelSubject`, `generatePixelAsset`와 과거 버튼들이 숨겨진 상태로 남아 있고 정적 테스트가 이 요소를 마이그레이션 계약처럼 요구한다.

해결 순서:

1. 과거 프로젝트 데이터 변환을 명시적인 deserializer/migration 함수로 이동
2. 실제 과거 fixture로 호환성 테스트 작성
3. 숨겨진 DOM과 우회 제어 코드 삭제
4. 문자열 존재 여부만 검사하는 테스트 제거

### 존재하지 않는 요소를 향한 no-op 연결

다음 ID를 찾는 방어 코드가 있으나 현재 DOM에는 없다.

- `aiPrompt`
- `aiPreset`
- `aiAspect`
- `generateBtn`
- `uiBorder`
- `uiCorner`

호환성 계층이 아니라면 제거하고, 필요한 요소라면 현재 스키마에 정식으로 추가한다.

### 스크립트 정리

generate/visualqa 계열 스크립트 약 15개가 `/Users/tajokim` 절대 경로를 포함한다. 또한 `asset-studio-local/asset-studio-local/scripts`처럼 중첩된 복제 경로가 있다.

사용되는 운영 스크립트, 재현 가능한 실험, 일회성 산출물을 구분해 `scripts/`, `experiments/`, 삭제 대상으로 정리해야 한다.

## 테스트 감사

관찰한 구조:

- 테스트 파일 79개
- 테스트 함수 약 537개
- 정적 소스 문자열 검사 파일 36개
- 소스를 직접 읽는 테스트 64개
- Node를 호출하는 테스트 21개
- `server.py`를 import하는 테스트 22개

현재 테스트는 코드 토큰 존재 여부를 많이 확인해 실제 계약 파손을 놓친다. 예를 들어 phase15 정적 테스트는 모두 통과하지만 `generateAiAsset()`와 `runPixelWorkflow()`의 반환 계약 불일치를 잡지 못한다.

직접 정적 실행에서 확인된 오래된 실패:

- `tests/test_phase16_page_asset_pack_static.py`
- `tests/test_phase7a_*.py`
- `tests/test_phase22_*.py`
- transform flip 관련 테스트

주된 원인은 `src/main.js?v=20260710.8` 같은 오래된 버전 문자열 기대다. `index.html`에는 오래된 CSS 버전 문자열을 테스트에 맞추기 위한 호환 주석도 있다.

검증 결과:

- `node --check src/main.js`: 통과
- `server.py` AST 파싱: 통과
- HTML parser 검사: 통과
- `git diff --check`: 통과
- 전체 pytest: 시스템 Python에 pytest가 없고 개발 의존성에도 명시되지 않아 실행하지 못함

필요한 테스트 전환:

- 함수 반환 타입과 실제 호출 결과를 검증하는 통합 테스트
- 모든 family/subtype의 생성 → 후처리 → 채택 → 내보내기 계약 테스트
- 실제 브라우저 없이도 실행 가능한 DOM 경계 테스트
- `dungeon-cleanup-inc` 규격 fixture를 사용한 스프라이트 시트 검증
- idle, walk, attack의 액션 의미, 루프, 피벗, 방향 순서 검사
- 과거 저장 프로젝트 fixture 기반 마이그레이션 테스트
- 정적 문자열 검사는 구조적 불변식에만 제한

## 권장 실행 순서

1. `dungeon-cleanup-inc`의 실제 소비자 계약을 코드에서 추출한다.
2. 현재 동작을 실행 가능한 회귀·통합 테스트로 고정한다.
3. 스프라이트 액션 합격 기준과 자동 QA fixture를 먼저 만든다.
4. 자동 채택과 검수 후 채택 중 하나로 제품 흐름을 확정한다.
5. 생성 결과 타입과 생성 파이프라인을 하나로 통합한다.
6. UI, 서버, QA, 저장, 내보내기의 taxonomy를 단일 소스로 합친다.
7. 크기, 종횡비, 배경 설정을 실제 출력 계약으로 만든다.
8. QA 계층을 실제 gate로 연결하거나 제품 코드에서 격리한다.
9. 정적 제공 범위, CORS, 절대 경로 응답과 실행 환경 이식성을 수정한다.
10. 회귀 테스트를 근거로 죽은 함수, CSS, 숨겨진 DOM, 일회성 스크립트를 삭제한다.
11. 마지막으로 현재 거대 파일을 검증된 기존 경계에 따라 분리한다.

모놀리스를 먼저 쪼개지 않는다. 계약과 동작을 고정한 뒤 taxonomy, 결과 상태, 생성 파이프라인, 캔버스 편집, 내보내기 같은 이미 존재하는 책임 경계를 따라 분리한다.

## 완료 기준

이 저장소의 개선 작업은 다음 조건을 만족해야 완료로 볼 수 있다.

- `dungeon-cleanup-inc`에서 요구하는 파일과 메타데이터를 수동 보정 없이 가져올 수 있다.
- idle, walk, attack 등 지원 액션이 방향별로 일관되고 재생 가능한 시퀀스다.
- 생성 설정과 실제 결과 규격이 일치한다.
- 실패한 액션이나 방향을 식별하고 부분 재생성할 수 있다.
- UI, 서버, QA, 저장, 내보내기 taxonomy가 동일하다.
- 죽은 기능과 호환성 잔재가 테스트를 이유로 제품 코드에 남지 않는다.
- lint, typecheck 또는 이에 준하는 정적 검사, 단위·통합 테스트가 재현 가능하게 실행된다.
- 로컬 전용 사용과 외부 터널 사용의 노출 범위가 명시적으로 분리된다.

## 근거와 추론의 경계

직접 근거:

- 함수 반환값과 호출부 조건
- UI에 노출된 subtype과 export descriptor 집합
- DOM, CSS, 함수 참조 관계
- 서버 라우팅, 정적 파일 제공, 하드코딩된 경로
- 테스트 구조와 직접 실행 결과
- 사용자가 확인한 스프라이트 액션 실패 및 소비자 저장소

추가 조사 후 확정할 항목:

- `dungeon-cleanup-inc`의 정확한 엔진, importer, 프레임·피벗·FPS 규격
- 실제 모델별 이미지 생성 한계와 액션 일관성 확보 방식
- 터널 운용 시 저장소 파일의 실제 외부 접근 가능 범위
- 제거 후보가 과거 사용자 프로젝트 파일에서 간접적으로 필요한지 여부

## 추가 요구사항 수집란

사용자가 이어서 제공하는 문제와 원하는 동작을 이 문서의 우선순위, 합격 기준, 실행 순서에 계속 반영한다.
