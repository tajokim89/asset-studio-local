---
title: "Asset Studio 기존 문서 통합 및 정리 판정"
tags: ["asset-studio", "documentation", "consolidation", "cleanup", "dead-code", "ui-audit", "decision"]
created: 2026-07-11T23:58:55+09:00
updated: 2026-07-11T23:58:55+09:00
sources: ["docs/plans/2026-07-10-ai-first-asset-studio-product-spec.md", "docs/plans/2026-07-10-ai-first-asset-studio-work-plan.md"]
links: ["asset-studio-최신-제품-방향-및-생성-검증-재설계.md", "asset-studio-제품-목적과-스프라이트-합격-기준.md", "asset-studio-이미지-생성-파이프라인-감사-보고서.md", "asset-studio-저장소-감사-및-개선-백로그.md"]
category: decision
confidence: high
schemaVersion: 1
---

# Asset Studio 기존 문서 통합 및 정리 판정

> 목적: 이전 보고서와 계획을 모두 대조해 현재도 사용할 내용, 최신 방향에 합칠 내용, 폐기하거나 역사 자료로만 둘 내용을 구분한다.
> 범위: 문서와 코드 근거 검토만 수행했다. 제품 코드는 수정하지 않았다.

## 최종 판정

기존 분석의 **코드 결함 근거와 편집기 재사용 판단은 대부분 유효**하다. 잘못된 부분은 `dungeon-cleanup-inc`를 유일한 제품 목표로 삼은 전제다.

따라서 기존 문서를 전부 버리지 않는다.

- 범용 제품 정의와 새 생성·검증 구조는 [[asset-studio-최신-제품-방향-및-생성-검증-재설계]]로 통합한다.
- 짧은 제품 결정과 스프라이트 공통 합격 기준은 [[asset-studio-제품-목적과-스프라이트-합격-기준]]에 둔다.
- 상세 코드 근거는 기존 감사·백로그에 남긴다.
- 던전 전용 규격과 실행 순서는 출력 프로필 사례 또는 역사 자료로 강등한다.

## 문서별 처리

| 문서 | 유지 | 수정·통합 | 폐기 또는 역사화 |
| --- | --- | --- | --- |
| 제품 목적과 스프라이트 합격 기준 | 액션 의미, 동일성, loop, pivot 기준 | 범용 도트 게임 도구와 Hermes 기본 결정으로 재작성 | 던전 전용 목적, 던전 규격을 최종 기준으로 둔 문장 |
| 저장소 감사 및 개선 백로그 | 반환 계약, taxonomy, 자동 채택, QA 단절, UI·보안·환경 근거 | 우선순위를 범용 recipe/profile 기준으로 재해석 | 던전 importer 완료를 제품 전체 완료 조건으로 둔 부분 |
| 이미지 생성 파이프라인 감사 보고서 | P0 결함, 스프라이트 분해 생성, QA 계층, 편집기 재사용, 삭제 후보 | 던전 규격을 `actor-v1` 예제로 전환 | 던전만을 위한 export·action playback을 제품 필수 조건으로 둔 결론 |
| AI-first 제품 명세 | AI 우선, 후보 비교, 명시적 채택, 편집 보조라는 원칙 | 상세 설정은 Output Profile과 Advanced로 이동 | 모든 subtype·기술 설정을 기본 UI 요구사항으로 해석하는 방식 |
| AI-first 작업 계획 | family 계약, Result Tray, Style Profile, QA 의도 | 실제 반복 생성 평가를 선행하는 새 계획으로 대체 | 정적 문자열·화면 구조 완료를 실제 품질 완료로 간주한 단계 |
| Phase 25 보고서와 JSON | 과거 요청·응답·실패 형태 | evaluation fixture로 추출 | 1회 생성 8/8을 품질 검증으로 간주한 결론 |

## 그대로 같이 사용할 코드

### 편집과 프로젝트 기반

- Fabric.js 캔버스, 레이어와 선택 편집
- 브러시, 지우개, 변형과 간단한 색 보정
- 프로젝트 저장, 히스토리와 rollback
- 기존 이미지를 불러와 수동 수정하는 흐름

생성 파이프라인을 다시 만들어도 이 영역은 마지막 보정 작업대로 유지할 수 있다.

### 결과 안전장치

- `src/main.js:144-280`의 AssetResult 저장·JSON 검증
- `src/main.js:288-354`의 이미지 preflight와 transactional adoption
- PNG, ZIP, CRC, SHA와 파일 inventory 유틸

AssetResult 구조 자체는 재사용하되 후보, QA, 승인, 편집, export-ready 상태를 명시하도록 확장한다.

### 제한 영역 편집

`server.py:2226-2305`의 마스크 결과를 로컬에서 제한 영역에만 합성하는 패턴은 유지한다. 모델이 전체 이미지를 다시 결정하지 않고 애플리케이션이 수정 경계를 강제한다는 점이 새 구조와 잘 맞는다.

### 결정적 검사

기존 geometry, alpha, canvas, frame count, ZIP 검사는 recipe 계약과 맞는 것만 QA 라이브러리로 모은다. HTTP 응답 성공 여부와 분리하고 Candidate gate에서 호출한다.

## 하나로 합쳐야 할 중복 영역

| 현재 분산 영역 | 통합 대상 | 목표 |
| --- | --- | --- |
| subtype 상수, 결과 allowlist, 서버 enum, export descriptor | `RecipeRegistry` | 지원 기능의 단일 진실 공급원 |
| Result Tray, gallery, pixelResultSlots | `CandidateTray` | 비교·QA·승인 상태 한 곳에서 관리 |
| `generateAiAsset`, 선택 이미지 생성, 방향/배치 워크플로 | `GenerationJob` | 같은 요청·결과 타입 사용 |
| family prompt, pixel prompt, raw core prompt | `RecipePromptBuilder` | 화면 미리보기와 실제 Provider 요청 일치 |
| family별 흩어진 QA와 미사용 gate | `QaPipeline` | 실패 시 채택·export 차단 |
| ZIP/export별 별도 metadata | `OutputProfileExporter` | manifest와 경로 규칙 통합 |
| Hermes private import와 보조 client | `HermesProviderAdapter` | Provider 교체·health check 경계 |

이 통합은 새 추상화를 많이 만드는 작업이 아니다. 이미 존재하는 여러 계약 중 하나를 정본으로 정하고 나머지를 삭제하는 작업이다.

## 삭제 또는 격리 후보

삭제 전에는 실제 호출 관계와 과거 프로젝트 fixture를 테스트로 고정한다.

### 강한 삭제 후보

| 후보 | 근거 | 삭제 조건 |
| --- | --- | --- |
| 존재하지 않는 `aiPrompt`로 쓰는 호환 경로 | 상세 prompt가 실제 생성에 연결되지 않음 | 실제 prompt builder 통합 후 |
| `runPixelWorkflow`의 현재 구현 | 반환 타입 불일치로 후처리 조용히 종료 | 새 job 통합 테스트 통과 후 |
| 숨겨진 legacy pixel controls | 숨은 DOM을 상태 저장소처럼 사용 | 과거 프로젝트 migration fixture 확보 후 |
| 미사용 `/api/upload-data-url`, `UPLOADS`, `PROJECTS` | 프론트·테스트 호출 없음 또는 mkdir만 수행 | 전체 참조·HTTP 회귀 확인 후 |
| 사용하지 않는 helper/import/CSS | 정적 참조 없음 | Fabric 동적 클래스 제외 후 |
| 특정 캐릭터용 `generate_*_once.py` | 재사용 불가, 절대 경로 포함 | 실패 사례를 fixture로 추출 후 |
| 중첩 복제 `asset-studio-local/asset-studio-local/scripts` | 동일 목적 스크립트 중복 | 유일 산출물 여부 확인 후 |

### 연결하지 않으면 삭제할 후보

- `route_family_qa`
- `resultWalkQaGate`
- `build_sprite_action_prompt`
- `slice_effect_sequence`
- `sprite_action_matrix_for_ui`
- `actorFramesFromImageData`
- `objectFamilyMetadata` 기반 export facade

이 코드는 아이디어는 유효하지만 현재 제품 경로와 끊겨 있다. 새 `QaPipeline`, Actor recipe 또는 Exporter에서 실제로 사용하지 않으면 실험 문서로 옮기고 제품 코드에서는 제거한다.

### 교체 대상

- 완성 스프라이트 시트 한 장 생성
- 전역 5방향 생성 + 3방향 미러 정책
- global green chroma 기본값
- Provider 성공 직후 자동 adopt
- synthetic actor 프레임을 production preview/export로 사용하는 흐름
- 생성 결과 하나를 여러 Object state가 있는 것처럼 포장하는 흐름
- geometry mismatch여도 성공 상태를 반환하는 family 후처리

## UI에서 기본 노출하지 않을 부분

현재 UI에는 실제 end-to-end 지원보다 많은 subtype과 기술 설정이 보인다. 기본 화면에서는 다음을 제거하거나 옮긴다.

### Output Profile로 이동

- W/H, 방향 순서, frame count와 FPS
- 행·열, 파일명과 폴더명
- pivot, root, contact baseline
- palette, outline와 mirror policy

### Advanced로 이동

- 세부 후처리 임계값
- Provider/model별 옵션
- reference strength와 실패 재시도 정책
- raw manifest와 prompt 진단 정보

### Lab으로 이동

- 아직 importer·topology 검증이 없는 Tile/Autotile
- 실제 state 이미지 생성이 없는 Object multi-state
- synthetic Actor preview
- production 계약이 없는 subtype과 alias

### 삭제

- 같은 동작을 다른 상태로 실행하는 중복 생성 버튼
- 사용자가 접근할 수 없는 숨겨진 호환 UI
- “B안 적용됨” 같은 개발 상태 문구와 seed demo
- 존재하지 않는 DOM을 향한 no-op 이벤트 연결

## 유지하지 않을 잘못된 전제

- 범용 도구가 아니라 던전 전용이라는 전제
- 88×88, 8방향, Godot 폴더 구조가 제품 전체 기본값이라는 전제
- attack 생성이 `dungeon-cleanup-inc` playback 구현과 함께 완료돼야 제품 기능이라는 전제
- 한 family의 1회 성공이 범용 생성 품질을 증명한다는 전제
- 화면에 옵션이 있으면 지원 기능이라는 전제
- 서버가 HTTP 200을 반환하면 에셋이 합격이라는 전제
- 모델이 만든 한 장을 deterministic postprocess만으로 production sprite로 바꿀 수 있다는 전제

## 테스트 정리 방향

### 줄일 테스트

- 함수명이나 DOM ID 존재만 확인하는 테스트
- cache-busting 버전 문자열을 고정하는 테스트
- 숨겨진 legacy 요소를 계속 유지하게 만드는 문자열 테스트
- QA 함수가 존재하는지만 확인하고 실제 gate 연결은 보지 않는 테스트

### 추가할 테스트

- UI recipe 선택 → canonical request
- request → server normalize → Provider adapter
- Provider artifact → local QA → semantic QA
- QA fail → adopt와 export 차단
- 승인 후보 → 편집 → manifest/export
- 모든 Production recipe의 end-to-end 계약 순회
- 과거 프로젝트 fixture migration
- 동일 manifest 반복 생성 평가 집계
- 출력 프로필별 importer 또는 package 검증

정리 작업은 테스트를 먼저 바꾼 뒤 한 냄새 단위로 삭제한다. 모놀리스를 먼저 파일 단위로 분해하지 않는다.

## 향후 구현 단위

1. 평가 fixture와 baseline을 먼저 고정한다.
2. taxonomy를 `RecipeRegistry` 하나로 통합한다.
3. 정규 request/candidate/QA/profile 타입을 만든다.
4. Hermes 호출을 Provider Adapter 뒤로 옮긴다.
5. 자동 채택을 제거하고 Candidate Tray를 하나로 합친다.
6. 정적 에셋 한 경로를 끝까지 완성해 공통 구조를 검증한다.
7. Actor를 identity/direction/beat/frame 파이프라인으로 재구축한다.
8. UI와 VFX recipe를 같은 구조 위에 추가한다.
9. 회귀 근거가 확보된 레거시·중복 코드를 삭제한다.
10. Tile은 평가 결과가 기준을 통과할 때 Production으로 승격한다.

## 문서 정본 순서

1. [[asset-studio-최신-제품-방향-및-생성-검증-재설계]] — 현재 제품·구조·검증 방향
2. [[asset-studio-제품-목적과-스프라이트-합격-기준]] — 짧은 제품 결정과 공통 합격 기준
3. 이 문서 — 기존 자료의 유지·폐기 판정
4. [[asset-studio-이미지-생성-파이프라인-감사-보고서]] — 상세 코드와 픽셀 근거
5. [[asset-studio-저장소-감사-및-개선-백로그]] — 전체 저장소 결함 목록

기존 `docs/plans`와 `docs/history`는 설계 의도와 과거 시도 근거로만 사용하며 최신 결정과 충돌할 때 위 순서를 우선한다.
