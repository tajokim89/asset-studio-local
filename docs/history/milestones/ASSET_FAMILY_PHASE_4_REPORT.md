# Asset Family Production Overhaul — Phase 4 / Milestone H 보고서

- **검증일:** 2026-07-11
- **프로젝트:** `/Users/tajokim/asset-studio-work`
- **보고 범위:** Milestone H — Project Style Profile (`H1`–`H4`)
- **최종 판정:** **PASS — Phase 4**
- **다음 단계:** Milestone I / Phase 5 Family QA Providers / Export

## 1. 판정 요약

Phase 4는 프로젝트 공통 미술 제약을 canonical Style Profile로 정의하고, 선택 family에 맞게 해석한 profile을 생성 prompt에 전달하며, profile과 family별 작성 중 상태를 Project v2에 보존하는 범위를 완료했다.

브라우저와 서버는 동일한 `asset-studio.style-profile/v1` 계약을 적용하며 malformed profile을 엄격히 거부한다. Sprite, Tile, UI, Object의 네 prompt에는 각각 선택 family의 override만 반영된 resolved profile이 전달되고, 다른 family의 `family_overrides` 값은 유출되지 않는다. Project v2는 canonical `styleProfile`, 정확히 네 개의 allow-listed `familyDrafts`, `selectedFamily`, `createdAt`, `updatedAt`을 보존한다. Legacy v1은 계속 load 가능하며, 검증 또는 hydrate 실패 시 기존 상태로 원자 rollback한다.

독립 H3 리뷰 결과는 **PASS**, critical/high 이슈는 **0**, focused 검증은 **65 passed**였다. H3 checklist의 문서-only 변경 직전 최신 full suite는 **810 passed, 53 warnings**였고, warning은 Pillow deprecation과 duplicate ZIP test warning에 한정됐다. `node --check`, Python `py_compile`, `git diff --check`도 모두 **PASS**였다.

따라서 H1–H3 구현과 H4 보고 범위는 **PASS**다. 다만 Style Profile은 생성 제약을 구조화할 뿐 결과의 시각적 품질을 보장하지 않으며, family draft 보존 범위도 의도적으로 제한돼 있다. 실제 visual QA는 Phase 5 범위다.

## 2. 완료 범위

| Task | 목표 | 객관적 완료 근거 | 판정 |
|---|---|---|---|
| H1 — Style Profile schema | 프로젝트 공통 style의 canonical schema와 fail-closed validation | browser/server `asset-studio.style-profile/v1` parity, exact fields, strict malformed/budget rejection, detached normalization | PASS |
| H2 — UI 및 family prompt 결합 | shared profile을 모든 family prompt에 적용하되 family-only 설정을 침범하지 않음 | 네 family payload/prompt가 resolved profile 수신, 선택 override만 반영, cross-family leakage 없음 | PASS |
| H3 — Project preservation | profile, family drafts, 선택 family와 project identity를 저장·복원하고 legacy 유지 | Project v2 lossless round-trip, allow-list validation, legacy v1 load, pre-mutation validation과 atomic rollback | PASS |
| H4 — Review/report | Phase 4 근거와 한계를 milestone report로 고정 | 독립 H3 review PASS 및 본 보고서 | PASS |

## 3. 구현 및 계약

### 3.1 Canonical Style Profile

Canonical schema version은 `asset-studio.style-profile/v1`이다. Profile은 identity/version/timestamps와 palette, outline, shading, material treatment, pixel density, silhouette, contrast, anti-aliasing, reference assets, forbidden elements 및 family overrides를 한 구조로 소유한다.

Browser normalizer와 server normalizer는 같은 필드 집합과 값 경계를 적용한다. 알 수 없는 필드나 family, 잘못된 enum·색상·숫자·timestamp, 비정상적인 구조와 자원 budget 초과는 기본값으로 조용히 보정하지 않고 fail-closed로 거부한다. 입력은 mutation하지 않으며 정규화 결과는 원본과 alias되지 않는다.

### 3.2 Family별 resolution과 prompt 전달

지원되는 project family는 정확히 다음 네 개다.

- `sprite`
- `tile`
- `ui`
- `object`

Resolver는 공통 style 위에 현재 선택 family의 override만 적용한다. 네 family 각각에 대해 다른 family의 override가 resolved 결과로 섞이지 않으며, 원본 canonical profile의 `family_overrides`도 mutation하지 않는다. 생성 payload는 legacy style 별칭을 병행하지 않고 하나의 canonical `style_profile`을 사용하며, family 고유 contract와 control은 Style Profile에 의해 대체되지 않는다.

### 3.3 Project v2 preservation

Project v2는 다음 Style Profile 관련 상태를 보존한다.

- canonical `styleProfile`
- 정확히 네 family key만 가진 allow-listed `familyDrafts`
- `selectedFamily`
- project identity의 `createdAt`, `updatedAt`

Family drafts는 임의 runtime/UI 상태 전체를 저장하지 않고 허용된 subtype과 control만 저장한다. 이 bounded 구조는 schema 확산과 다른 family 상태의 혼입을 막는다. 허용된 lexical input은 숫자로 재직렬화하지 않고 문자열 그대로 보존한다.

Loader는 timestamp와 profile/draft 구조를 첫 canvas mutation 전에 검사한다. 성공 시 canvas/editor/result ecosystem/style/drafts/selected family/identity를 함께 복원하며, 어느 단계든 실패하면 load 이전 snapshot으로 원자 rollback한다. 기존 Style Profile 필드가 없는 legacy Project v1도 기본 profile과 bounded draft 상태로 계속 load할 수 있다.

## 4. 변경 및 검증 대상 파일

### 4.1 Production

- `index.html` — Style Profile UI surface
- `styles/app.css` — Style Profile UI styling
- `src/main.js` — browser schema normalization/resolution, prompt integration, Project v2 save/load 및 rollback
- `server.py` — server-side canonical validation/resolution과 request boundary

### 4.2 Tests

- `tests/test_project_style_profile.py` — canonical schema, browser/server parity, malformed rejection, family resolution
- `tests/test_project_style_profile_roundtrip.py` — four-family draft lexical preservation, timestamp preflight, legacy rollback surface
- `tests/test_asset_family_payload_contract.py`
- `tests/test_asset_family_payload_runtime.py`
- `tests/test_effect_sequence_contract.py`
- `tests/test_tile_family_workflow.py`
- `tests/test_ui_family_workflow.py`
- `tests/test_object_family_workflow.py`
- 관련 Project v2/history/static 회귀 tests

### 4.3 Documentation

- `docs/plans/2026-07-10-asset-family-production-overhaul.md` — H1–H3 checklist 근거
- `docs/history/milestones/ASSET_FAMILY_PHASE_4_REPORT.md` — 본 H4 산출물

## 5. 자동 검증 근거

### 5.1 Focused 및 독립 리뷰

H3 독립 리뷰의 최종 결과는 다음과 같다.

- 판정: **PASS**
- critical: **0**
- high: **0**
- focused tests: **65 passed**, failed 0

Focused 실행은 Style Profile schema/round-trip과 family payload/prompt, 관련 Project v2 회귀를 대상으로 했다. 핵심 실행 형태는 다음과 같다.

```text
python -m pytest -q tests/test_project_style_profile.py tests/test_project_style_profile_roundtrip.py <관련 family payload/workflow 및 Project v2 focused tests>
node --check src/main.js
python -m py_compile server.py

git diff --check
```

`<...>`는 65-test focused selection에 포함된 관련 테스트 묶음을 요약한 표기이며, 하나의 복사 가능한 literal command라고 과장하지 않는다.

### 5.2 최신 full regression snapshot

H3 checklist의 문서-only 변경 직전 최신 전체 실행 결과:

- **810 passed**
- **53 warnings**
- failed: **0**
- warning 범위: **Pillow deprecations 및 duplicate ZIP test warning만 존재**
- `node --check src/main.js`: **PASS**
- `python -m py_compile server.py`: **PASS**
- `git diff --check`: **PASS**

810 수치는 문서-only checklist 변경 직전 코드 상태의 full suite snapshot이다. 본 H4 보고서 작성으로 production/test 동작이 바뀌었다는 의미는 아니다.

### 5.3 검증된 핵심 불변식

- Browser와 server가 canonical `asset-studio.style-profile/v1`을 동일하게 수용·거부한다.
- Unknown/extra keys, invalid enum/range/color/timestamp, prototype/cycle/depth/node/string/array/UTF-8 budget 위반을 fail-closed 처리한다.
- 네 family prompt 모두 resolved profile을 받는다.
- 선택 family override만 적용되며 다른 family override는 전달되지 않는다.
- Profile normalization/resolution은 입력을 mutation하거나 mutable alias를 남기지 않는다.
- Project v2는 canonical profile, 정확히 네 개의 allow-listed drafts, 선택 family와 identity timestamps를 보존한다.
- Legacy v1 load 경로가 유지된다.
- Malformed project/profile/timestamp는 첫 canvas mutation 전에 거부되며 실패 시 전체 상태가 rollback된다.

## 6. localhost 브라우저 검증

실제 브라우저 save/load 경로에서 lexical value와 project identity 보존을 검증했다.

### 6.1 Lossless draft 및 prompt 보존

- 출력 폭 문자열 **`+0512`** 보존
- 출력 크기 문자열 **`00064`** 보존
- 선행·후행 whitespace를 포함한 prompt 보존
- 네 family draft가 서로 섞이지 않고 각각 복원됨
- 저장·복원 뒤 canonical Style Profile과 선택 family 유지

이는 허용된 값을 parse 후 재포맷한 “동등값”이 아니라 사용자 입력 문자열을 lossless하게 보존했음을 확인한 것이다.

### 6.2 Timestamp identity 및 pre-mutation rejection

- `createdAt`과 `updatedAt`이 save/load 후 문자열 그대로 보존됨
- malformed timestamp를 canvas/state mutation 전에 거부함
- 실패 전후 project JSON 비교 결과가 **동일**함

즉 malformed identity 입력이 partial canvas/style/draft/history 변경을 남기지 않는 것을 before/after project JSON equality로 확인했다.

## 7. 독립 H3 리뷰 결과

독립 검토는 단순 UI token 존재가 아니라 schema parity, prompt resolution, persistence와 failure atomicity를 대상으로 했다. 최종 판정은 **PASS**이며 critical/high 이슈는 각각 **0**이었다.

특히 다음 경계를 확인했다.

1. Browser/server validator가 서로 다른 profile을 암묵적으로 허용하지 않는다.
2. 모든 family가 resolved profile을 받지만 family-only contract는 profile로 덮이지 않는다.
3. `family_overrides`는 선택 family에만 적용되고 cross-family leakage가 없다.
4. Project v2의 draft key와 control은 allow-list 밖으로 확장되지 않는다.
5. Timestamp validation이 첫 canvas mutation보다 앞선다.
6. Legacy 및 v2 load 실패 경로가 style/drafts/selection/identity를 포함해 rollback한다.

## 8. 호환성·안전 경계

- Canonical profile은 exact-key schema와 bounded nested values를 사용한다.
- 지원하지 않는 family나 production field를 family override에 삽입하면 거부한다.
- Profile과 drafts는 deep-copy/validation 경계를 거쳐 원본 및 family 간 alias를 차단한다.
- Project timestamps는 strict canonical 형식과 순서를 검증한다.
- Legacy v1 호환은 유지하되 malformed 신규 필드를 관대하게 무시하지 않는다.
- Load validation은 mutation보다 먼저 수행되며, async hydrate 실패도 이전 project 상태로 복구한다.

## 9. 알려진 한계와 증거 경계

1. **시각 품질 보장 아님:** Style Profile은 palette, outline, shading 등 생성 제약을 정의·전달하지만 provider 결과의 심미성, 일관성 또는 production-ready 품질을 보장하지 않는다.
2. **Bounded family drafts:** Project는 의도적으로 allow-listed 네 family와 허용 control만 보존한다. 임의 UI state나 미래의 미등록 family/control을 자동 보존하지 않는다.
3. **Visual QA는 Phase 5:** deterministic 및 optional provider 기반 family visual QA는 Milestone I / Phase 5에서 다룬다. Phase 4 PASS를 visual QA PASS로 확대 해석하지 않는다.
4. **검증 수치의 시점:** 810-pass full suite는 H3 checklist 문서-only 변경 직전 snapshot이고, 65-pass 수치는 H3 focused selection이다. 두 수치를 합산하지 않는다.
5. **브라우저 검증 범위:** 브라우저 검증은 persistence, lexical identity와 rollback을 입증하며 실제 유료 provider 생성 품질을 평가하지 않는다.

## 10. 저장소 안전 및 H4 변경 범위

- H4에서는 production code, tests 또는 plan을 수정하지 않았다.
- 본 작업의 직접 산출물은 `docs/history/milestones/ASSET_FAMILY_PHASE_4_REPORT.md` 하나다.
- commit은 생성하지 않았다.
- 기존 dirty tree가 있다면 이를 H4 변경분으로 간주하지 않는다.

## 11. 최종 결론

**Milestone H / Phase 4: PASS.**
**H1–H3 implementation: COMPLETE; H4 report: COMPLETE.**
**Independent H3 review: PASS; critical/high 0; focused 65 passed.**
**Latest pre-checklist full suite: 810 passed, 53 scoped warnings.**
**`node --check`, `py_compile`, `git diff --check`: PASS.**

이 판정은 canonical browser/server Style Profile parity, strict malformed rejection, 네 family의 누출 없는 resolved prompt 결합, Project v2의 lossless bounded persistence, legacy v1 load와 atomic rollback, 그리고 실제 브라우저의 lexical/timestamp 보존 및 pre-mutation rejection 근거에 한정된다. Style Profile 자체의 시각 품질 보장과 family별 visual QA는 포함하지 않으며 Phase 5에서 검증한다.
