# Asset Family Production Overhaul — Milestone A Report

Date: 2026-07-10
Project: `/Users/tajokim/asset-studio-local`
Verdict: **PASS**

## 적용

- 현재 family facade 상태를 코드 근거로 감사해 `docs/history/artifacts/ASSET_FAMILY_BASELINE_AUDIT.md`에 고정했다.
- 공통 생성 셸의 core request, shared style, family settings, output, Generate 순서와 ARIA tab 계약을 테스트로 고정했다.
- browser payload가 공통 필드와 선택한 family nested contract 하나만 만들도록 검증했다.
- server normalizer를 allow-list 기반 family contract로 정리하고 공통 `style`/`output`을 정규화했다.
- invalid structured family/type은 fail-closed 처리하며 실제 HTTP endpoint에서 JSON 400을 반환한다.
- 실제 pre-A5 flat actor payload는 actor-specific field가 있을 때만 legacy adapter로 수용한다.
- 비용 없는 `window.__assetStudioDebug` payload inspection 경로를 유지했다.

## RED / GREEN 검증

- A2: 초기 false RED는 spec review에서 제거했으며, 실제 shell contract는 12 passed였다.
- A4 RED: 9 failed / 41 passed.
  - shared style/output server normalization 누락 5건
  - browser/server invalid sprite subtype fallback 4건
- A5 GREEN: focused payload suite 50 passed.
- A5 quality-fix RED: legacy/HTTP validation 7 failed / 5 passed.
- A5 quality-fix GREEN: focused 12 passed.
- Milestone A expanded family/HTTP suite: 112 passed.

## Syntax / regression

- `python -m py_compile server.py`: PASS
- `node --check src/main.js`: PASS
- `git diff --check`: PASS
- Milestone A 범위의 신규 regression: 0

## Browser 검증

- URL: `http://127.0.0.1:4184`, `http://127.0.0.1:4185`
- mouse family 전환과 family별 copy/settings 변경 확인.
- ArrowRight, End, Home으로 탭 선택과 focus 이동 확인.
- sprite/tile core-request draft 왕복 복원 확인.
- family 전환 중 history/canvas/layer reset 없음.
- representative payload 5종 확인:
  - sprite/character
  - sprite/effect
  - tile/terrain
  - ui/button
  - object/interactable
- 각 payload는 공통 `prompt/style/output`과 선택 family key 하나만 포함.
- browser console messages 0 / JavaScript errors 0.
- 유료 생성 호출 없음.

## Review verdict

- A1: SPEC PASS / QUALITY APPROVED
- A2: SPEC PASS / QUALITY APPROVED
- A3: SPEC PASS / QUALITY APPROVED
- A4: SPEC PASS / QUALITY APPROVED
- A5: SPEC PASS / QUALITY APPROVED

## Dirty-tree safety

- 시작 시점의 대량 tracked/untracked dirty baseline을 보존했다.
- reset, clean, stash, unrelated restore, 기존 파일 삭제를 수행하지 않았다.
- commit/push하지 않았다.

## 남은 blocker

- Milestone A blocker 없음.
- 다음 범위: Milestone B의 effect sequence contract, slicing, common-canvas preview, export round-trip.
