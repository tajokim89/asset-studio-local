# Asset Family Production Overhaul — Phase 5 Report

## 1. 판정

**Milestone I / Phase 5: PASS.**

I1–I5의 공통 QA envelope, family별 deterministic QA, 승인 기반 optional visual QA, 선택 Result 기반 unified export dispatch, 독립 ZIP import/round-trip verifier가 구현되었다. 이 판정은 자동화·synthetic fixture와 기존 browser exporter 산출물 검증에 근거하며, 실제 유료 visual provider 호출은 포함하지 않는다.

## 2. 범위

- I1: 공통 QA verdict envelope와 provider router RED 계약
- I2: actor/effect/tile/UI/object deterministic geometry·alpha·metadata QA
- I3: 명시적 승인과 1회 예산을 요구하는 optional visual QA provider
- I4: 선택 Result family/subtype 기반 unified export descriptor/dispatch/UI
- I5: browser ZIP과 독립된 Python import/round-trip verifier

## 3. 공통 QA 계약

Canonical schema: `asset-studio.family-qa/v1`

공통 결과는 다음을 보존한다.

- `PASS | FAIL | PARTIAL`
- reasons, metrics, warnings, artifact refs
- provider id/method/version
- deterministic/visual 하위 결과
- family/subtype/route 일치
- canonical UTC timestamp와 content-bound result ID

Strict validation은 unknown/missing keys, bool metric, NaN/Infinity, cycle/depth/node/string/list budget, unsafe ID/version/timestamp, duplicate/unsafe artifact ref, cross-family contract/provider mismatch를 거부한다. Top-level verdict/reasons/metrics/warnings는 하위 결과의 canonical aggregation과 일치해야 한다.

## 4. Deterministic QA

### Actor

- frame geometry/inventory
- frame별 alpha/non-empty
- distinct motion frame
- walk frame count와 direction contract
- motion에서 동일 프레임 fail-closed

실제 opposite-foot alternation은 deterministic label로 증명하지 않는다.

### Effect

- rows/columns/frame count/grid capacity
- required frame cell non-empty
- frame progression 변화
- pivot/grid/adjacent metadata 일치

### Tile

- tile size/margin/spacing 기반 atlas geometry
- tile inventory/non-empty/distinct coverage
- seamless edge comparison
- topology rule coverage와 metadata

### UI

- source geometry
- states exactness
- 9-slice margins/content safe area bounds
- adjacent metadata consistency

### Object

- alpha bounds/footprint
- normalized pivot/ground/y-sort/snap points
- states/placement/collision metadata consistency
- 다중 상태의 불가능한 1×1 footprint fail-closed

Missing local artifact는 FAIL, remote/mixed artifact는 deterministic `UNAVAILABLE/PARTIAL`이며 PASS로 승격하지 않는다.

## 5. Optional visual QA

- provider가 없으면 `NOT_RUN/PARTIAL`
- provider가 있어도 명시 승인 없이는 0회 호출
- 승인 scope는 정확한 family route와 일치해야 함
- `max_calls=1`, call budget 1만 허용
- retry/duplicate 호출 없음
- strict visual result response
- malformed response/exception은 `UNAVAILABLE/PARTIAL`
- deterministic FAIL은 visual PASS로 덮을 수 없음

Family rubric은 actor identity/direction/실제 limb alternation, effect progression/readability, tile topology/repeat fitness, UI 9-slice/state fidelity, object placement/state readability를 각각 분리한다. 실제 외부·유료 호출은 수행하지 않았다.

## 6. Unified Family Export Center

Schema: `asset-studio.family-export-center/v1`

선택된 succeeded Result의 family/subtype을 다음 route로 dispatch한다.

- Actor: sheets / frames / FPS / pivot
- Effect: full-cell / trim / FPS / pivot
- Tile: atlas / rules / collision / navigation
- UI: states / nine-slice / safe-area
- Object: states / pivot / ground / collision / interaction

Cross-family option은 builder 호출 전에 거부하며, 반환 manifest family가 route와 다르면 실패한다. Export 패널에 선택 Result 요약, effect reconstruction mode, 단일 package export 버튼을 추가했다.

## 7. Import / round-trip verifier

`scripts/verify_family_export.py`는 browser exporter 구현을 import하지 않는 독립 검증기다.

검증 항목:

- ZIP CRC, duplicate/path traversal, byte/file budget
- manifest family/schema
- inventory coverage, bytes, CRC32, SHA-256
- 모든 PNG 독립 decode와 dimensions
- actor frame/atlas/FPS/pivot
- effect trim reconstruction/source offsets/pivot
- tile atlas/tile rectangle bounds
- UI state dimensions/9-slice/safe area
- object state dimensions/pivot/ground/y-sort

CLI:

```bash
python scripts/verify_family_export.py <downloaded-family-package.zip>
```

## 8. TDD 및 회귀 증거

- I1 최초 RED: 49 failed — 두 공개 API 구현 부재
- I2 focused: 70 passed
- I3 최초 RED: 6 failed — visual provider kwargs/API 부재
- I3 QA focused: 76 passed
- I4 exporter focused: 65 passed
- I5 importer/export round-trip focused: 69 passed
- I3 시점 full suite: 886 passed, 53 scoped warnings
- `python -m py_compile server.py scripts/verify_family_export.py`: PASS
- `node --check src/main.js`: PASS
- `git diff --check`: PASS

경고는 기존 Pillow `getdata` deprecation과 duplicate-ZIP mutation fixture 범위다.

## 9. 한계와 정직성 경계

- deterministic QA는 시각적 완성도 또는 실제 발 교대를 자동 보증하지 않는다.
- visual provider는 테스트 더블 통합까지만 검증했으며 실제 유료 호출은 승인 없이 수행하지 않았다.
- remote artifact는 fetch하지 않으므로 deterministic 결과는 PARTIAL이다.
- 최종 실제 브라우저 end-to-end와 full integration review는 Milestone J에서 별도 수행한다.

## 10. 결론

**Phase 5 PASS.**

공통 QA와 family별 판정·export·독립 재수입 검증 경계가 연결되었다. deterministic-only를 production visual PASS로 오인하지 않으며, visual 판단 비용은 명시 승인과 1회 예산으로 제한된다.
