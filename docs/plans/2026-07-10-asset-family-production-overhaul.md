# Asset Studio Local — Asset Family Production Overhaul 실행 계획

> **For Hermes:** `subagent-driven-development`, `test-driven-development`, `requesting-code-review`, `ai-image-editor-prototyping` 스킬을 사용해 아래 작업을 순서대로 실행한다. 각 코드 작업은 RED → GREEN → REFACTOR, 사양 리뷰 → 품질 리뷰 순서를 지킨다.

**Goal:** Asset Studio Local의 `sprite / effect / tile / ui / object`를 탭과 payload만 존재하는 facade가 아니라, 생성 요청부터 preview·QA·엔진용 export까지 이어지는 실제 패밀리별 제작 시스템으로 완성한다.

**Architecture:** 하나의 공통 생성 셸 위에 정확히 하나의 family contract만 활성화한다. Browser payload, server normalization, provider prompt, postprocess, preview, QA, export를 같은 family schema로 연결하며, actor 전용 상태가 effect/tile/ui/object로 새지 않게 한다. 모든 단계는 기존 dirty worktree를 baseline으로 보존하고 task delta만 검증한다.

**Tech Stack:** Python HTTP server, Fabric.js, vanilla JavaScript, HTML/CSS, Pillow, pytest, browser/computer verification, Godot/Tiled/Unity/Aseprite 호환 metadata 개념.

**Project root:** `/Users/tajokim/asset-studio-local`

**Primary specification:** `/Users/tajokim/asset-studio-local/SESSION_HANDOFF_2026-07-10.md`의 Sections 12~23

---

## 0. 실행 제어 규칙

### 0.1 사용자 승인 범위

사용자는 이 문서의 전체 범위를 순차적으로 계속 실행하도록 승인했다. 각 task가 통과하면 다음 task로 진행한다. 사소한 구현 선택은 질문하지 말고 specification과 기존 convention에 맞는 안전한 기본값을 선택한다.

다음 상황에서만 멈추고 보고한다.

- 비밀키·비밀번호·권한 입력이 필요함
- 결제·유료 API를 반복 호출해야 함
- 파일 삭제, reset, clean, stash, 대량 이동 등 되돌리기 어려운 작업이 필요함
- 기존 사용자 변경과 task 변경을 안전하게 분리할 수 없음
- specification끼리 실제로 충돌해 한쪽을 임의로 버려야 함
- focused test 또는 browser path가 두 번의 원인 분석·수정 후에도 차단됨

### 0.2 Git 안전 규칙

현재 worktree는 대량의 tracked 수정·삭제와 untracked 파일이 있는 dirty 상태다.

절대 하지 않는다.

```text
git reset
git clean
git stash
git checkout -- <unrelated-file>
git restore <unrelated-file>
rm -rf on existing project paths
git add -A
git commit
git push
```

- 사용자 승인 전 commit/push하지 않는다.
- task에서 허용된 파일만 수정한다.
- 각 task 전에 `git status --short`와 task 대상 파일 diff를 확인한다.
- reviewer에게 baseline dirtiness와 허용 파일을 명시한다.
- pre-existing failure와 task-introduced regression을 구분한다.

### 0.3 계획 파일 진행 기록

실행자는 task 완료 직후 이 문서의 체크박스를 `[x]`로 바꾸고 아래 형식으로 증거를 기록한다.

```text
Evidence:
- RED: <command> → expected failure
- GREEN: <command> → N passed
- Syntax: <commands/results>
- Browser: <tested interactions, console error count>
- Files: <task delta>
- Review: SPEC PASS / QUALITY APPROVED
```

실패한 task는 체크하지 않는다. `PARTIAL`을 `DONE`으로 기록하지 않는다.

### 0.4 공통 검증 명령

```bash
cd /Users/tajokim/asset-studio-local
PY=/Users/tajokim/.hermes/hermes-agent/venv/bin/python
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; fi

"$PY" -m py_compile server.py
node --check src/main.js
"$PY" -m pytest <focused tests> -q
git diff --check
```

전체 회귀는 milestone 종료 시 실행한다.

```bash
"$PY" -m pytest tests -q
```

전체 suite에 baseline failure가 있으면 숫자와 test 이름을 그대로 기록하고, task 전후 비교로 신규 regression 여부를 판정한다.

### 0.5 브라우저 검증 규칙

- 가능한 경우 `./scripts/run_server.sh`로 서버를 실행한다.
- 기존 중복 server를 임의로 죽이지 않는다. 포트 충돌 시 process 상태를 먼저 확인하고 이번 실행을 구분한다.
- 실제 UI를 클릭한다. DOM token 존재만으로 PASS하지 않는다.
- console error를 확인한다.
- 다운로드 산출물은 실제 browser UI에서 받은 파일로 검사한다.
- 유료 생성은 static/focused/browser wiring이 모두 통과한 뒤에만 실행한다.
- provider가 가능하면 각 family당 최대 1개의 저비용 smoke 결과만 생성한다. 실패 시 무한 retry하지 않는다.

---

## 1. 완료 정의 — Anti-Facade Gate

패밀리 하나를 완료하려면 아래 전체 경로가 실제로 연결돼야 한다.

```text
family-specific core request
→ shared style/reference
→ family-only production settings
→ isolated normalized payload
→ prompt consuming every visible setting
→ family-specific postprocess
→ family-specific preview
→ family-specific QA
→ engine-usable export + metadata
```

다음은 완료가 아니다.

- 탭만 존재
- subtype 목록만 존재
- 조건부 controls만 존재
- payload key만 분리
- 정적 테스트만 통과
- 결과가 일반 이미지 썸네일로만 보임
- PNG는 있으나 엔진용 metadata가 없음

---

# Milestone A — Baseline과 공통 생성 셸

## Task A1 — Live baseline 감사표 생성

- [x] **A1 완료**

**Objective:** 현재 actor/effect/tile/ui/object의 visible UI → payload → prompt → postprocess → preview → QA → export 상태를 `DONE / PARTIAL / MISSING / CONTRADICTORY`로 고정한다.

**Files:**
- Read: `SESSION_HANDOFF_2026-07-10.md`
- Read: `index.html`
- Read: `src/main.js`
- Read: `server.py`
- Read: `tests/test_asset_family_ui_static.py`
- Read: `tests/test_asset_family_payload_contract.py`
- Create: `docs/history/artifacts/ASSET_FAMILY_BASELINE_AUDIT.md`

**Steps:**

1. `git status --short`, `git diff --stat`, task 파일별 diff를 기록한다.
2. 다섯 representative type을 추적한다: `character`, `effect`, `terrain/tileset`, `button/main_panel`, `interactable/prop`.
3. 각 type의 core request, visible controls, nested payload, prompt branch, server normalizer, postprocess, preview, QA, export를 표로 작성한다.
4. `character/idle` fallback, `effect → ui_static/1 frame`, dead UI field, generic thumbnail-only flow를 별도 blocker로 적는다.
5. 코드 수정은 하지 않는다.
6. reviewer가 코드 근거와 감사표가 일치하는지 확인한다.

**Acceptance:** 감사표만 보고 다음 task의 최소 수정 지점을 알 수 있어야 한다.

Evidence:
- Baseline: `git status --short`; `git diff --stat` → 63 files changed, 1471 insertions(+), 2691 deletions(-); `git diff --check` → PASS
- Audit verification: focused family tests → 58 passed, 9 baseline failures; `node --check src/main.js` → PASS; `python3 -m py_compile server.py` → PASS
- Browser: not applicable for read-only baseline audit; no server/provider call performed
- Files: created `docs/history/artifacts/ASSET_FAMILY_BASELINE_AUDIT.md`; no production code/tests changed
- Review: SPEC PASS / QUALITY APPROVED

---

## Task A2 — 공통 생성 셸 계약 테스트

- [x] **A2 완료**

**Objective:** 모든 family에 필수 core request/style/output/generate 흐름이 있고 family 전환 시 draft가 보존돼야 한다는 failing tests를 먼저 고정한다.

**Files:**
- Create or Modify: `tests/test_asset_family_anti_facade_static.py`
- Modify later in GREEN: `index.html`, `src/main.js`, `styles/app.css`

**RED requirements:**

- sprite/tile/ui/object 모든 tab에 같은 공통 core request가 보인다.
- label/placeholder/help는 family별로 바뀐다.
- family별 core-request draft가 별도로 저장·복원된다.
- shared style와 output/background가 active family에서 보인다.
- primary Generate는 core request/settings/output 뒤에 있다.
- tab에 `aria-controls`, matching tabpanel, roving tabindex, ArrowLeft/Right/Home/End가 있다.
- family 변경은 canvas/layers/history를 초기화하지 않는다.

**Steps:**

1. behavior별 failing test를 하나씩 작성한다.
2. focused test를 실행해 예상 이유로 RED인지 확인한다.
3. 아직 production code는 수정하지 않는다.

**Acceptance:** 기존 코드가 이미 만족하는 항목은 test를 억지로 실패시키지 않는다. 실제 missing behavior만 RED로 남긴다.

Evidence:
- RED: initial 7 passed / 4 failed was rejected by spec review as a false ancestry constraint; the invalid RED was removed rather than forcing production changes
- Focused: `pytest tests/test_asset_family_anti_facade_static.py -q` → 12 passed; no legitimate A2 RED remained because the live shell already satisfies the stated contract
- Syntax: test `py_compile` PASS; `git diff --check` PASS
- Browser: deferred to A3 runtime verification
- Files: created `tests/test_asset_family_anti_facade_static.py`; no production code changed
- Review: SPEC PASS / QUALITY APPROVED

---

## Task A3 — 공통 생성 셸 최소 구현

- [x] **A3 완료**

**Objective:** A2의 failing tests를 최소 변경으로 통과시키고 실제 브라우저에서 네 family를 전환할 수 있게 한다.

**Files:**
- Modify: `index.html`
- Modify: `src/main.js`
- Modify: `styles/app.css`
- Test: `tests/test_asset_family_anti_facade_static.py`

**Steps:**

1. shared core request/style/output controls를 한 번만 렌더링한다.
2. family별 label/placeholder/help와 draft state를 구현한다.
3. Generate CTA를 입력 흐름 끝에 둔다.
4. ARIA tab keyboard behavior를 구현한다.
5. app eager initialization은 모든 `let/const`와 listener 선언 뒤에 둔다.
6. focused tests → syntax → diff check를 실행한다.
7. 브라우저에서 mouse/keyboard 전환, draft 보존, console을 검증한다.
8. spec review 후 quality review를 통과한다.

Evidence:
- GREEN: `pytest tests/test_asset_family_anti_facade_static.py -q` → 12 passed; existing baseline shell required no additional production edit
- Syntax: `python -m py_compile server.py` → PASS; `node --check src/main.js` → PASS; `git diff --check` → PASS
- Browser: `http://127.0.0.1:4184` actual UI; mouse sprite→tile changed family copy/settings; exactly one of `spriteSettings/tileSettings/uiSettings/objectSettings` had computed display other than `none`
- Browser draft: sprite=`A3 sprite draft sentinel`, tile=`A3 tile draft sentinel`; each restored after round-trip switching
- Browser keyboard: ArrowRight sprite→tile with focus; End→object; Home→sprite
- Browser state/console: history remained at initial entry, no canvas/layer reset observed, console messages 0 / JS errors 0
- Files: no A3 production delta; no paid generation; no result tray/style-profile/family-preview scope creep
- Review: SPEC PASS / QUALITY APPROVED

**Do not:** 결과 트레이, 프로젝트 스타일 프로필, family preview를 이 task에서 미리 구현하지 않는다.

---

## Task A4 — Family payload isolation RED tests

- [x] **A4 완료**

**Objective:** 대표 family payload가 정확히 하나의 nested contract만 가지며 숨은 actor state를 포함하지 않는다는 tests를 고정한다.

**Files:**
- Modify: `tests/test_asset_family_payload_contract.py`
- Create if needed: `tests/test_asset_family_payload_runtime.py`
- Modify later in GREEN: `src/main.js`, `server.py`

**Required representative payloads:**

- `sprite/character`
- `sprite/effect`
- `tile/terrain`
- `ui/button`
- `object/interactable`

**Assertions:**

- `asset_family`, `asset_type`, `prompt`, `style`, `output` 존재
- 선택한 nested key 하나만 존재
- effect에 direction/equipment/gait 없음
- tile에 actor action/frame/direction 없음
- UI에 actor/effect/tile/object keys 없음
- object에 actor direction/action 없음
- legitimate zero values 보존
- numeric bounds와 enum normalization
- 빈 hidden subtype가 character로 fallback하지 않음
- duplicate generate guard 존재

**Steps:** RED를 확인하고 task를 종료한다.

Evidence:
- RED: `pytest -q tests/test_asset_family_payload_contract.py tests/test_asset_family_payload_runtime.py` → 41 passed / 9 expected failures
- RED causes: server shared `style`/`output` normalization missing (5); browser/server empty+invalid sprite subtype still falls back to `character` (4)
- Passing coverage: five representative browser payload schemas/values, exactly one family contract, foreign-family isolation, UI/effect invariants, zero/false preservation through production helpers, numeric/enum bounds, duplicate in-flight guard
- Syntax: both test files `py_compile` PASS; Node harness timeout/diagnostics verified; `git diff --check` PASS
- Browser/provider: cost-free Node builder harness + direct server normalizer runtime only; no paid call
- Files: modified `tests/test_asset_family_payload_contract.py`; created `tests/test_asset_family_payload_runtime.py`; no production code changed
- Review: SPEC PASS / QUALITY APPROVED

---

## Task A5 — Browser builder와 server normalizer 격리

- [x] **A5 완료**

**Objective:** A4 tests를 통과하도록 browser payload builder와 server allow-list normalizer를 단일 family contract로 정리한다.

**Files:**
- Modify: `src/main.js`
- Modify: `server.py`
- Test: `tests/test_asset_family_payload_contract.py`
- Test: `tests/test_asset_family_payload_runtime.py` if created

**Steps:**

1. selected family nested object만 만드는 builder를 구현한다.
2. `Number(value) || fallback`을 legitimate zero-safe helper로 교체한다.
3. server는 raw `dict(data)`를 유지하지 않고 allow-list normalized object를 만든다.
4. legacy flat compatibility를 actor sprite branch로 제한한다.
5. non-costly payload debug action/helper를 제공한다.
6. focused tests, syntax, diff check를 실행한다.
7. 브라우저에서 다섯 representative payload를 확인한다.
8. spec/quality review를 통과한다.

Evidence:
- RED: payload suites → 9 failed / 41 passed (shared style/output normalization 5; browser/server invalid subtype fallback 4)
- GREEN: A5 payload suite → 50 passed; expanded A5/family + HTTP validation suite → 112 passed
- Syntax: `python -m py_compile server.py` PASS; `node --check src/main.js` PASS; `git diff --check` PASS
- Browser: `http://127.0.0.1:4185` debug API verified sprite/character, sprite/effect, tile/terrain, ui/button, object/interactable; each had common prompt/style/output and exactly one selected family key; console errors 0
- HTTP/legacy: actual pre-A5 flat actor payload positively adapts; malformed structured payloads return JSON HTTP 400 before provider call
- Files: modified `src/main.js`, `server.py`; created `tests/test_a5_legacy_actor_http_validation.py`; no paid generation
- Review: SPEC PASS / QUALITY APPROVED

---

# Milestone B — Sprite Actor / Effect

## Task B1 — Effect sequence contract RED tests

- [x] **B1 완료**

**Objective:** effect가 actor나 ui_static으로 collapse되지 않고 sequence 계약을 end-to-end 유지해야 한다는 tests를 작성한다.

**Files:**
- Create: `tests/test_effect_sequence_contract.py`
- Modify later: `src/main.js`, `server.py`

**Assertions:**

- `effectFrameCount`가 prompt/payload/grid/preview/export의 single source of truth
- `animation_mode = effect_sequence`
- static effect와 sequence effect 구분
- `ui_static`, `single asset`, `no sprite sheet` contradiction 없음
- envelope width/height, layout, gap, FPS/duration, loop, normalized pivot, size basis 존재
- actor direction/body/equipment/action cleanup bypass

**Steps:** RED를 확인한다.

Evidence:
- RED: `pytest -q tests/test_effect_sequence_contract.py` → 21 passed / 10 expected failures
- RED causes: missing functional effect controls; incomplete browser/server static+sequence contract and timing; missing normalized metadata at both effect postprocessor routes; effect frame count/layout/envelope not yet driving grid/preview/actual export selection
- Passing coverage: semantic sequence prompt/contradiction variants, valid category baseline, actor cleanup bypass route harness, no-cost provider stubs, robust DOM parser and Node diagnostics
- Syntax: test `py_compile` PASS; `node --check src/main.js` PASS; `git diff --check` PASS
- Files: created `tests/test_effect_sequence_contract.py`; no production code changed
- Review: SPEC PASS / QUALITY APPROVED

---

## Task B2 — Effect contract와 UI 구현

- [x] **B2 완료**

**Objective:** effect static/sequence 설정과 공통 envelope/pivot contract를 UI부터 server postprocess까지 연결한다.

**Files:**
- Modify: `index.html`
- Modify: `src/main.js`
- Modify: `server.py`
- Modify: `styles/app.css`
- Test: `tests/test_effect_sequence_contract.py`

**Controls:**

- category
- static/sequence
- one-shot/loop/ping-pong
- frame count
- FPS 또는 duration
- layout rows/columns/gap
- frame envelope width/height
- size basis: pixels/tile/actor-relative/world/screen
- pivot preset + normalized x/y
- trim policy

**Acceptance:** effect path가 actor helper를 공유해 1 frame으로 바뀌지 않는다.

Evidence:
- RED: B1 contract → 21 passed / 10 failed; quality regressions additionally reproduced for capacity, selected-reference payload/success path, accessibility, and real loop playback
- GREEN: `tests/test_effect_sequence_contract.py` → 42 passed; full suite → 338 passed (8 existing Pillow deprecation warnings)
- Browser: effect-only controls visible; sequence 7 frames / 2×4 / gap 3 / envelope 80×48 / FPS 20; static→1 frame and sequence restoration; under-capacity 2×1 canonicalized to 2×4; controls accessible; history unchanged; console errors 0
- Routing: primary and selected-reference effects use structured payloads and pass normalized contract to effect postprocessing; actor cleanup bypassed
- Playback: one-shot/loop/ping-pong map to once/loop/pingpong; one-shot draws through final frame once and stops
- Syntax: `python -m py_compile server.py` PASS; `node --check src/main.js` PASS; `git diff --check` PASS
- Files: modified `index.html`, `src/main.js`, `server.py`, `styles/app.css`, effect/payload/static regression tests; no paid generation
- Review: SPEC PASS / QUALITY APPROVED

---

## Task B3 — Effect slicer synthetic fixtures RED tests

- [x] **B3 완료**

**Objective:** variable visible bbox, detached particles, faint glow를 가진 sequence가 안전하게 분리·복원돼야 한다는 deterministic tests를 만든다.

**Files:**
- Create: `tests/test_effect_sequence_slicing.py`
- Create if useful: `tests/helpers/effect_fixture_factory.py`
- Modify later: `src/main.js` and/or server-side deterministic helpers

**Fixtures:**

1. 6-frame explosion grow/shrink
2. core + detached sparks
3. alpha 1~20 glow
4. tiny spark below 48px
5. 1px boundary intrusion
6. adjacent frames connected by trail
7. trimmed frames with common sourceSize/pivot

**Assertions:**

- connected component count is never frame count
- exact declared frame count/order
- full-cell mode preserves common dimensions
- trim mode records sourceSize/trimRect/pivot
- reconstruction is pixel-equivalent within declared tolerance
- glow/sparks not dropped
- boundary intrusion fails with reason/metrics

Evidence:
- Fixture self-tests: 20 passed
- Contract RED: 14 failed, all deliberate missing `server.slice_effect_sequence` behavior; no collection/import/fixture errors
- Coverage: all 7 required fixtures plus safe-padding/empty-frame variants; exact RGBA low-alpha/tiny/detached preservation and full-cell↔trim reconstruction
- Contract: `docs/contracts/EFFECT_SEQUENCE_SLICING_CONTRACT.md` (`effect-slices/v1`, row-major declared grid, 1px safe trim padding, alias-tolerant semantic fields)
- Syntax/diff: PASS
- Files: added `tests/test_effect_sequence_slicing.py`, `tests/helpers/effect_fixture_factory.py`, `tests/helpers/__init__.py`, contract doc; no production changes
- Review: SPEC PASS / QUALITY APPROVED

---

## Task B4 — Effect sequence grid, trim metadata, common-canvas preview

- [x] **B4 완료**

**Objective:** contract-based sequence slicing을 기본으로 하고 optional trim과 common-canvas preview를 구현한다.

**Files:**
- Modify: `src/main.js`
- Modify: `server.py` only if deterministic image helpers belong server-side
- Modify: `index.html`
- Modify: `styles/app.css`
- Test: `tests/test_effect_sequence_slicing.py`

**Implementation rules:**

- fixed grid는 declared rows/columns/cell/gap을 사용
- component detector는 loose asset extraction 전용
- alpha bbox는 QA/trim에만 사용하고 frame origin을 바꾸지 않음
- trim preview는 sourceSize에 trimRect offset으로 복원
- pivot overlay 표시
- effect-only preview와 actor-composite preview 분리
- validator는 frame count, non-empty, gutter alpha, edge/cross-cell, low-alpha preservation metrics 반환

Evidence:
- RED→GREEN: B3 `20 passed / 14 failed` → B4 slicing `36 passed`
- Related effect suites: 82 passed; full suite: 374 passed (8 existing Pillow warnings)
- Server: declared-grid full-cell/trim slicer, 1px safe padding, exact RGBA, structured validation metrics and bounded input checks
- Browser: synthetic 4-frame 2×2/gap3/32×32 trim preview; sourceSize 32×32, varied trimRects, low-alpha 20 preserved; pivot 0.25/0.75 rendered at 25%/75%; effect-only and actor-composite visually distinct; console errors 0
- Scope: no B5 ZIP/manifest/download implementation
- Syntax/diff: PASS
- Files: modified `server.py`, `src/main.js`, `index.html`, `styles/app.css`, `tests/test_effect_sequence_slicing.py`; no paid generation
- Review: SPEC PASS / QUALITY APPROVED

---

## Task B5 — Effect export와 browser round-trip

- [x] **B5 완료**

**Objective:** full-cell sequence와 trim+metadata export를 실제 browser 다운로드 경로에서 검증한다.

**Files:**
- Modify: `src/main.js`
- Modify: `index.html`
- Test: `tests/test_effect_export_manifest.py`

**Manifest fields:**

- schema_version
- kind/effect category
- frame count/order
- sourceSize/logical frame size
- layout/gap/padding
- loop/FPS/duration
- pivot/coordinate convention
- trim mode and per-frame trimRect

**Browser acceptance:** 다운로드 ZIP/JSON을 다시 읽어 common-canvas sequence를 복원할 수 있다.

Evidence:
- RED→GREEN: B5 focused `6 failed` → 11 passed after quality regressions
- Related effect suites: 93 passed; full suite: 385 passed (8 existing Pillow warnings)
- Browser: synthetic 4-frame full-cell and trim+metadata ZIP downloads completed through actual buttons; manifest + frame-000..003; common 32×32 reconstruction; low alpha retained; console errors 0
- Independent compatibility: Python `zipfile` CRC/order/manifest verification + Pillow PNG decode and exact RGBA reconstruction for both modes
- Safety: 4,096-frame / 8,388,608-pixel / ~192MiB working-set preflight, safe integer checks, busy-state restoration, hardened generated-output validators
- Syntax/diff: PASS
- Files: added `tests/test_effect_export_manifest.py`; modified `src/main.js`, `index.html`; no paid generation
- Review: SPEC PASS / QUALITY APPROVED

---

# Milestone C — Tile / Map

## Task C1 — Tile contract와 rule coverage RED tests

- [x] **C1 완료**

**Objective:** tile이 size+seamless 수준을 넘어 terrain topology와 engine metadata를 가져야 한다는 tests를 고정한다.

**Files:**
- Create: `tests/test_tile_family_workflow.py`
- Modify later: `index.html`, `src/main.js`, `server.py`

**Contract:**

- environment/material/use
- tile size/shape
- atlas margin/spacing
- single/tileset/autotile
- rows/columns
- seamless
- topology: corner/edge/corner+edge/blob
- inner/outer corners and transitions
- terrain types
- variants/frequency
- collision/occlusion/navigation/custom metadata

**Assertions:** tile prompt에 actor/action/direction/UI language가 없다.

Evidence:
- Focused RED: 5 passed / 35 failed, all missing ratified browser/server tile-contract behavior; no harness/import/collection errors
- Coverage: full nested tile schema, family isolation, mode/topology enums, typed corners/transitions/terrains/variants/metadata, structural validation, prompt contamination absence
- Scope: no C2 controls/postprocessor, C3 preview/QA, or C4 export assertions
- Syntax/diff: PASS
- Files: added `tests/test_tile_family_workflow.py`; no production changes
- Review: SPEC PASS / QUALITY APPROVED

---

## Task C2 — Tile authoring form와 prompt/postprocess

- [x] **C2 완료**

**Objective:** tile contract의 모든 visible setting을 prompt와 family-specific postprocess에 연결한다.

**Files:**
- Modify: `index.html`
- Modify: `src/main.js`
- Modify: `server.py`
- Modify: `styles/app.css`
- Test: `tests/test_tile_family_workflow.py`

**Do not:** actor trim/candidate/direction cleanup 사용 금지.

Evidence:
- RED→GREEN: C1 `5 passed / 35 failed` → C1/C2 43 passed; stale contract tests aligned and full suite 427 passed (8 existing Pillow warnings)
- Browser: complete accessible tile form; autotile 8×8, 32px, margin2/spacing1, blob topology, transitions/terrains/variants/metadata serialize exactly; malformed JSON blocked with field-specific error; prompt foreign-language scan false; history unchanged; console errors 0
- Server: strict structural normalization with safe empty/poison-only defaults; dedicated tile postprocessor on both generation routes; no actor/effect cleanup
- Scope: no C3 preview/QA or C4 export
- Syntax/diff: PASS
- Files: modified `index.html`, `src/main.js`, `server.py`, `styles/app.css` and updated authoritative/stale tests; no paid generation
- Review: SPEC PASS / QUALITY APPROVED

---

## Task C3 — Tile repeat/paint/topology preview와 QA

- [x] **C3 완료**

**Objective:** tile 결과를 실제 map-use 관점으로 검사한다.

**Files:**
- Modify: `index.html`
- Modify: `src/main.js`
- Modify: `styles/app.css`
- Create: `tests/test_tile_preview_and_qa.py`

**Preview modes:**

- source atlas
- 3×3 repeat
- broad random repeat
- terrain brush simulation
- transition/rule coverage
- collision/occlusion/navigation overlay
- variant distribution

**QA:** seam, missing rule, bad corner, repeated pattern, out-of-grid, metadata mismatch.

Evidence:
- Runtime: 13 deterministic C3 tests cover seven modes, exact alpha/grid slicing, QA reasons, budget guards, O(1) grid membership, fit geometry, variant distribution and read-only wiring
- Browser: synthetic 19×19 / 2×2 atlas exercised all modes; deterministic 3×3, 12×8 random/brush, rule/overlay/distribution models; QA WARN with metrics; no preview history mutation
- Visual QA fixes: centered nearest-neighbor fit and wrapped metrics; variant distribution uses proportional bars with id/percentage
- Safety: preflight before canvas/getImageData; max dimension 16,384, source/work 16,777,216 px, 4,096 cells, preview 4,194,304 px
- Full verification: 440 passed, 8 existing Pillow warnings; syntax/compile/diff PASS
- Scope: no C4 export/download
- Review: SPEC PASS / QUALITY APPROVED
- Process note: dedicated C3 suite was initially omitted and added retrospectively; its first run exposed one real corner-coverage omission, then GREEN

---

## Task C4 — Tile export

- [x] **C4 완료**

**Objective:** atlas/individual tiles/rules/metadata export를 browser path로 제공한다.

**Files:**
- Modify: `src/main.js`
- Modify: `index.html`
- Create: `tests/test_tile_export_manifest.py`

**Outputs:**

- atlas PNG
- tile ZIP
- index/coordinates
- margin/spacing
- terrain rules and variants
- collision/navigation/custom properties
- Godot/TSX-friendly JSON where supported

Evidence:
- Package: exact atlas PNG, row-major per-tile PNGs, canonical manifest, terrain mapping, engine metadata, TSX/TMX for supported square grids
- Executable C4 tests: 28 passed; independent Python zipfile/Pillow/json/hashlib/CRC/XML verifies pixels, alpha1, checksums, geometry, metadata and XML
- Security: strict local/central/EOCD matching, path/duplicate/CRC/SHA/PNG/schema/geometry/XML validation, no trailing/multidisk/ZIP64; archive/allocation budgets preflighted
- Round-trip limits: tile verifier supports full 16,777,216-pixel export ceiling while effect decoder keeps 8,388,608 default
- Browser: deterministic 19×19 2×2 package, actual download, parser verified 4 tiles/10 files, exact topology/metadata, PASS summary, busy recovery, console errors 0
- Full verification: 468 passed; syntax/compile/diff PASS
- Review: SPEC PASS / QUALITY APPROVED

---

# Milestone D — UI Component

## Task D1 — UI production contract RED tests

- [x] **D1 완료**

**Objective:** UI가 flattened mockup이 아니라 reusable component source가 되도록 contract tests를 작성한다.

**Files:**
- Create: `tests/test_ui_family_workflow.py`

**Contract:**

- component purpose/information structure
- actual source width/height
- fixed/9-slice
- four slice margins
- content safe area/padding
- border/corner/decor density
- edge/center stretch or tile
- opacity
- states
- target resolution/device safe area
- text-free default

**Assertions:** actor/effect/tile/object state 없음, `ui_static`, frame count 1, direction none.

Evidence:
- 84 contract tests collected; 77 deliberate RED / 7 legacy-baseline pass with working Node/browser-builder and Python normalizer harnesses
- Exact nested schema, safe defaults, allowlist stripping, family isolation, dimensions/edge boxes, fixed/9-slice, border/corner, density, stretch/tile, opacity, states, target/device areas and static invariants
- Exact minimal declarations: border `{style,width}`, corner `{style,radius}`; malformed booleans/types/duplicates/unknowns covered
- Scope: test-only; no D2 controls/prompt/postprocess, D3 preview/QA, or D4 export
- Review: SPEC PASS / QUALITY APPROVED

---

## Task D2 — UI form와 prompt/postprocess

- [x] **D2 완료**

**Objective:** UI settings를 provider prompt와 size/corner-preserving postprocess에 연결한다.

**Files:**
- Modify: `index.html`
- Modify: `src/main.js`
- Modify: `server.py`
- Modify: `styles/app.css`
- Test: `tests/test_ui_family_workflow.py`

**Prompt exclusions:** baked text, fake numbers, full-screen mockup, character scene, watermark.

Evidence:
- Complete accessible UI authoring form and exact D1 nested schema; browser/server strict validation with 16,384 dimension/edge bounds and slice-fit checks
- Prompt carries every reusable-component setting and explicit typography/numeral/branding/device-wide/figure-scene exclusions
- UI postprocessor is byte-preserving, reports exact contract/dimensions and PASS/WARN dimension status, and is isolated on both generation routes
- Browser: all controls/read-only invariants visible, exact payload, exclusions verified, history unchanged; duplicate region/state gap found via acceptance and fixed
- D1/D2 focused 133 passed; full 567 passed; syntax/compile/diff PASS
- Scope: no D3 preview/QA or D4 export
- Review: SPEC PASS / QUALITY APPROVED

---

## Task D3 — 9-slice/resize/state/assembly preview와 QA

- [x] **D3 완료**

**Objective:** corner/edge/center와 safe area가 실제 resize에서 유지되는지 확인한다.

**Files:**
- Modify: `index.html`
- Modify: `src/main.js`
- Modify: `styles/app.css`
- Create: `tests/test_ui_nine_slice_preview.py`

**Preview:** 1:1, guides, small/medium/large, temporary text/icon/content, state comparison, integer scale.

**QA:** stretched corners, non-seamless tiled edge, safe-area violation, state size drift, baked text.

Evidence:
- 8개 preview mode(source/guides/small/medium/large/assembly/state-comparison/integer-scale), common state reuse label, temporary safe-area assembly 및 deterministic QA 구현
- 독립 review에서 발견된 zero center-span tile seam 허위 경고를 신규 RED로 재현하고 해당 축 비교만 생략하도록 수정
- preflight 검증을 실제 `preflightUiPreview → canvas allocation → getImageData` runtime 순서에 맞춰 강화
- GREEN: D3 34 passed; 전체 UI focused 132 passed; `node --check src/main.js`; `git diff --check` PASS
- Browser synthetic fixture: 8개 mode 실행, QA PASS, history/canvas mutation 없음
- Review: SPEC PASS / QUALITY APPROVED

---

## Task D4 — UI export

- [x] **D4 완료**

**Objective:** text-free state assets와 9-slice metadata를 export한다.

**Files:**
- Modify: `src/main.js`
- Modify: `index.html`
- Create: `tests/test_ui_export_manifest.py`

**Outputs:** state PNG/ZIP, sourceSize, slice margins, safe area, padding, stretch/tile modes.

Evidence:
- Strict RED: UI package builder/state PNG/manifest/ZIP/budget/path/download wiring 부재로 `2 failed, 9 errors` 확인
- GREEN: horizontal/vertical/base-reused state source를 resize 없이 RGBA byte-exact PNG로 분리하고 deterministic ZIP + manifest 구현
- Safety: source/output/archive budget preflight, state drift 거부, traversal/filename collision fail-closed, busy `finally` 복구, provider/history/Fabric mutation 없음
- Focused D4 11 passed; 관련 UI suites PASS; `node --check src/main.js`; `git diff --check` PASS
- Browser artifact: `ui-state-package.zip` 1,652 bytes, SHA-256 `55bcc35577965cd05276b8fd6509dcfa38f7f151b9dc8ba53d03be53a84decdc`; manifest + 3 state PNG; Python `zipfile`/Pillow 독립 round-trip; console error 0; history/canvas unchanged
- Review: SPEC PASS / QUALITY APPROVED

---

# Milestone E — World Object

## Task E1 — Object production contract RED tests

- [x] **E1 완료**

**Objective:** object를 world sprite와 inventory icon으로 구분하고 placement metadata를 요구한다.

**Files:**
- Create: `tests/test_object_family_workflow.py`

**Contract:**

- world/icon use
- subtype/form/material/function
- view
- tile/character-relative scale
- source canvas/padding
- pivot
- ground/Y-sort point
- shadow policy
- states/variants
- collision shape
- interaction point
- placement/snap/custom properties

Evidence:
- 현재 지원되는 usage/view를 가짜 누락으로 만들지 않고 flat facade가 손실하는 E1 semantic contract만 12개 RED로 고정
- Browser production builder/helpers와 server normalizer를 실제 실행해 nested semantics, zero-safe values, family isolation, legacy 정책 중립성을 검증
- 최초 exact schema 과잉 제약을 독립 SPEC review에서 발견해 제거하고 master-plan semantic contract 중심으로 수정
- Test harness: comment/string/template/regex-safe lexical extraction, production helper/constant 실행, deep-copy fixture, 중립 validation exceptions
- RED: 12 collected / 12 failed — 모두 현재 flat Object facade와 nested validation 부재 때문; py_compile/diff PASS
- Review: SPEC PASS / QUALITY APPROVED

---

## Task E2 — Object form와 prompt/postprocess

- [x] **E2 완료**

**Objective:** object settings를 family prompt와 alpha/pivot/state-preserving path에 연결한다.

**Files:**
- Modify: `index.html`
- Modify: `src/main.js`
- Modify: `server.py`
- Modify: `styles/app.css`
- Test: `tests/test_object_family_workflow.py`

**Do not:** object를 UI card/icon mockup이나 actor action sheet로 생성하지 않는다.

Evidence:
- Strict GREEN: E1 nested semantics를 32개 visible Object controls → browser payload → strict server normalization → canonical provider prompt → Object-only postprocess로 연결
- Prompt: server-authoritative assembly, untrusted canonical JSON fence, literal delimiter collision escape, policy-after-data, actor/UI/tile/effect/scene/text/baked-VFX exclusions
- Safety: JSON depth/node/key/string/serialized-byte budgets, recursive prototype keys 거부, finite/safe integers, source canvas/padding bounds·pixel budget, provider image byte/format/dimension/decode work preflight
- Preservation: provider bytes/alpha/source canvas/pivot/ground/Y-sort/states/variants/collision/interaction/custom metadata 보존; 단일 실제 이미지와 요청 states를 정직하게 구분; dimension mismatch WARN
- Browser: non-default/zero sentinel 32 controls, nested payload/prompt 도달, console 0, history/canvas unchanged, provider 호출 없음
- Tests: Object 26; 관련 payload 75; 확장 family 262; full regression 638 passed; py_compile/node/diff PASS
- Review: SPEC PASS / QUALITY APPROVED

---

## Task E3 — Map placement/collision/state preview와 QA

- [x] **E3 완료**

**Objective:** object를 실제 tile grid와 character scale에 배치해 검증한다.

**Files:**
- Modify: `index.html`
- Modify: `src/main.js`
- Modify: `styles/app.css`
- Create: `tests/test_object_placement_preview.py`

**Preview:** tile grid, character scale, pivot, ground/Y-sort, collision, interaction, states, shadow modes, icon derivative.

**QA:** wrong footprint, floating ground point, pivot mismatch, state size drift, collision out of bounds.

Evidence:
- Strict RED→GREEN: 실제 tile/character scale, pivot-origin/ground/Y-sort/snap, box/polygon collision, interaction radius, shadow none/contact/soft+baked suppression, icon contain/fit/crop, metadata state selector/requested-only 구현
- QA: exact displayed state RGBA single-pass alpha/contact 분석, stable 5 reasons, FAIL>WARN>PASS, source common-canvas/pivot drift 구분
- Safety: strict finite/normalized geometry, box/polygon bounds, duplicate/zero-edge/self-intersection/degenerate polygon 거부, source/state/snap/polygon/label/DOM/canvas budgets와 allocation-before-read preflight
- Browser: 512×384; tile 32; object 64×48; character 48; origin/ground overlays; state base/closed/open(requested-only); network/Fabric mutation/console error 0
- Tests: E3 10; E1–E3 36; 확대 관련 85; node/py_compile/diff PASS
- Review: SPEC PASS / QUALITY APPROVED

---

## Task E4 — Object export

- [x] **E4 완료**

**Objective:** object를 engine-usable package로 export한다.

**Files:**
- Modify: `src/main.js`
- Modify: `index.html`
- Create: `tests/test_object_export_manifest.py`

**Outputs:** PNG, state ZIP/atlas, pivot, ground point, collision, interaction, world scale/footprint, custom properties, icon derivative, optional separate shadow.

Evidence:
- Strict RED→GREEN: deterministic `asset-studio.object-package/v1`, 실제 state PNG+horizontal atlas, requested-only honesty, common sourceSize/pivot/ground/Y-sort, collision/interaction/scale/footprint/snap/custom metadata
- Derivatives: deterministic nearest-neighbor icon contain/fit/crop; actual separate shadow only, baked duplicate suppression
- Safety: full-plan preflight before canvas/pixel/PNG/ZIP; state/path/case/reserved checks; contract JSON/manifest/work/archive/file budgets; safe arithmetic; valid fixed DOS epoch + Unix 0100644 attrs
- Integrity: payload-only inventory policy, independent Python CRC32/SHA-256/bytes/timestamp/attrs, malformed/truncated/unsafe/local-central/checksum mutation audits
- Browser artifact: `/tmp/e4-independent-browser-object-package.zip`, 22,030 bytes, SHA-256 `1b0a0937ca9f08ed13c4c579db0eca009ca5be59a7ceaeb96688d67e8ac0a733`, 7 entries; console/network/history/Fabric mutation 0
- Tests: Object export 6; 4-family export 56; spec-stage full regression 652 passed; node/py_compile/diff PASS
- Review: SPEC PASS / QUALITY APPROVED

---

# Milestone F — Phase 2 통합 리뷰

## Task F1 — Cross-family spec review

- [x] **F1 완료**

**Objective:** 네 family와 actor/effect가 Anti-Facade Gate를 충족하는지 독립 검토한다.

**Review matrix:**

- core request visible
- family draft preserved
- visible setting → payload → prompt trace
- postprocess isolation
- preview is use-specific
- QA exists
- export is engine-usable
- no hidden actor fallback
- duplicate paid request guard
- accessibility tab behavior

**Output:** `docs/history/milestones/ASSET_FAMILY_PHASE_2_REPORT.md`

---

## Task F2 — Phase 2 full verification

- [x] **F2 완료**

**Commands:** focused family tests, `py_compile`, `node --check`, full `pytest`, `git diff --check`.

**Browser:** all family tabs, representative payloads, one runtime interaction per family preview/export, downloads, console 0.

**Gate:** new regressions or missing browser path가 있으면 Phase 3로 가지 않는다.

Evidence:
- Automated: full `pytest` 722 passed / 0 failed / 53 warnings; 28 Python files compile; JS syntax and diff whitespace PASS
- Localhost-only browser: Actor/Effect/Tile/UI/Object representative preview·QA·actual ZIP Blob paths PASS; cloudflare/provider calls 0
- Actor ZIP 54,744 bytes SHA-256 `ff2cddde0506bec1bfa491983da80ab6ef0455cf1bf219a855b8d9d2a1cc2a02`; strict visual approval/reset verified
- Effect full/trim ZIPs PASS; Tile package 9,273 bytes PASS; UI package 924,313 bytes PASS; Object package 596,078 bytes PASS
- Independent manifest/PNG/atlas/inventory audits PASS; console/JS errors/network generation/history/Fabric mutation 0

---

# Milestone G — Phase 3 Result Tray / Adopt / Project Restore

## Task G1 — Result model RED tests

- [x] **G1 완료**

**Objective:** 모든 family 결과가 공통 tray item envelope와 family-specific metadata를 가진다.

**Files:**
- Create: `tests/test_asset_result_tray.py`
- Modify later: `src/main.js`, `index.html`, `styles/app.css`

**Result fields:** id, family/type, status, preview URL/data, source request, normalized contract, QA summary, artifacts, adopted/rejected, timestamps, error.

---

## Task G2 — Result tray UI와 선택/비교

- [x] **G2 완료**

**Objective:** 생성 결과를 canvas에 즉시 덮지 않고 tray에서 preview/select/compare/retry/reject할 수 있게 한다.

**Files:** `index.html`, `src/main.js`, `styles/app.css`, `tests/test_asset_result_tray.py`

**Acceptance:** duplicate previews를 만들지 않고 canonical result tray를 사용한다.

---

## Task G3 — Adopt flow

- [x] **G3 완료**

**Objective:** 선택 결과를 new layer/replace source/library entry로 명시적으로 채택한다.

**Requirements:** original preservation, undo/history, family metadata attached to adopted layer, failure rollback.

---

## Task G4 — Project save/load result preservation

- [x] **G4 완료**

**Objective:** tray items, adopted state, family contract, QA, artifact refs가 project JSON에 보존·복원된다.

**Files:** `src/main.js`, `tests/test_phase11_project_v2_static.py`, new runtime tests if needed.

---

## Task G5 — Phase 3 review/report

- [x] **G5 완료**

**Output:** `docs/history/milestones/ASSET_FAMILY_PHASE_3_REPORT.md`

**Browser round-trip:** create deterministic result → adopt → save → reload → result/layer/metadata/history 확인.

---

# Milestone H — Phase 4 Project Style Profile

## Task H1 — Style profile schema RED tests

- [x] **H1 완료**

**Schema:** profile id/name, visual preset, palette, outline, lighting, material rules, pixel density, reference assets, exclusions, family overrides, version.

**Files:** Create `tests/test_project_style_profile.py`.

---

## Task H2 — Style profile UI와 family prompt 결합

- [x] **H2 완료**

**Objective:** shared style profile이 모든 family prompt에 적용되며 family-only settings를 덮지 않는다.

**Files:** `index.html`, `src/main.js`, `server.py`, `styles/app.css`.

**Acceptance:** profile은 현재 대화의 특정 게임 테마로 hard-code되지 않는다. 테마는 profile preset/data다.

---

## Task H3 — Profile save/load와 project preservation

- [x] **H3 완료**

**Objective:** profile과 family drafts가 project save/load에 보존되고 legacy project도 열린다.

---

## Task H4 — Phase 4 review/report

- [x] **H4 완료**

**Output:** `docs/history/milestones/ASSET_FAMILY_PHASE_4_REPORT.md`

---

# Milestone I — Phase 5 Family QA Providers / Export

## Task I1 — QA result schema와 provider router RED tests

- [x] **I1 완료**

**Objective:** family별 QA가 공통 verdict envelope와 family metrics를 반환한다.

**Common:** `PASS/FAIL/PARTIAL`, reasons, metrics, warnings, artifact refs, provider/method/version.

**Routes:** actor motion, effect sequence, tile topology/repeat, UI 9-slice/state, object placement/state.

---

## Task I2 — Deterministic QA providers

- [x] **I2 완료**

**Objective:** 모델 판단 이전에 deterministic geometry/alpha/metadata checks를 family별 구현한다.

**Do not:** deterministic 통과를 visual production PASS와 동일시하지 않는다.

---

## Task I3 — Optional visual QA provider integration

- [x] **I3 완료**

**Objective:** provider가 가능할 때 family-specific visual rubric으로 결과를 평가하고 deterministic metrics와 합친다.

**Guard:** 유료 호출 전 사용자 승인 범위와 저비용 1회 제한을 따른다. provider unavailable이면 deterministic-only로 명시하고 PARTIAL 처리한다.

---

## Task I4 — Unified family export center

- [x] **I4 완료**

**Objective:** 선택 result의 family를 읽어 올바른 export options와 manifest를 제공한다.

**Outputs:**

- Actor: sheets/frames/FPS/pivot
- Effect: full-cell or trim reconstruction
- Tile: atlas/rules/collision/navigation
- UI: states/9-slice/safe area
- Object: states/pivot/ground/collision/interaction

---

## Task I5 — Import/round-trip verification

- [x] **I5 완료**

**Objective:** 실제 browser 다운로드 산출물을 다시 파싱해 schema와 픽셀/offset/coordinates를 검증한다.

---

## Task I6 — Phase 5 report

- [x] **I6 완료**

**Output:** `docs/history/milestones/ASSET_FAMILY_PHASE_5_REPORT.md`

---

# Milestone J — Final Integration / Quality Gate

## Task J1 — Full independent integration review

- [x] **J1 완료**

Fresh reviewer가 전체 task delta를 검사한다.

**Review dimensions:**

- specification completeness
- cross-family contamination
- browser state/initialization
- project save/load
- metadata coordinate conventions
- export round-trip
- duplicate cost guard
- security/input validation
- accessibility
- test quality
- no unrelated dirty-tree changes

---

## Task J2 — Final automated verification

- [x] **J2 완료**

```bash
cd /Users/tajokim/asset-studio-local
PY=/Users/tajokim/.hermes/hermes-agent/venv/bin/python
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; fi
"$PY" -m py_compile server.py
node --check src/main.js
"$PY" -m pytest tests -q
git diff --check
```

- baseline failure와 신규 failure를 구분한다.
- task-introduced regression은 0이어야 한다.

---

## Task J3 — Final browser verification

- [x] **J3 완료**

실제 UI에서 최소 다음을 검증한다.

1. mouse와 keyboard로 family 전환
2. family별 draft 보존
3. representative payload 5종
4. actor animation preview
5. effect common-canvas sequence/trim round-trip
6. tile repeat/paint/topology preview
7. UI 9-slice resize/state preview
8. object placement/collision/state preview
9. result tray select/adopt/reject
10. project save/load restore
11. style profile 적용/복원
12. family export 다운로드/재파싱
13. console errors 0

실제 생성 smoke를 생략하거나 provider가 실패했다면 정확히 적는다.

---

## Task J4 — Final report와 handoff 갱신

- [x] **J4 완료**

**Files:**
- Create: `docs/history/milestones/ASSET_FAMILY_FINAL_INTEGRATION_REPORT.md`
- Modify: `SESSION_HANDOFF_2026-07-10.md`
- Update: 이 계획의 모든 checkbox/evidence

**Final report format:**

```text
Verdict: PASS / PARTIAL / FAIL
Implemented:
Verified:
Focused/full tests:
Browser path:
Generated/downloaded proofs:
Known limitations:
Dirty-tree safety:
Commit/push: not performed unless explicitly authorized
```

---

# 실행자용 최종 원칙

1. 계획을 다시 설계하느라 멈추지 말고 위 순서대로 실행한다.
2. production code 전에 failing test를 작성하고 실제 RED를 본다.
3. task마다 spec review 후 quality review를 받는다.
4. 정적 테스트를 실제 브라우저 검증으로 착각하지 않는다.
5. 패밀리 탭만 만들고 완료라고 하지 않는다.
6. 모든 visible field를 payload와 prompt까지 추적한다.
7. effect의 visible bbox와 logical frame canvas를 구분한다.
8. tile을 seamless PNG로 축소하지 않는다.
9. UI를 flattened mockup으로 만들지 않는다.
10. object를 metadata 없는 PNG로 끝내지 않는다.
11. 기존 dirty changes를 정리·삭제·되돌리지 않는다.
12. commit/push하지 않는다.
13. 실패를 숨기지 말고 `PASS / PARTIAL / FAIL`로 정확히 기록한다.
14. 한 task가 승인되면 다음 task로 계속 진행한다.
