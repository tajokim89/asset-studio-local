# Asset Family Production Overhaul — Phase 3 / Milestone G 보고서

- **검증일:** 2026-07-11
- **프로젝트:** `/Users/tajokim/asset-studio-work`
- **보고 범위:** Milestone G — Result Tray / Adopt / Project Restore (`G1`–`G4`)
- **최종 판정:** **PASS — Phase 3**
- **다음 전체 회귀 게이트:** Milestone J

## 1. 판정 요약

Phase 3는 생성 결과를 곧바로 Fabric canvas에 덮어쓰던 흐름을, 검증 가능한 canonical Result 수명주기로 분리했다. 모든 asset family 결과는 공통 envelope에 기록되고, tray에서 선택·실제 비교·거부·재시도를 거친 뒤 사용자가 명시적으로 채택한다. 채택 상태, library, provenance, 선택/비교 상태와 관련 history는 Project v2에 저장되고 원자적으로 복원된다.

`G1`부터 `G4`까지 완료했으며, 최종 focused 자동 검증 **92 passed**, JavaScript syntax 검사 `node --check` **PASS**, whitespace/error 검사 `git diff --check` **PASS**를 확인했다. localhost 브라우저에서는 서로 다른 두 deterministic 결과의 생성부터 선택·비교·library 채택·저장·초기화·복원·Undo/Redo까지 실제 경로로 확인했고 console JavaScript error는 **0**이었다.

따라서 Phase 3의 범위는 정직하게 **PASS**다. 단, 이번 검증에서 유료 provider를 호출하지 않았고 deterministic data URL을 사용했으므로 실제 provider 이미지 품질을 승인한 것은 아니다. 저장소 전체 full suite는 후속 Milestone J에서 수행한다.

## 2. 완료 범위

| Task | 목표 | 완료 근거 | 판정 |
|---|---|---|---|
| G1 — Canonical Result model | 모든 family의 공통 결과 envelope와 family별 metadata | DOM-independent model/store, 상태 전이·deep copy·중복/비정상 입력 거부 | PASS |
| G2 — Result tray / select / compare | canvas 즉시 교체 없이 preview·선택·비교·재시도·거부 | canonical tray, 실제 side-by-side 비교와 metadata, 접근 가능한 조작 | PASS |
| G3 — Adopt flow | new layer / replace source / library의 명시적 채택 | preflight, compact provenance, 단일 atomic history commit, rollback, 실제 Undo/Redo | PASS |
| G4 — Project v2 persistence | result 생태계와 history를 저장·원자 복원 | fail-closed graph validation, Fabric 5/6 async load, legacy defaults | PASS |

Phase 3는 style profile, provider별 family QA, export 확대 또는 실제 유료 생성 품질 검증을 포함하지 않는다. 이 항목들은 후속 milestone 범위다.

## 3. 구현 아키텍처

### 3.1 Canonical Result와 store

Result는 최소한 다음 정보를 하나의 JSON-safe envelope로 소유한다.

- identity/status: `id`, `family`, `type`, `status`, timestamps, structured `error`
- generation evidence: `sourceRequest`, `normalizedContract`, `preview`, `qaSummary`, `artifacts`
- disposition: `adopted`, `rejected`, 각 상태 timestamp

생성자는 입력을 deep copy하며 injected clock/id를 지원한다. 상태 전이는 pending/succeeded/failed와 adopted/rejected 불변식을 검사한다. 성공 결과는 durable preview/artifact가 없으면 거부하고, unsafe/non-JSON/prototype 입력도 fail-closed 처리한다. Store는 DOM과 독립적이며 ID 중복을 허용하지 않고, snapshot/restore 시 values뿐 아니라 `selectedId`와 `compareIds`의 모든 참조 및 중복을 선검증한 뒤 한 번에 교체한다.

### 3.2 Tray와 실제 비교

생성 성공은 canvas를 즉시 교체하지 않고 canonical store와 tray에 추가된다. Tray가 preview/select/compare/retry/reject/adopt의 단일 UI 표면이므로 별도 duplicate preview 상태를 만들지 않는다. Compare는 단순 토글 표식이 아니라 선택한 두 결과의 이미지와 family/type/status/QA 등 실제 metadata를 side-by-side로 렌더링한다.

### 3.3 명시적 채택과 provenance

`adoptResult`는 다음 세 모드를 지원한다.

1. `new-layer`: 결과 이미지를 provenance가 붙은 새 Fabric layer로 추가
2. `replace-source`: 원본 관계를 보존하면서 source layer를 명시적으로 교체
3. `library`: canvas를 변경하지 않고 reusable library entry로 채택

채택 전에는 succeeded/non-rejected/non-adopted 상태, QA, contract, artifact를 검사하고, data URL의 MIME·byte/pixel·decode·timeout budget을 preflight한다. 채택 자체는 provider/API를 호출하지 않는다. Canvas에는 전체 request/contract를 중복 저장하지 않고 `resultId`, `resultFamily`, `resultType`, `replacesLayerId` 등 compact reference provenance만 직렬화한다.

Canvas, Result store, library, adoption record를 하나의 논리적 transaction으로 취급한다. 성공 시 history commit은 정확히 한 번이며, 어느 단계든 실패하면 사전 snapshot으로 rollback한다.

### 3.4 Project v2와 history restore

Project v2는 기존 형식에 additive하게 다음을 저장한다.

- canonical results
- selected result와 compare IDs
- asset library와 adopted 상태
- family contract, QA, artifact references
- history entry별 Result snapshot, library, adoption records

Loader는 JSON graph와 Result/canvas/history/library의 모든 상호 참조를 canvas mutation 전에 검증한다. 이후 Fabric canvas, editor state, Result store, library, adoption record를 원자적으로 hydrate하며 실패 시 전체 rollback한다. Legacy project는 빈 Result/library 기본값으로 열린다. Fabric 6 Promise API와 Fabric 5 callback API는 공통 async adapter를 통하며, 호출자는 완료를 실제로 `await`한다.

## 4. 자동 검증 근거

### 4.1 최종 focused 실행

Phase 3 Result model, tray, adoption, Project v2 round-trip 및 관련 history/static 회귀를 묶은 최종 focused 실행 결과는 다음과 같다.

- **92 passed**
- **failed 0**
- `node --check`: **PASS**
- `git diff --check`: **PASS**

핵심 검증 파일은 다음과 같다.

- `tests/test_asset_result_tray.py`
- `tests/test_asset_result_adoption.py`
- `tests/test_asset_result_project_roundtrip.py`
- `tests/test_phase11_project_v2_static.py`
- 관련 history/static focused tests

### 4.2 검증한 불변식

- 5개 대표 family/type이 동일 envelope와 정확한 family-specific contract를 유지한다.
- Result 생성/전이/store는 DOM 없이 Node runtime에서 동작한다.
- malformed status/timestamp, non-JSON, prototype key, nondurable success를 거부한다.
- store duplicate ID와 잘못된 selection/compare snapshot을 원자적으로 거부한다.
- adopted/rejected는 상호 배타적이다.
- 채택 세 모드, preflight budget, compact provenance, 단일 history commit과 rollback이 존재한다.
- Project v2는 duplicate/dangling/mismatched reference와 잘못된 adopted timestamp를 거부한다.
- file byte budget은 `JSON.parse` 전에 검사한다.
- Fabric 5 callback과 Fabric 6 Promise load를 모두 실제 async 순서로 기다린다.
- history load 성공/실패 모두 canvas/store/library/index/`suppressHistory` 원자성을 지킨다.
- keyboard Undo/Redo의 async rejection을 처리한다.

위 **92 passed**는 focused Phase 3 검증 수치이며 저장소 전체 full regression 수치로 확대 해석하지 않는다.

## 5. localhost 브라우저 검증

비용 없는 deterministic data URL fixture로 실제 UI와 runtime을 검증했다.

### 5.1 생성·선택·비교

- succeeded 결과 2개를 생성:
  - `r1`: **sprite / character**
  - `r2`: **tile / terrain**
- 두 결과 모두 deterministic data URL을 사용했다.
- 생성 직후 canvas object count는 **1**로 유지되어 즉시 교체가 없었다.
- `r1`을 선택하고 `r1`/`r2`를 compare했다.
- compare 영역에서 두 결과 이미지와 실제 side-by-side metadata를 확인했다.

### 5.2 채택·저장·초기화·복원

- `r1`을 **library** 모드로 채택했다.
- `await buildProjectV2()` 결과 저장 크기: **8,801 bytes**
- runtime 상태를 clear한 뒤 `await loadProjectV2(...)`를 수행했다.
- 복원 후 확인값:
  - result count: **2**
  - selected result: **`r1`**
  - compare count: **2**
  - `r1.adopted`: **true**
  - QA: **PASS**
  - library entry의 result: **`r1`**
  - history position/count: **2 / 2**
  - canvas object count: **1** — 저장 전과 동일

즉, Result graph와 선택/비교/QA/adopt/library/history가 보존되면서 library 채택이 canvas를 불필요하게 변경하지 않았다.

### 5.3 실제 Undo / Redo

복원된 브라우저 runtime에서 실제 history 조작을 수행했다.

| 상태 | `r1.adopted` | library count | history index |
|---|---:|---:|---:|
| 채택 후 | true | 1 | 1 |
| Undo | false | 0 | 0 |
| Redo | true | 1 | 1 |

Redo 완료 뒤 `suppressHistory`는 **false**였고, console JavaScript error는 전체 시나리오에서 **0**이었다. 이는 버튼 존재나 static token 검사가 아니라 Result와 library가 canvas history와 함께 실제로 왕복한 runtime 근거다.

## 6. 독립 리뷰에서 발견하고 수정한 결함

초기 구현을 그대로 승인하지 않고 독립 검토에서 다음 결함을 발견해 수정했다.

1. **History atomicity:** canvas만 되돌아가고 Result/library가 어긋날 수 있던 경로를 통합 snapshot과 rollback으로 교정했다.
2. **모든 history reference validation:** 현재 canvas뿐 아니라 저장된 history entry의 result/replacement reference까지 전부 검증하도록 확대했다.
3. **실제 compare view:** compare 상태 표식만 있던 수준을 두 preview와 metadata의 실질적 side-by-side view로 교체했다.
4. **`store.restore` invariant:** duplicate key, key/value ID 불일치, dangling selection, duplicate/dangling compare ID를 mutation 전에 원자 거부하도록 수정했다.
5. **Fabric 6 project load Promise bug:** callback 전제 때문에 load 완료를 기다리지 못하던 문제를 version-aware Promise/callback adapter로 수정했다.
6. **누락된 `updateCanvasTransform`:** restore 이후 canvas transform 갱신 경로를 복구했다.
7. **Fabric 6 Undo path:** Undo/Redo history load도 Promise 완료를 기다리고 실패 시 이전 상태로 rollback하도록 수정했다.
8. **Keyboard rejection:** keyboard shortcut에서 발생한 async Undo/Redo rejection이 unhandled가 되지 않도록 공통 오류 처리에 연결했다.

수정 후 focused tests, syntax/diff 검사와 브라우저 round-trip/Undo/Redo를 다시 통과했다.

## 7. 보안·자원 budget·legacy 호환

- Result와 Project 입력은 JSON-safe 구조, 허용 family/type/status, timestamp, durable URL, adoption invariant를 fail-closed 검증한다.
- prototype-bearing 객체, duplicate identity, dangling/mismatched provenance와 library/history 참조를 거부한다.
- Project file byte 제한을 parse 전에 적용한다.
- 이미지 preflight는 허용 MIME, encoded/decoded bytes, pixel 수와 decode timeout을 제한한다.
- adoption은 provider/API call 없이 로컬 Result artifact만 사용하므로 중복 유료 요청을 만들지 않는다.
- Canvas object에는 compact reference만 넣어 request/contract 전체 복제로 인한 project/history 팽창을 줄인다.
- 기존 Project v2 필드는 additive하게 유지하고, Result 필드가 없는 legacy project는 빈 Result ecosystem으로 복원한다.
- 실패한 load/adopt/history 작업은 partial mutation을 남기지 않고 이전 canvas/editor/store/library/history 상태로 rollback한다.

## 8. 잔여 위험과 증거 경계

1. **유료 provider 미검증:** Phase 3 최종 검증 중 paid provider call은 없었다. deterministic data URL은 상태 수명주기와 UI/persistence를 검증하지만 실제 생성 모델의 미술 품질·응답 변동·외부 장애를 검증하지 않는다.
2. **Focused suite 경계:** 최종 **92 passed**는 Phase 3 집중 회귀다. 저장소 전체 suite는 후속 Milestone J에서 실행·판정한다.
3. **브라우저 fixture 경계:** 두 family의 contract/metadata 분리를 확인했지만 모든 family와 대형 실제 artifact 조합을 브라우저에서 소진한 것은 아니다.
4. **장기/대형 project:** 현재 byte/pixel budget과 validation은 안전 경계를 제공하지만, 매우 긴 history와 대형 durable data URL을 포함한 장기 사용의 성능·저장 크기는 별도 stress 검증 대상이다.
5. **Legacy 다양성:** legacy 기본값과 기존 Project v2 경로는 자동 검증했지만 현존하는 모든 과거 사용자 파일 표본을 수집해 migration 검증한 것은 아니다.

## 9. 최종 결론

**Milestone G / Phase 3: PASS.**
**G1–G4: COMPLETE.**
**Focused verification: 92 passed; `node --check` PASS; `git diff --check` PASS.**
**Browser round-trip and actual Undo/Redo: PASS; console JavaScript errors 0.**

이 판정은 canonical Result model, 실제 tray compare, 명시적·원자적 adoption, Project v2 fail-closed restore, Fabric 5/6 async history/load 호환과 localhost runtime 증거에 근거한다. 유료 provider 품질과 전체 저장소 full suite는 이 판정에 포함하지 않으며, 후자는 Milestone J의 후속 게이트로 남긴다.
