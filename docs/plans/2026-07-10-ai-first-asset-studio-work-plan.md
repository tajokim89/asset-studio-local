# AI-First Pixel Asset Studio Implementation Plan

> **For Hermes:** Use the `subagent-driven-development` skill to implement this plan task-by-task. 사용자 승인 없이 다음 Phase로 넘어가지 않는다.

**Goal:** Pixel Asset Studio를 AI 생성 중심의 게임 에셋 제작 도구로 재구성하고, 수동 편집 기능은 `수정 모드` 안의 보조 기능으로 정리한다.

**Architecture:** 현재 `index.html` + `styles/app.css` + `src/main.js` 구조와 기존 API를 유지하면서, 먼저 화면 상태를 `ai`/`edit` 모드로 분리한다. 이후 에셋 요청을 `sprite`/`tile`/`ui`/`object` family로 정규화하고, 결과 트레이·스타일 프로필·분류별 QA를 독립 단계로 추가한다. 기존 스프라이트 계약과 dirty working tree를 보존하며 각 Phase를 별도 검증한다.

**Tech Stack:** HTML, CSS, vanilla JavaScript, Fabric.js, Python HTTP server/API, pytest, browser console/DOM verification.

**Product Spec:** `docs/plans/2026-07-10-ai-first-asset-studio-product-spec.md`

**Repository Safety:** 현재 작업 트리는 이미 dirty/untracked 상태다. 이 계획 실행 전후로 기존 변경을 정리·삭제·stash·commit하지 않는다. 각 작업은 정확한 파일만 수정하고 `git diff --check` 및 focused tests로 검증한다. 커밋은 사용자 승인 후에만 수행한다.

---

# Phase 0 — 실행 전 기준선

### Task 0.1: 현재 상태와 충돌 범위 기록

**Objective:** 기존 기능과 dirty tree를 손상하지 않도록 시작 기준선을 고정한다.

**Files:**
- Read: `SESSION_HANDOFF_2026-07-10.md`
- Read: `index.html`
- Read: `styles/app.css`
- Read: `src/main.js`
- Read: `server.py`
- Read: `tests/test_project_hygiene.py`
- Read: `tests/test_phase25_action_preset_contract_static.py`

**Step 1: 상태 확인**

Run:

```bash
git status --short
git diff --check
```

Expected:

- 기존 dirty/untracked 항목이 보인다.
- whitespace error가 없어야 한다.
- 어떤 파일도 자동 정리하지 않는다.

**Step 2: 현재 focused regression 확인**

Run:

```bash
python3 -m pytest -q \
  tests/test_project_hygiene.py \
  tests/test_phase13_pixel_asset_generator_static.py \
  tests/test_effect_asset_type_and_no_vfx_static.py \
  tests/test_phase25_action_preset_contract_static.py
```

Expected: 기존 기준선에서 모두 PASS. 실패가 있으면 새 구현 전에 pre-existing failure로 기록한다.

**Step 3: 실행 로그 기록**

새 Phase 보고서를 아직 만들지 않는다. 테스트 명령과 결과는 작업 세션 TODO 또는 최종 보고에만 기록한다.

**Commit:** 하지 않음.

---

# Phase 1 — AI 중심 화면 골격

Phase 1의 목적은 **새 AI 기능을 추가하는 것이 아니라 제품의 중심을 AI로 옮기는 것**이다. API payload와 기존 생성 로직은 변경하지 않는다.

### Task 1.1: 모드 셸 정적 계약 테스트 작성

**Objective:** AI 모드가 기본이며 고정 도구와 모드별 도구가 구분되는 DOM 계약을 먼저 고정한다.

**Files:**
- Create: `tests/test_ai_first_mode_shell_static.py`
- Later modify: `index.html`

**Step 1: 실패 테스트 작성**

테스트가 다음 ID/속성을 요구하게 한다.

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def test_ai_mode_is_default_and_mode_switch_exists():
    assert 'id="workspaceModeSwitch"' in HTML
    assert 'data-workspace-mode="ai"' in HTML
    assert 'data-workspace-mode="edit"' in HTML
    assert 'aria-pressed="true"' in HTML


def test_common_tools_stay_outside_mode_specific_groups():
    assert 'id="commonToolGroup"' in HTML
    assert 'data-tool="select"' in HTML
    assert 'data-tool="pan"' in HTML
    assert 'data-tool="region"' in HTML
    assert 'id="editToolGroup"' in HTML
```

**Step 2: 실패 확인**

Run:

```bash
python3 -m pytest -q tests/test_ai_first_mode_shell_static.py
```

Expected: FAIL — 새 DOM ID가 아직 없음.

**Step 3: 커밋 보류**

사용자 승인 없는 commit은 하지 않는다.

---

### Task 1.2: 상단 모드 전환과 도구 그룹 마크업 추가

**Objective:** 상단에 `AI 모드 | 수정 모드`를 추가하고 공통/수정 도구를 구조적으로 분리한다.

**Files:**
- Modify: `index.html:11-45`
- Test: `tests/test_ai_first_mode_shell_static.py`

**Implementation constraints:**

- `AI 모드` 버튼이 초기 `aria-pressed="true"`다.
- `수정 모드` 버튼은 초기 `aria-pressed="false"`다.
- `선택`, `이동`, `영역`은 `#commonToolGroup` 안에 둔다.
- `크롭`, `브러시`, `펜슬`, `지우개`, `마스크`, `텍스트`, `도형`, `업로드`는 `#editToolGroup` 안에 둔다.
- 기존 `data-tool` 값과 버튼 ID를 바꾸지 않는다.
- 기존 이벤트 핸들러가 그대로 찾을 수 있도록 기능 요소를 삭제하지 않는다.
- AI 모드 진입 CTA는 `AI 생성` 도구/패널과 연결한다.

**Step 1: 최소 마크업 구현**

예시 구조:

```html
<div id="workspaceModeSwitch" class="mode-switch" aria-label="작업 모드">
  <button data-workspace-mode="ai" aria-pressed="true">AI 모드</button>
  <button data-workspace-mode="edit" aria-pressed="false">수정 모드</button>
</div>

<nav class="toolrail" aria-label="Tools">
  <div id="commonToolGroup" class="tool-group">...</div>
  <div id="aiToolGroup" class="tool-group">...</div>
  <div id="editToolGroup" class="tool-group hidden">...</div>
</nav>
```

**Step 2: 테스트 실행**

Run:

```bash
python3 -m pytest -q tests/test_ai_first_mode_shell_static.py
```

Expected: PASS.

---

### Task 1.3: 작업 모드 상태와 전환 로직 추가

**Objective:** 모드 버튼을 누르면 도구와 왼쪽 패널이 바뀌고, AI 모드가 기본으로 열린다.

**Files:**
- Modify: `src/main.js` near tool activation/state initialization
- Modify: `tests/test_ai_first_mode_shell_static.py`

**Step 1: 실패 테스트 추가**

정적 테스트가 다음 계약을 확인하게 한다.

```python
JS = (ROOT / "src/main.js").read_text(encoding="utf-8")


def test_workspace_mode_state_and_switching_are_wired():
    assert "let workspaceMode = 'ai'" in JS
    assert "function setWorkspaceMode" in JS
    assert "workspaceModeSwitch" in JS
    assert "editToolGroup" in JS
```

**Step 2: 실패 확인**

Run:

```bash
python3 -m pytest -q tests/test_ai_first_mode_shell_static.py
```

Expected: FAIL.

**Step 3: 최소 구현**

필수 동작:

- 초기 상태 `workspaceMode = 'ai'`
- `setWorkspaceMode('ai' | 'edit')`
- 모드 버튼의 `aria-pressed`, active class 동기화
- AI 모드: `#aiToolGroup` 표시, `#editToolGroup` 숨김, AI 도구 활성화
- 수정 모드: `#editToolGroup` 표시, AI 생성 폼 숨김
- 공통 도구는 항상 표시
- 현재 선택/영역 정보는 모드 전환 후에도 유지
- 수정 모드에서 AI 모드로 돌아가도 캔버스/레이어/히스토리를 재생성하지 않음

**Step 4: 테스트 실행**

Run:

```bash
node --check src/main.js
python3 -m pytest -q tests/test_ai_first_mode_shell_static.py
```

Expected: syntax PASS, test PASS.

---

### Task 1.4: AI 중심 시각 계층 추가

**Objective:** AI 모드 전환과 생성 CTA를 가장 강하게 보이게 하고 수동 도구는 보조 수준으로 낮춘다.

**Files:**
- Modify: `styles/app.css`
- Modify: `tests/test_ai_first_mode_shell_static.py`

**Step 1: CSS 계약 테스트 추가**

필수 selector:

```python
CSS = (ROOT / "styles/app.css").read_text(encoding="utf-8")


def test_ai_first_mode_visual_contract_exists():
    assert ".mode-switch" in CSS
    assert ".mode-switch button[aria-pressed=\"true\"]" in CSS
    assert ".tool-group" in CSS
    assert ".ai-primary-cta" in CSS
```

**Step 2: 최소 스타일 구현**

- 상단 모드 switch는 중앙에서 명확히 보인다.
- AI 활성 버튼은 현재 accent를 사용하되 장식 과잉을 피한다.
- 생성 CTA는 왼쪽 패널 폭 전체를 사용한다.
- 수정 도구는 작은 아이콘/텍스트 계층을 유지한다.
- 기존 topbar hidden-scrollbar 규칙을 유지한다.
- 1280px에서 버튼이 겹치거나 세로로 찌그러지지 않게 한다.

**Step 3: 검사**

Run:

```bash
git diff --check
python3 -m pytest -q tests/test_ai_first_mode_shell_static.py
```

Expected: PASS.

---

### Task 1.5: 오른쪽 패널 탭 셸 정리

**Objective:** 오른쪽의 긴 패널을 `속성 | 레이어 | 내보내기` 탭으로 나누되 기존 기능을 보존한다.

**Files:**
- Modify: `index.html:113-126`
- Modify: `src/main.js`
- Modify: `styles/app.css`
- Test: `tests/test_ai_first_mode_shell_static.py`

**Step 1: 실패 테스트 작성**

필수 DOM:

- `#rightPanelTabs`
- `#propertiesPanel`
- `#layersPanel`
- `#exportPanel`
- `#historyDisclosure`

**Step 2: 최소 구현**

- 속성 탭: Transform, Appearance/Text
- 레이어 탭: layer controls와 layers list
- 내보내기 탭: 배경 제거, 캔버스/내보내기, 분류별 도구의 현재 위치를 임시 보존
- 히스토리: 접이식 영역
- 기존 ID는 이동만 하고 삭제/변경하지 않는다.
- 선택한 탭은 localStorage에 저장해도 되지만 Phase 1 필수는 아니다.

**Step 3: 테스트/문법 검사**

Run:

```bash
node --check src/main.js
python3 -m pytest -q tests/test_ai_first_mode_shell_static.py tests/test_phase7a_static.py
```

Expected: PASS.

---

### Task 1.6: Phase 1 브라우저 검증

**Objective:** 외부 URL에서 실제 모드 전환과 기존 기능 보존을 확인한다.

**Files:**
- No code unless verification finds defects.

**Automated checks:**

```bash
python3 -m pytest -q \
  tests/test_ai_first_mode_shell_static.py \
  tests/test_phase7a_static.py \
  tests/test_phase13_pixel_asset_generator_static.py \
  tests/test_phase14_animation_preview_static.py \
  tests/test_project_hygiene.py
git diff --check
node --check src/main.js
```

**Browser checks:**

1. 캐시 버스트 URL로 외부 터널 접속.
2. 초기 모드가 AI인지 확인.
3. 선택/이동/영역이 항상 보이는지 확인.
4. 수정 모드에서 크롭/브러시/펜슬/지우개가 나타나는지 확인.
5. AI 모드로 돌아오면 생성 패널이 다시 보이는지 확인.
6. 캔버스와 레이어가 모드 전환 후 유지되는지 확인.
7. 오른쪽 탭 전환 확인.
8. 콘솔 JS 오류 0건 확인.
9. 1280px와 좁은 viewport에서 topbar scrollbar가 보이지 않는지 확인.

**Phase gate:** 결과와 외부 URL을 보고하고 멈춘다. 사용자 승인 전 Phase 2를 시작하지 않는다.

---

# Phase 2 — 에셋 분류와 조건부 설정

### Task 2.1: asset family 정적 계약 테스트 작성

**Objective:** 네 대분류와 하위 타입 계약을 테스트로 고정한다.

**Files:**
- Create: `tests/test_asset_family_ui_static.py`
- Create: `tests/test_asset_family_payload_contract.py`
- Later modify: `index.html`, `src/main.js`, `server.py`

**Required families:**

```text
sprite: character, monster, npc, effect
tile: floor, wall, corner, door, terrain, decal, autotile, tileset
ui: main_panel, inner_panel, popup, card, button, slot, badge, hud_chip, gauge, icon, cursor
object: item, equipment, weapon, loot, furniture, machine, prop, interactable, destructible
```

**Failure expectation:** 현재는 flat `pixelAssetType`이므로 테스트 FAIL.

---

### Task 2.2: 대분류 탭과 하위 종류 UI 추가

**Objective:** AI 새 에셋 제작 화면에 네 family 탭과 동적 하위 타입을 추가한다.

**Files:**
- Modify: `index.html` AI panel
- Modify: `src/main.js`
- Modify: `styles/app.css`
- Test: `tests/test_asset_family_ui_static.py`

**Requirements:**

- `#assetFamilyTabs`
- `#assetSubtype`
- `#spriteSettings`
- `#tileSettings`
- `#uiSettings`
- `#objectSettings`
- family 변경 시 해당 설정만 표시
- 기존 `pixelAssetType`은 내부 호환용으로 유지하거나 명확한 migration helper를 둔다.
- 사용자에게 raw backend key보다 한국어 label을 보여준다.

---

### Task 2.3: 스프라이트 설정 분기

**Objective:** actor sprite와 effect sprite의 설정을 분리한다.

**Files:**
- Modify: `src/main.js`
- Modify: `index.html`
- Test: `tests/test_asset_family_ui_static.py`
- Test: existing sprite tests

**Requirements:**

- character/monster/npc: direction, action, frame controls 표시
- effect: effect category, loop, frame count, pivot 표시
- effect에서 actor direction/reference-direction/equipment controls 숨김
- 기존 `walk4 = N → L → N → R` 계약 변경 금지
- 기존 action 7-lock QA 변경 금지

---

### Task 2.4: 타일 전용 설정

**Objective:** tile family에만 tile size, layout, seamless, connection controls를 표시한다.

**Files:**
- Modify: `index.html`
- Modify: `src/main.js`
- Test: `tests/test_asset_family_ui_static.py`

**Required fields:**

- `tileSize`
- `tileLayout`
- `tileRows`, `tileCols`
- `tileSeamless`
- `tileConnections`
- `tileVariants`

**Acceptance:** animation/direction controls hidden; prompt/payload에 tile contract 포함.

---

### Task 2.5: UI 전용 설정

**Objective:** UI 제작에 필요한 실제 크기, 9-slice, 안전영역, 상태 세트를 제공한다.

**Files:**
- Modify: `index.html`
- Modify: `src/main.js`
- Test: `tests/test_asset_family_ui_static.py`

**Required fields:**

- `uiWidth`, `uiHeight`
- `uiNineSlice`
- `uiNineSliceMargin`
- `uiSafeArea`
- `uiBorderWeight`
- `uiCornerStyle`
- `uiDecorationDensity`
- `uiTextFree` default true
- `uiStates`

**Acceptance:** UI는 항상 `animation_mode: ui_static`, `direction_mode: none`, `frame_count: 1`; sprite residue cleanup 경로를 타지 않는다.

---

### Task 2.6: 오브젝트 전용 설정

**Objective:** 월드 오브젝트의 시점, 피벗, 크기, 변형을 제공한다.

**Files:**
- Modify: `index.html`
- Modify: `src/main.js`
- Test: `tests/test_asset_family_ui_static.py`

**Required fields:**

- `objectView`
- `objectWorldScale`
- `objectPivot`
- `objectShadow`
- `objectVariants`
- `objectState`
- `objectUsage`: world/icon

---

### Task 2.7: payload normalizer 추가

**Objective:** 분류와 무관한 옵션이 서버에 전송되지 않도록 payload를 정규화한다.

**Files:**
- Modify: `src/main.js` near `generateAiAsset()`
- Modify: `server.py` request parsing
- Test: `tests/test_asset_family_payload_contract.py`

**Required function shape:**

```javascript
function buildAssetGenerationPayload() {
  const family = currentAssetFamily();
  const payload = { asset_family: family, asset_type: currentAssetSubtype(), ... };
  if (family === 'sprite') payload.sprite = buildSpriteContract();
  if (family === 'tile') payload.tile = buildTileContract();
  if (family === 'ui') payload.ui = buildUiContract();
  if (family === 'object') payload.object = buildObjectContract();
  return payload;
}
```

**Contract assertions:**

- UI payload에 sprite direction/action 없음
- tile payload에 animation 없음
- object payload에 sprite cleanup 없음
- actor sprite payload에는 action/direction/frame count 있음
- effect payload에는 actor body/equipment contract 없음

**Focused tests:**

```bash
python3 -m pytest -q \
  tests/test_asset_family_payload_contract.py \
  tests/test_effect_asset_type_and_no_vfx_static.py \
  tests/test_phase25_action_preset_contract_static.py
```

---

### Task 2.8: Phase 2 브라우저 검증

**Checks:**

- family 네 개 전환
- 각 family에서 전용 설정만 표시
- UI 선택 시 9-slice와 상태가 보임
- effect 선택 시 방향 설정이 사라짐
- sprite actor 선택 시 기존 action 설정 복구
- 브라우저에서 최종 payload를 non-costly stub/console hook으로 확인
- 실제 생성 호출은 사용자 승인 또는 low-cost smoke 범위에서만 수행
- 콘솔 오류 0건

**Phase gate:** 외부 URL, 테스트 수, payload 예시를 보고하고 멈춘다.

---

# Phase 3 — AI 결과 트레이

### Task 3.1: 결과 상태 모델 테스트

**Objective:** 생성 결과와 캔버스 레이어를 분리한다.

**Files:**
- Create: `tests/test_ai_result_tray_static.py`
- Modify later: `src/main.js`, `index.html`, `styles/app.css`

**State shape:**

```javascript
{
  id,
  family,
  subtype,
  url,
  prompt,
  createdAt,
  status: 'ready' | 'failed' | 'adopted',
  metadata
}
```

### Task 3.2: 결과 트레이 UI

**Required controls:**

- 후보 thumbnail
- 확대/선택
- 캔버스에 추가
- 새 변형
- AI 수정으로 전달
- 삭제
- 실패 결과 접기

### Task 3.3: 생성 성공 경로 연결

- 성공 결과는 트레이에 추가
- 자동 canvas insertion을 제거하거나 명확한 opt-in으로 바꿈
- 기존 갤러리는 migration 기간 동안 결과 트레이와 중복되지 않게 정리
- 채택 후에만 canvas layer 생성

### Task 3.4: 프로젝트 저장/불러오기

- 결과 트레이 상태를 project JSON v2 확장 필드에 저장
- legacy load 유지
- adopted/failed 상태 복원

### Task 3.5: Phase 3 검증

- 후보 2개 mock 추가
- 하나만 캔버스에 채택
- 삭제/복구
- 프로젝트 저장/불러오기
- 레이어와 결과 상태가 섞이지 않는지 확인

---

# Phase 4 — 프로젝트 스타일 프로필

### Task 4.1: 프로필 스키마와 테스트

**Files:**
- Create: `tests/test_project_style_profile_static.py`
- Modify later: `src/main.js`, `index.html`

**Schema:**

```javascript
{
  id,
  name,
  pixelDensity,
  palette,
  primaryMaterial,
  secondaryMaterial,
  outline,
  shadingSteps,
  lightDirection,
  cameraView,
  exclusions,
  referenceLayerId,
  notes
}
```

### Task 4.2: 스타일 프로필 UI

- 프로필 선택
- 새 프로필
- 이름 변경
- 저장
- 복제
- 삭제는 확인 필요
- 선택 이미지 스타일 참조

### Task 4.3: prompt/payload 결합

- family prompt보다 앞서 공통 style contract 생성
- 사용자가 직접 쓴 핵심 요청을 덮어쓰지 않음
- exclusions를 Negative에 병합하되 중복 제거

### Task 4.4: 프로젝트 JSON 보존

- profiles와 activeProfileId 저장
- legacy 프로젝트는 기본 프로필 생성

### Task 4.5: Phase 4 검증

- 프로필 저장/전환
- 네 family payload에 같은 profile ID/스타일이 반영
- reload 후 복원
- 콘솔 오류 0건

---

# Phase 5 — 분류별 QA와 내보내기

### Task 5.1: QA provider interface

**Objective:** family별 QA를 공통 인터페이스로 호출한다.

```javascript
runAssetQa(result) -> {
  family,
  pass,
  checks,
  artifacts
}
```

### Task 5.2: 스프라이트 QA 연결

- 기존 7-lock과 action whitelist 재사용
- alpha/frame/cell cleanup은 plumbing QA로만 표시
- 명확한 PASS/FAIL

### Task 5.3: 타일 QA

- edge pixel 비교
- 3×3 반복 proof
- seam count
- 연결 세트 누락 검사

### Task 5.4: UI QA

- corner alpha
- text/logo/watermark 유무
- 내부 절단선
- 9-slice 확대 proof
- safe area 크기
- state dimension consistency

### Task 5.5: 오브젝트 QA

- corner alpha
- subject bounds
- bottom-center pivot
- game-scale preview
- variant identity consistency

### Task 5.6: 분류별 내보내기

- sprite: sheet PNG, frame ZIP, GIF preview
- tile: tileset PNG, tile ZIP, manifest
- UI: component PNG, state ZIP, 9-slice metadata JSON
- object: transparent PNG, variant ZIP, pivot metadata JSON

### Task 5.7: Phase 5 검증

각 family에서 하나의 mock 또는 승인된 실제 에셋을 사용해 전체 QA와 export를 확인한다. 실제 AI 비용 호출 없이 가능한 검증을 우선하고, 실제 생성 smoke는 사용자 승인 후 진행한다.

---

# 공통 테스트 명령

## 빠른 정적/문법 검사

```bash
node --check src/main.js
git diff --check
python3 -m pytest -q tests/test_project_hygiene.py
```

## Phase 1 회귀

```bash
python3 -m pytest -q \
  tests/test_ai_first_mode_shell_static.py \
  tests/test_phase7a_static.py \
  tests/test_phase13_pixel_asset_generator_static.py \
  tests/test_phase14_animation_preview_static.py
```

## Phase 2 회귀

```bash
python3 -m pytest -q \
  tests/test_asset_family_ui_static.py \
  tests/test_asset_family_payload_contract.py \
  tests/test_effect_asset_type_and_no_vfx_static.py \
  tests/test_phase21_sprite_action_matrix.py \
  tests/test_phase25_action_preset_contract_static.py \
  tests/test_phase26_walk_anchor_and_gif_static.py
```

## 전체 테스트

```bash
python3 -m pytest -q
```

전체 테스트는 focused tests가 모두 통과한 뒤 실행한다.

# 외부 URL 검증 규칙

각 Phase 완료 시:

1. 의도한 app server와 tunnel만 사용한다.
2. 캐시 버스트 query를 붙인다.
3. 외부 URL에서 페이지 title과 고유 UI label을 확인한다.
4. 핵심 상호작용을 직접 클릭한다.
5. 브라우저 console 오류를 확인한다.
6. 사용자에게 검증한 URL 하나만 전달한다.
7. 이전 stale tunnel은 전달하지 않는다.

# 완료 보고 형식

```text
[검증된 외부 URL]

Phase N 완료. commit/push는 하지 않았습니다.
- 적용: ...
- 검증: focused N passed, 전체 N passed, console 0건
- 보류: 다음 Phase 항목
```

# 작업 중 금지 사항

- 기존 dirty tree 정리/stash/reset
- 사용자 승인 없는 commit/push
- Phase 1 중 backend payload 전면 수정
- UI를 한 번에 전면 재작성
- 기존 스프라이트 계약 완화
- UI/tile/object에 sprite action defaults 전송
- AI 결과의 자동 원본 덮어쓰기
- 수동 편집 기능 삭제
- 검증하지 않은 외부 URL 전달

# 첫 실행 단위

사용자가 작업 시작을 승인하면 **Phase 0 기준선 확인 후 Phase 1만** 실행한다.

Phase 1의 최종 인수 기준:

- AI 모드가 기본이다.
- 선택/이동/영역이 항상 보인다.
- 브러시/펜슬/지우개/크롭 등은 수정 모드에만 보인다.
- 모드 전환이 캔버스, 레이어, 히스토리를 잃지 않는다.
- 기존 AI 생성 경로가 여전히 열린다.
- 오른쪽 패널이 속성/레이어/내보내기로 분리된다.
- 외부 URL에서 실제 동작한다.
- focused tests와 기존 핵심 회귀가 PASS다.
- 사용자 확인 전 Phase 2를 시작하지 않는다.
