# Asset Family Production Overhaul — Phase 2 / F1 보고서

- **검증일:** 2026-07-11 KST
- **프로젝트:** `/Users/tajokim/asset-studio-local`
- **기준 브랜치 / HEAD:** `main` / `9af254a` (`ahead 2`)
- **보고 범위:** F1 Cross-family spec review 및 Phase 2 구현 판정
- **최종 판정:** **PASS — F1 / Phase 2 spec implementation**
- **다음 게이트:** **F2 full verification (미완료)**

## 1. 판정 요약

Actor, Effect, Tile, UI, Object의 사용자 요청부터 family별 설정·payload·prompt, 후처리, 용도별 preview/QA, engine-usable export까지를 독립 검토했다. 초기 F1 검토는 Actor export와 reference collector/security 통합 결함 때문에 **FAIL**이었으나, 해당 결함과 반복 품질 리뷰에서 제기된 blocker를 수정한 뒤 최종 검토에서 전 family가 **SPEC PASS**, 전체 품질이 **QUALITY APPROVED**를 받았다.

따라서 F1이 요구하는 Phase 2 명세 구현은 통과한다. 다만 F1 최종 수정 이후 모든 브라우저 경로를 다시 수행하는 일은 F2의 독립 게이트다. 특히 visual approval의 마지막 strict RFC3339 timestamp 수정 뒤 Actor ZIP을 브라우저에서 재다운로드·재검증했다는 주장은 하지 않는다.

## 2. Anti-Facade 검토 매트릭스

| 검토 항목 | Actor | Effect | Tile | UI | Object |
|---|---|---|---|---|---|
| Core request가 UI에 노출됨 | PASS | PASS | PASS | PASS | PASS |
| Family draft 왕복 보존 | PASS | PASS | PASS | PASS | PASS |
| visible setting → payload → prompt 추적 | PASS | PASS | PASS | PASS | PASS |
| Family별 후처리 격리 | PASS | PASS | PASS | PASS | PASS |
| 용도별 preview | PASS: 방향/보행 | PASS: 시퀀스 재생 | PASS: 지형/반복 | PASS: 상태/9-slice | PASS: 배치/상태 |
| QA 존재 | PASS | PASS | PASS | PASS | PASS |
| Engine-usable export | PASS: actor package | PASS: slices/package | PASS: atlas/terrain package | PASS: state/9-slice package | PASS: state/atlas package |
| 숨은 Actor fallback 없음 | PASS | PASS | PASS | PASS | PASS |
| 중복 유료 요청 방지 | PASS | PASS | PASS | PASS | PASS |
| 접근 가능한 tab 동작 | PASS | PASS | PASS | PASS | PASS |
| 최종 독립 리뷰 | SPEC PASS | SPEC PASS | SPEC PASS | SPEC PASS | SPEC PASS |

공통 payload는 core request와 shared style/output을 유지하면서 선택된 family contract만 포함한다. Family 전환은 draft를 보존하며 canvas/history를 암묵적으로 초기화하지 않는다. 각 family는 이름만 다른 공통 facade가 아니라 서로 다른 제어, 후처리, preview/QA, export 계약을 가진다.

## 3. RED → GREEN 및 리뷰 이력

### 3.1 초기 F1 RED

초기 독립 검토 판정은 **FAIL**이었다.

1. **Actor export 결함:** Actor package/export 경로가 F1의 engine-usable 및 무결성 요구를 완전히 충족하지 못했다.
2. **Reference collector/security 통합 결함:** reference 수집기가 family-neutral하지 않았고, 요청 경계의 Host/Origin 검증 및 family별 제한이 충분히 통합되지 않았다.
3. **품질 blocker:** artifact 승인과 시간 형식의 결속·엄격성이 독립 감사에 충분하지 않았다.

### 3.2 수정 후 GREEN

- Actor exporter를 실제 방향·beat·프레임 의미론과 결정적 ZIP/manifest 계약에 맞게 보강했다.
- visual approval을 **artifact SHA-256에 결속**해 다른 산출물의 승인을 재사용할 수 없게 했다.
- 승인 timestamp를 **strict RFC3339**로 제한했다.
- reference collector를 Tile/UI/Object에도 적용 가능한 **family-neutral** 구조로 통합했다.
- 모든 HTTP method에서 strict Host/Origin 검증을 적용했으며, **Host 누락도 거부**한다.
- Tile/UI reference에 family별 fence와 입력/작업 budget을 적용해 경로·크기·자원 남용을 fail-closed 처리했다.
- 반복 spec/quality 리뷰에서 발견된 blocker를 해소한 뒤 최종 결과는 전 family **SPEC PASS**, 종합 **QUALITY APPROVED**였다.

## 4. 단계별 검증 근거

> 아래 수치는 서로 다른 검증 단계의 결과다. 합산하거나 동일 실행으로 해석하지 않는다.

| 단계 | 검증 결과 | 의미 |
|---|---:|---|
| 초기 F1 spec review | **FAIL** | Actor export 및 reference collector/security 통합 blocker 발견 |
| 수정 후 family spec review | Actor/Effect/Tile/UI/Object **전부 SPEC PASS** | Anti-Facade 및 family별 생산 경로 충족 |
| 반복 quality review 최종 | **QUALITY APPROVED** | 중간 blocker 수정 후 최종 승인 |
| E4 Object export focused | **6 tests** | Object export 계약 집중 검증 |
| E4 당시 4-family export | **56 tests** | 해당 시점 Actor 제외 4-family export 회귀 |
| E4 당시 spec-stage full regression | **652 passed** | E4 완료 시점 전체 회귀 스냅샷 |
| F1 최종 full test | **722 passed** | 최종 코드 상태의 전체 자동 테스트 결과 |

최종 focused 검증과 full regression은 모두 통과했으며, syntax/static/diff 계열 점검도 PASS 근거에 포함됐다. 테스트는 provider를 stub/비용 없는 경로로 검증했으며 유료 provider 호출은 수행하지 않았다.

## 5. 브라우저 및 실제 산출물 근거

### 5.1 Actor 실제 브라우저 산출물 — 마지막 timestamp 수정 이전 검증 단계

비용 없는 synthetic fixture로 Actor 브라우저 경로를 실제 실행해 다음을 확인했다.

- 구성: **4 directions × 4 beats = 16 frames**
- 방향 순서: **S, W, E, N**
- beat 순서: **contact, down, passing, up**
- 재생: **8 fps**, **125 ms/frame**, **loop**
- 스키마: **`actor-package/v1`**
- ZIP 크기: **48,963 bytes**
- 독립 검증기: Python **`zipfile` / Pillow / `hashlib` / `zlib`**
- 브라우저 관찰: **network 0 / console error 0**

이는 Actor export가 단순 UI 표식이 아니라 실제 16-frame package를 만들고 독립 도구로 해제·이미지·hash/checksum을 검증할 수 있음을 입증한다.

**증거 경계:** 이후 visual approval의 SHA-256 binding 및 strict RFC3339 수정은 자동 테스트와 리뷰로 검증됐다. 그러나 마지막 timestamp 수정 뒤 동일 Actor browser artifact를 다시 생성했다고 기록할 직접 근거는 없으므로, 위 48,963-byte ZIP을 “post-last-fix browser revalidation”으로 표현하지 않는다. 이 재검증은 F2에서 수행할 항목이다.

### 5.2 E4 Object 실제 산출물

E4에서는 실제 Object package를 브라우저에서 생성하고 독립 검증했다.

- 경로: `/tmp/e4-independent-browser-object-package.zip`
- 크기: **22,030 bytes**
- SHA-256: `1b0a0937ca9f08ed13c4c579db0eca009ca5be59a7ceaeb96688d67e8ac0a733`
- 엔트리: **7개**
- 검증 내용: 실제 state PNG와 horizontal atlas, manifest/metadata, CRC32·SHA-256·byte size, ZIP timestamp/attribute 및 변조 거부
- 브라우저 부작용: **console/network/history/Fabric mutation 0**

이 근거는 Object의 state, pivot/ground/Y-sort, collision/interaction, scale/footprint, custom metadata와 실제 derivative/export가 engine-usable package에 보존됨을 뒷받침한다.

## 6. 서버 통합 및 보안 근거

- Reference collector는 Actor 전용 분기가 아니라 **Tile/UI/Object를 포함한 family-neutral** 경로다.
- Host/Origin 검사는 method별 우회 없이 **모든 method**에 적용된다.
- 허용 Host가 명시되지 않은 요청, 즉 **missing Host**도 fail-closed로 거부한다.
- 잘못된 Origin, 구조화 payload, family/type 조합은 provider 호출 전에 거부한다.
- Tile/UI 입력에는 전용 fence와 source/output/work budget을 적용한다.
- archive path traversal, 이름 충돌, unsafe arithmetic, 과도한 frame/pixel/archive 계획은 생성 전에 차단한다.
- 오류 시 busy state를 복원하며 provider/history/Fabric 상태를 불필요하게 변경하지 않는다.

## 7. 한계와 비평가 범위

1. **Provider 이미지 품질 미평가:** 유료 provider 호출을 하지 않았으므로 실제 모델이 생성하는 미술 품질, 방향 일관성, 심미성은 이 PASS의 평가 대상이 아니다. 검증 대상은 계약, 통합, deterministic 후처리/QA/export 및 보안 경계다.
2. **F2 미완료:** 모든 family tab, 대표 payload, family별 preview/export interaction, download, console 0을 최종 HEAD 상태에서 한 번에 재검증하는 F2가 다음 게이트다.
3. **Actor post-fix browser 재검증 경계:** strict RFC3339 마지막 수정 이후 Actor artifact 재생성 근거가 없으므로 F2에서 SHA-256-bound approval과 새 ZIP의 일치까지 확인해야 한다.

## 8. 저장소 및 dirty-tree 안전

- 기준 상태는 `main` / `9af254a`, upstream 대비 **ahead 2**다.
- 작업 시작 전 존재한 tracked/untracked **dirty baseline을 그대로 보존**했다.
- 이 보고서 범위는 문서 작성뿐이며 code, tests, plan을 변경하지 않는다.
- reset, clean, stash, commit, push 및 provider call을 수행하지 않았다.
- 따라서 dirty tree 전체를 Phase 2 변경분이라고 해석해서는 안 되며, 이 보고서의 직접 산출물은 본 문서 하나다.

## 9. 최종 결론

**F1 / Phase 2 spec implementation: PASS.**
**Cross-family review: Actor, Effect, Tile, UI, Object 모두 SPEC PASS.**
**Quality review: APPROVED.**

이 판정은 최종 **722 passed** 자동 회귀, 단계별 focused 검증, Actor/E4의 실제 독립 artifact 근거, 그리고 reference collector·Host/Origin·budget 경계의 통합 검토에 근거한다. 단, 이는 F2 완료 선언이 아니다. Phase 3 진입 전 F2에서 최종 HEAD 기준 전 family 브라우저/download 재검증을 수행해야 한다.
