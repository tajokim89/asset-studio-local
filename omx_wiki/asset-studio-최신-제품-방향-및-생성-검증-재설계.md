---
title: "Asset Studio 최신 제품 방향 및 생성·검증 재설계"
tags: ["asset-studio", "pixel-art", "image-generation", "sprite", "hermes", "qa", "evaluation", "product-direction"]
created: 2026-07-11T23:58:55+09:00
updated: 2026-07-11T23:58:55+09:00
sources: ["docs/plans/2026-07-10-ai-first-asset-studio-product-spec.md", "docs/plans/2026-07-10-ai-first-asset-studio-work-plan.md", "docs/history/milestones/PHASE_25_REPORT.md", "docs/history/artifacts/PHASE_25_ACTION_PRESET_GENERATION_RESULTS.json"]
links: ["asset-studio-제품-목적과-스프라이트-합격-기준.md", "asset-studio-이미지-생성-파이프라인-감사-보고서.md", "asset-studio-저장소-감사-및-개선-백로그.md", "asset-studio-기존-문서-통합-및-정리-판정.md"]
category: architecture
confidence: high
schemaVersion: 1
---

# Asset Studio 최신 제품 방향 및 생성·검증 재설계

> 기준일: 2026-07-11
> 상태: 현재 제품 방향의 정본
> 조사 방식: 브라우저·서버·유료 API를 실행하지 않고 코드, 테스트와 기존 산출물을 대조했다. 제품 코드는 수정하지 않았다.
>
> 세분화된 실행 순서와 중단·재개 규칙: [Asset Studio 원자 단위 실행 계획](../.omx/plans/asset-studio-atomic-execution-plan.md)

## 결론

Asset Studio는 **Hermes를 기본 생성 Provider로 사용하는 범용 도트 게임 에셋 생성·경량 편집 도구**로 재정비한다.

편집기는 상당 부분 재사용할 수 있다. 전면 교체가 필요한 곳은 AI 모델 자체가 아니라 다음 생성 오케스트레이션이다.

    레시피와 출력 프로필
      -> 후보 여러 개 생성
      -> 결정적 로컬 QA
      -> 의미·시각 QA
      -> 후보 비교와 사용자 승인
      -> 필요한 부분만 편집
      -> 프로필 기반 내보내기

현재처럼 모델 응답 한 장을 곧바로 성공·자동 채택하는 흐름은 중단해야 한다. 특히 애니메이션 스프라이트는 완성 시트 한 장 생성 방식에서 벗어나 정체성, 방향, 동작 단계와 프레임 후보를 나누어 생성·조립해야 한다.

## 제품 경계

| 구분 | 제품 공통 계약 | 출력 프로필 계약 | 사례 |
| --- | --- | --- | --- |
| 생성 | 레시피, 후보, reference, Provider | 허용 모델·스타일 기본값 | Hermes 기본 |
| 이미지 | 알파, 픽셀 정렬, 후보 상태 | W/H, 팔레트, 외곽선 | 88×88 actor |
| 애니메이션 | action, direction, frame, loop | 액션명, 방향 순서, FPS, pivot | `dungeon-cleanup-inc/actor-v1` |
| 내보내기 | manifest, hash, QA 결과 | 경로, 파일명, importer 형식 | Godot 경로 |

`dungeon-cleanup-inc`는 마지막 열의 프로토타입 사례다. 범용 기본값이나 제품 완료 조건으로 사용하지 않는다.

## 현재 생성이 운에 의존하는 직접 원인

### 1. 생성 성공과 품질 성공이 같은 상태다

- `src/main.js:6411-6417`은 Provider 응답 직후 결과를 자동 채택한다.
- `src/main.js:314-354`의 채택 경로에는 동작 의미나 family QA gate가 없다.
- `server.py:383`의 `route_family_qa`는 생성 API에 연결되지 않았다.
- `src/main.js:383`의 `resultWalkQaGate`도 실제 채택에 연결되지 않았다.

따라서 “이미지 응답을 받음”과 “게임 에셋으로 쓸 수 있음”이 구분되지 않는다.

### 2. 한 번의 요청에 너무 많은 제약을 건다

`server.py:3263-3264`의 일반 경로는 Provider를 한 번 호출해 한 장을 받는다. 스프라이트 시트에서는 한 요청이 캐릭터 동일성, 방향, 프레임 순서, 동작, 루프, 배경과 셀 규격을 동시에 맞춰야 한다. 실패할수록 다시 전체를 뽑기 때문에 결과가 운에 좌우된다.

### 3. 화면에 있는 계약과 실제 요청이 다르다

- 상세 프롬프트는 `src/main.js:1146-1176`에서 만들어지지만 `src/main.js:1179-1185`가 존재하지 않는 `aiPrompt`에 쓰려 한다.
- 실제 생성은 `src/main.js:6364-6386`에서 `assetCorePrompt` 원문을 사용한다.
- 출력 W/H는 payload와 서버 정규화에는 있지만 Provider에는 종횡비만 전달된다.
- 클라이언트의 `attack4`, `jump4` 등은 서버 action enum과 맞지 않아 idle로 정규화될 수 있다.
- `runPixelWorkflow()`는 `result.img`를 기대하지만 `generateAiAsset()`은 다른 객체 형태를 반환해 후처리가 중단된다.

### 4. 메뉴 수가 지원 능력보다 많다

화면에는 32개 subtype이 있지만 AssetResult, 생성, QA와 export의 공통 교집합은 12개뿐이다. UI, 서버, 결과 저장과 내보내기가 서로 다른 taxonomy를 사용한다. 사용자는 동작하지 않는 내부 계약까지 제품 기능으로 오해하게 된다.

### 5. 기존 검증 결과가 실제 품질을 증명하지 못한다

과거 Phase 25는 액션별 한 번 생성한 결과를 alpha, frame count와 cleanup 중심으로 8/8 성공으로 집계했다. 실제 동작 의미, 캐릭터 동일성, 루프와 반복 실행 성공률은 측정하지 않았다. 보관 JSON에는 일부 `cleanup_qa.pass=false`인 응답도 있어 상위 요약 집계와 세부 결과가 일치하지 않는다.

## Hermes 기본 전략

직접 API는 비용이 발생하므로 기본값으로 두지 않는다. Hermes를 유지하되 **의존 방향**을 바꾼다.

현재 문제:

    Asset Studio -> Hermes 저장소의 private Python 모듈과 helper 직접 import

목표:

    Asset Studio -> AssetProvider 인터페이스 -> Hermes Adapter
                                      -> Direct API Adapter (선택)
                                      -> Local Adapter (향후)

필수 Provider 계약:

- `health()` — 설치, 인증과 생성 가능 여부
- `capabilities()` — reference, mask edit, aspect, seed 지원 여부
- `generate(request)` — 후보와 provenance 반환
- `edit(request)` — 선택 영역 또는 reference 기반 수정
- `review(request)` — 선택적 의미·시각 평가

원칙:

- Hermes가 기본이며 직접 API는 설정하지 않으면 UI에도 강조하지 않는다.
- 하드코딩된 사용자 홈 경로를 제거하고 설정·환경 변수로 주입한다.
- Provider 응답은 Asset Studio 소유의 정규 결과 타입으로 변환한다.
- Provider가 없어도 편집, 프로젝트 로드, 로컬 QA와 export는 유지한다.
- private helper import를 Adapter 밖으로 노출하지 않는다.

## 목표 생성 파이프라인

### 공통 상태 모델

    Requested
      -> GeneratedCandidates
      -> LocalQaPassed | LocalQaFailed
      -> VisualQaPassed | VisualQaFailed
      -> UserApproved | Rejected
      -> Edited
      -> ExportReady

- 자동 채택을 제거한다.
- 실패 결과도 원인과 설정을 보존한다.
- 채택은 승인된 후보에만 허용한다.
- 실패한 단계만 다시 실행할 수 있게 job을 작게 나눈다.

### 생성 레시피

기본 화면은 임의의 기술 파라미터가 아니라 검증된 레시피를 고르게 한다.

| V1 레시피 | 생성 단위 | 핵심 검증 | 상태 |
| --- | --- | --- | --- |
| 정적 Sprite/Object | 단일 투명 이미지 후보 | 실루엣, 알파, 크기, 팔레트 | 우선 구현 |
| Actor Animation | identity → direction → beat/frame | 동일성, 동작, loop, pivot | 우선 구현 |
| UI Component | 컴포넌트와 상태 묶음 | 동일 canvas, safe area, 9-slice, text-free | 우선 구현 |
| VFX Sequence | 프레임 후보와 시간 순서 | envelope, pivot, 진행, loop/one-shot | 우선 구현 |
| Tile/Autotile | topology 규칙 기반 atlas | seam, adjacency, importer | Lab에서 검증 후 승격 |

미검증 subtype을 기본 메뉴에 넣지 않는다. 레시피마다 실제 생성, QA, 편집과 export가 모두 연결됐을 때만 Production으로 승격한다.

## 스프라이트 생성 재설계

### 생성 순서

1. 캐릭터 설명이나 reference로 identity 후보를 만든다.
2. 사용자가 identity master를 승인한다.
3. 출력 프로필이 요구하는 방향별 master pose를 만든다.
4. 액션을 `idle`, `walk`, `attack` 같은 이름이 아니라 pose beat로 분해한다.
5. 각 beat/frame에 identity, direction master, 인접 프레임과 고정 pivot guide를 함께 제공한다.
6. 프레임별 후보를 선택하거나 실패한 프레임만 재생성한다.
7. 로컬 코드가 canvas, root, 팔레트와 셀 배치를 결정적으로 정규화한다.
8. 애니메이션 재생 QA와 사용자 승인을 거쳐 sheet 또는 개별 프레임으로 export한다.

예시 beat:

- idle: settle → rise → settle → fall
- walk: contact L → down → passing → contact R → down → passing
- attack: anticipation → wind-up → strike → impact → recovery → return

프레임 수는 출력 프로필이 정하며 위 예시는 의미 검증용 기본 구조다.

### QA 계층

결정적 로컬 QA:

- 정확한 W/H, 알파, 방향·프레임 수와 순서
- 빈 프레임, 중복 프레임과 경계 잘림
- root/contact, bbox와 scale 변화 한계
- 팔레트·외곽선 이탈
- loop closing 차이
- walk 지지발 교대와 attack 단계별 변화량

의미·시각 QA:

- 같은 캐릭터인가
- 요청 방향과 동작으로 읽히는가
- 장비 위치와 손잡이가 유지되는가
- 프레임 사이 형태가 무너지지 않는가
- loop나 impact가 시각적으로 자연스러운가

로컬 QA 탈락 결과에는 추가 에이전트 검수를 사용하지 않는다. 비용과 지연이 큰 평가는 로컬 조건을 통과한 후보에만 적용한다.

## 기본 UI 축소안

기본 생성 화면에는 다음만 둔다.

1. 에셋 레시피
2. 출력 프로필
3. 만들 대상 설명
4. 선택적 reference
5. 후보 수와 생성 버튼

생성 후에는 하나의 Candidate Tray에서 QA, 비교, 재시도, 승인과 편집 진입을 처리한다.

다음 항목은 Advanced/Profile/Lab으로 이동한다.

- 행·열, 방향 slug, 폴더명과 파일명 같은 출력 계약
- 크로마와 세부 후처리 임계값
- 미완성 Tile topology와 Object multi-state 옵션
- 내부 taxonomy alias
- synthetic actor preview
- 중복 생성·배치·방향 전용 버튼
- 숨겨진 legacy pixel controls

## 재사용할 구현

- Fabric.js 캔버스와 레이어 기반 수동 수정
- `src/main.js:144-280` AssetResult 저장·검증 기반
- `src/main.js:288-354` 이미지 preflight, rollback와 history
- `server.py:2226-2305` 마스크 결과의 제한 영역 합성 패턴
- 프로젝트 저장과 히스토리
- PNG encode, ZIP, CRC, SHA와 inventory 유틸
- 이미 구현된 geometry·budget 검사 중 실제 레시피 계약과 맞는 부분

단, AssetResult는 후보·QA·승인 상태를 표현하도록 확장하고 자동 채택과 결합된 기존 상태 전이는 수정해야 한다.

## 실제 생성 검증 계획

### Golden Job 세트

최소 네 계열을 고정한다.

- 정적 투명 아이템 또는 오브젝트
- 동일 캐릭터의 idle, walk, attack
- normal/hover/pressed/disabled UI 컴포넌트
- one-shot VFX

`dungeon-cleanup-inc` 자료는 Actor와 UI job의 한 fixture로 포함하되 전부가 되지 않게 서로 다른 스타일·규격의 fixture를 추가한다.

### 반복 평가

- 같은 manifest로 각 job을 여러 번 생성한다.
- 초기 개발은 job당 5회, release 후보는 job당 최소 20회 평가한다.
- 기존 파이프라인과 새 파이프라인을 같은 기준으로 비교한다.
- 비트 단위 동일 출력은 요구하지 않는다. 대신 요청, reference, Provider, 모델, 후처리와 QA 버전을 재현 가능하게 기록한다.

### 측정값

- Provider 응답 성공률
- 결정적 QA 통과율
- 의미 QA 통과율
- 사용자 최종 승인률
- 승인 하나를 얻기까지 필요한 후보 수
- 실패 프레임 재생성 횟수
- 승인 후 수동 수정 시간
- identity, action, direction과 loop 점수
- manifest와 export 계약 일치율

“샘플 한 번 생성 성공”은 검증 완료로 인정하지 않는다.

## 실행 순서

### Phase 0 — 평가 기준 고정

- Golden Job, 실패 fixture와 사람 검수 rubric 작성
- 현재 파이프라인 baseline 반복 측정
- 생성 성공과 품질 성공 상태 분리 테스트 작성

### Phase 1 — 공통 계약 정리

- 단일 taxonomy와 recipe registry
- 정규 GenerationRequest, Candidate, QAResult, OutputProfile 타입
- Hermes Adapter와 시작 health check
- 자동 채택 제거, Candidate Tray 통합

### Phase 2 — 정적 에셋 수직 완성

- 정적 Sprite/Object 한 경로를 생성부터 export까지 완성
- 로컬 alpha, canvas, palette QA 연결
- 반복 성공률을 측정해 공통 파이프라인 검증

### Phase 3 — Actor Animation 재구축

- identity와 direction master
- beat/frame 후보 생성과 부분 재생성
- pivot, loop, action QA
- 개별 프레임과 sheet export profile

### Phase 4 — UI와 VFX

- 동일 상태 canvas와 9-slice 계약
- VFX frame progression과 pivot 계약
- 검증된 subtype만 Production에 추가

### Phase 5 — 정리와 범위 확장

- 회귀 테스트를 근거로 중복·죽은 코드 삭제
- Tile/Autotile은 topology 평가를 통과할 때만 Lab에서 승격
- 추가 엔진·게임 출력 프로필 도입

## 완료 조건

- 기본 생성 화면에서 미완성 메뉴가 보이지 않는다.
- 같은 recipe/profile 요청을 반복해 품질 성공률을 수치로 확인할 수 있다.
- QA 실패 결과는 자동 채택·export되지 않는다.
- idle, walk, attack이 이름뿐 아니라 동작·동일성·loop 기준을 통과한다.
- 실패한 프레임이나 상태만 재생성할 수 있다.
- Hermes가 기본 Provider지만 내부 구현 교체가 제품 코드 전체에 퍼지지 않는다.
- `dungeon-cleanup-inc`를 포함한 서로 다른 출력 프로필이 같은 공통 파이프라인을 사용한다.
- 기존 편집 기능은 생성 결과의 마지막 보정 단계로 그대로 사용할 수 있다.

## 현재 검증 한계

- 이번 작업에서는 Chrome, 브라우저와 서버를 실행하지 않았다.
- Hermes 또는 유료 API를 호출하지 않아 실제 새 이미지 품질 평가는 아직 수행하지 않았다.
- 현재 보관된 Phase 25 실제 PNG가 없어 당시 시각 품질은 재평가할 수 없다.
- 따라서 코드상 원인과 목표 구조의 확신도는 높지만, 새 파이프라인의 품질 목표값은 구현 후 반복 생성으로 보정해야 한다.
