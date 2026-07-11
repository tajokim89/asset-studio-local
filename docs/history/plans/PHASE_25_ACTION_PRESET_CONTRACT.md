# Phase 25 — Action Preset Contract 정리 계획

> **For Hermes / Coding Agent:** 이 문서를 먼저 읽고, 아래 `Goal Prompt` 지시대로 구현한다.
> 사용자는 Phase 단위 검증을 선호한다. 이 Phase에서는 액션 프리셋 계약 정리, 프롬프트/프레임 수 정합성, 정적 테스트/브라우저 검증, 보고서 작성까지만 수행한다.

## Goal

idle 외 동작(`walk`, `attack`, `jump`, `cast`, `hurt`, `death`)이 UI/프론트 프롬프트/서버 action matrix/API payload/QA에서 같은 계약으로 처리되도록 전체 정합성을 맞춘다.

현재 문제는 모델 성능만이 아니라 **UI 액션 목록과 서버 액션 계약이 불일치하는 구조 문제**다. 이 Phase의 목표는 모델이 idle 외 동작을 더 안정적으로 생성할 수 있도록 액션별 frame beat sheet와 검증 기준을 코드에 명확히 넣는 것이다.

---

## Current Findings

### 1. 서버 `SPRITE_ACTION_MATRIX`가 UI 액션 목록보다 부족함

프론트 UI/프롬프트는 다음 동작을 다룬다.

- `idle`
- `walk4`
- `walk6`
- `attack`
- `jump`
- `cast`
- `hurt`
- `death`

하지만 서버 `server.py`의 `SPRITE_ACTION_MATRIX`는 현재 대략 아래만 가진다.

- `idle`
- `walk`
- `attack`
- `hit`
- `death`

문제:

- `jump` 계약 없음
- `cast` 계약 없음
- UI는 `hurt`인데 서버는 `hit`
- `death4`/`attack4`/`walk6` 같은 payload key normalize가 부족할 수 있음
- `idle4`처럼 프론트가 보내는 animation key와 서버 matrix key가 완전히 일치하지 않음

### 2. idle은 쉬운 동작이고, 다른 동작은 frame beat sheet가 필요함

idle은 거의 같은 포즈에서 호흡만 표현하면 되므로 모델이 상대적으로 잘 맞춘다.

반대로 아래 동작은 구체적 프레임 순서가 없으면 쉽게 무너진다.

- `walk`: 다리/팔 교대가 가짜 복붙 프레임으로 나올 수 있음
- `attack`: 무기/팔/이펙트가 셀 경계 밖으로 나갈 수 있음
- `jump`: pivot/baseline이 흔들릴 수 있음
- `cast`: 이펙트가 캐릭터를 덮거나 다른 그림처럼 나올 수 있음
- `hurt`: 캐릭터 정체성/방향이 무너질 수 있음
- `death`: 마지막 프레임이 down/still로 고정되지 않을 수 있음

### 3. `walk6`가 실제 6프레임으로 강제되지 않을 수 있음

`src/main.js`의 `requestedPixelFrameCount()`는 현재 `pixelWalkFrames` 값을 모든 actor animation frame count로 사용한다.

따라서 UI에서 `walk6`를 골라도 `pixelWalkFrames` 값이 4면 실제 payload가 `frame_count: 4`가 될 수 있다.

### 4. QA가 action-specific하지 않음

현재 QA는 주로 geometry/grid/chroma/alpha/direction 중심이다. 추가로 액션별 최소 정적 검증이 필요하다.

예:

- `walk`: `walk4/walk6`가 각각 기대 frame count를 갖는지
- `attack`: frame order가 ready/wind-up/strike/recover를 포함하는지
- `jump`: crouch/takeoff/air/landing beat가 prompt에 들어가는지
- `cast`: VFX가 셀 안에 제한된다는 문구가 들어가는지
- `hurt`: `hurt`와 legacy `hit`가 같은 계약으로 normalize되는지
- `death`: 마지막 프레임이 down/still/dead 계열로 끝나야 함

### 5. 배경 제거 후 잔여 테두리/셀 경계가 남는 문제

사용자 첨부 예시 이미지: `/Users/tajokim/.hermes/image_cache/img_d02a939b0d1b.png`

관찰 내용:

- 스프라이트 주변과 셀 사이에 매우 어두운 초록/검정 계열 배경 잔여물이 남아 있음.
- 각 프레임 셀의 사각형 경계선이 희미하게 보임.
- 배경 제거 후 투명해야 할 영역이 완전히 alpha 0이 아니라 잔상/halo처럼 남아 보임.
- 캐릭터 외곽 주변의 chroma spill 또는 dark fringe가 깨끗하게 제거되지 않음.

따라서 Phase 25에는 action preset 계약뿐 아니라, **프레임 생성 후 배경 제거/테두리 클린업 QA**도 포함한다.

---

## Required Implementation Scope

### A. 액션 계약을 단일 소스에 가깝게 정리

가능하면 프론트/서버 각각에 흩어진 액션 정의를 같은 내용으로 맞춘다. 대규모 리팩터는 피하고, 이번 Phase에서는 최소한 아래 정합성을 달성한다.

서버 `server.py`의 `SPRITE_ACTION_MATRIX`는 다음 canonical action을 모두 가져야 한다.

```text
idle
walk
attack
jump
cast
hurt
death
```

권장 기본 frame count:

```text
idle: 4
walk: 4 또는 6
attack: 4
jump: 4
cast: 4
hurt: 4
death: 4 또는 6
```

주의:

- 기존 테스트/파이프라인이 `idle`을 1프레임으로 가정하는 곳이 있으면 즉시 깨지지 않게 확인한다.
- `ui_static`은 여전히 1프레임이어야 한다.
- source 이미지 기반 action generation의 payload가 `idle4`, `walk4`, `walk6`, `attack4`, `jump4`, `cast4`, `hurt4`, `death4`처럼 들어와도 서버에서 canonical action으로 normalize되게 한다.
- legacy `hit`는 `hurt`의 alias로 유지한다.

### B. animation key normalize 함수 추가/정리

서버에 명시적 normalize helper를 둔다.

예상 형태:

```python
def normalize_animation_action(animation_mode: str) -> str:
    raw = str(animation_mode or "idle").strip().lower()
    aliases = {
        "idle4": "idle",
        "walk4": "walk",
        "walk6": "walk",
        "attack4": "attack",
        "jump4": "jump",
        "cast4": "cast",
        "hurt4": "hurt",
        "hit": "hurt",
        "hit2": "hurt",
        "death4": "death",
        "death6": "death",
        "static1": "ui_static",
        "ui_static": "ui_static",
    }
    if raw in aliases:
        return aliases[raw]
    # fallback: strip trailing digits, then alias again
    stripped = re.sub(r"\d+$", "", raw)
    return aliases.get(stripped, stripped if stripped in SPRITE_ACTION_MATRIX else "idle")
```

단, 실제 구현은 현재 코드 구조에 맞춰 조정한다.

### C. 프론트 `animationPresetSpec()`와 `requestedPixelFrameCount()` 정리

`src/main.js`에서 프레임 수가 프리셋과 맞게 결정되도록 한다.

권장 방향:

- `walk6` 선택 시 기본 `frames: 6`
- `walk4` 선택 시 `frames: 4`
- `idle` 기본 `frames: 4`
- `attack/jump/cast/hurt` 기본 `frames: 4`
- `death`는 우선 `4` 또는 현재 UX가 허용하면 `6`; 서버와 프론트 일치가 우선
- `pixelWalkFrames`를 모든 동작에 무조건 적용하지 말고, 프리셋별 기본값/override 정책을 명확히 한다.

최소 구현 예:

```js
const PIXEL_ANIMATION_PRESET_DEFAULT_FRAMES = {
  idle: 4,
  walk4: 4,
  walk6: 6,
  attack: 4,
  jump: 4,
  cast: 4,
  hurt: 4,
  death: 4,
  ui_static: 1,
};
```

그리고 `animationPresetSpec()`는 `walk6`에서 `key: 'walk6', frames: 6`처럼 실제 payload와 UI가 일치해야 한다.

### D. 액션별 frame beat sheet 강화

프론트 prompt와 서버 prompt 계약 둘 다 아래 내용을 포함하도록 정리한다.

#### idle 4f

```text
1. neutral stance
2. subtle breath up
3. neutral stance
4. subtle breath down
```

#### walk 4f

```text
1. contact A
2. passing A
3. contact B
4. passing B
```

#### walk 6f

```text
1. contact A
2. down A
3. passing A
4. contact B
5. down B
6. passing B
```

#### attack 4f

```text
1. ready pose
2. wind-up, weapon/arm pulled back
3. strike/impact, arc stays inside cell
4. recovery, returns toward stance
```

#### jump 4f

```text
1. crouch/anticipation
2. takeoff
3. airborne peak
4. landing/recovery
```

#### cast 4f

```text
1. ready pose
2. gather small magic/energy
3. release contained effect
4. recover, effect fades
```

#### hurt 4f

```text
1. normal pose
2. impact flinch
3. recoil
4. recovery
```

#### death 4f

```text
1. alive/impact
2. collapse
3. down
4. dead/still
```

공통 필수 문구:

```text
Preserve same identity, direction, costume, scale, palette, pivot, and baseline across all frames.
Every body part, weapon, motion smear, slash arc, VFX, shadow, and silhouette must stay fully inside its own cell.
Do not cross cell boundaries. Do not create different characters per frame. No text, labels, numbers, watermark.
```

### E. 배경 제거/테두리 클린업 강화

프레임 생성 결과를 배경 제거한 뒤, 아래 문제가 남지 않도록 후처리와 QA를 강화한다.

필수 처리 방향:

- chroma green/near-black/very dark green background residue를 alpha 0으로 제거한다.
- 셀 사이에 남는 희미한 사각형 border/grid line을 제거한다.
- 캐릭터 외곽의 green spill/dark fringe/halo를 최대한 정리한다.
- 캐릭터 본체 픽셀은 과도하게 깎지 않는다.
- 최종 PNG는 실제 투명 배경이어야 하며 checkerboard/black preview에서 잔여 박스가 보이면 실패로 본다.

테스트/QA 기준:

- corner alpha가 `[0,0,0,0]` 또는 동등하게 완전 투명인지 확인한다.
- 프레임 셀 gutter/경계 영역에 남은 non-transparent dark green/black-ish pixels 비율을 검사한다.
- chroma cleanup report에 residual green/dark border 지표를 추가하거나 기존 QA summary에 포함한다.
- 사용자 첨부 예시처럼 셀 박스가 보이는 결과는 실패 케이스로 문서화한다.

### F. 서버 `/api/sprite-action-matrix` 또는 기존 matrix endpoint 정적 테스트 강화

현재 `tests/test_phase21_sprite_action_matrix.py`가 있다. 이 테스트를 확장하거나 새 테스트를 만든다.

필수 검증:

1. matrix에 canonical actions가 모두 존재한다.
2. `hurt`가 존재하고, legacy `hit`는 alias 또는 호환 경로가 있다.
3. 각 action에 `frames`, `columns`, `contract`가 있다.
4. `jump`, `cast`, `hurt`, `death` columns가 beat sheet를 반영한다.
5. normalize helper가 아래 입력을 기대값으로 바꾼다.

```text
idle4 -> idle
walk4 -> walk
walk6 -> walk
attack4 -> attack
jump4 -> jump
cast4 -> cast
hurt4 -> hurt
hit -> hurt
death4 -> death
death6 -> death
static1 -> ui_static
```

### G. 프론트 정적 테스트 강화

가능하면 기존 static test에 아래 검증을 추가한다.

- `PIXEL_ANIMATION_PRESET_DEFAULT_FRAMES` 또는 동등한 구조가 존재한다.
- `walk6`는 6프레임으로 payload가 잡히는 구조다.
- `animationPresetSpec()`에 `jump`, `cast`, `hurt`, `death`가 있고 frame order/motion 문구가 있다.
- `buildSelectedActionSpritePrompt()`가 action-specific frame order를 포함한다.

### H. 브라우저/API 검증

구현 후 아래를 수행한다.

1. 정적 테스트 실행

```bash
python3 -m pytest tests/test_phase21_sprite_action_matrix.py -q
```

2. 관련 테스트 전체 실행

```bash
python3 -m pytest tests/test_phase21_sprite_action_matrix.py tests/test_phase21_sprite_visual_gate_static.py tests/test_phase21_sprite_quality_gate.py -q
```

3. 앱 서버 실행/확인

```bash
python3 server.py
```

서버가 이미 실행 중이면 새로 띄우지 말고 기존 서버를 사용하거나 포트 충돌 없이 처리한다.

4. 브라우저에서 최소 확인

- Pixel asset generator UI 열림
- animation preset에서 `walk6`, `attack`, `jump`, `cast`, `hurt`, `death` 선택 가능
- `walk6` 선택 시 프롬프트/payload가 6프레임 계약으로 보이는지 확인
- `attack/jump/cast/hurt/death` 선택 시 프롬프트에 각 beat sheet가 들어가는지 확인
- 콘솔 JS 에러 없음

5. 실제 AI 생성은 시간/비용이 크면 필수로 하지 않는다. 대신 `/api/generate-reference` payload 구성까지 브라우저/코드 레벨에서 검증한다. 사용자가 실제 샘플 생성을 요청하면 그때 1~2개만 생성한다.

---

## Files Likely to Modify

- `server.py`
  - `SPRITE_ACTION_MATRIX`
  - animation/action normalize helper
  - `/api/generate-reference` 또는 matrix를 사용하는 prompt building path
  - postprocess 조건 중 `animation_mode == "idle"` 같은 직접 비교가 있으면 normalize 적용 여부 확인

- `src/main.js`
  - `requestedPixelFrameCount()`
  - `pixelPresetFrameCount()`
  - `animationPresetSpec()`
  - `buildDirectionalSpriteSheetContract()`
  - `buildPixelAssetPrompt()`
  - `buildSelectedActionSpritePrompt()`
  - action preset change handler가 `walk6` 프레임 수를 제대로 sync하는지 확인

- `index.html`
  - animation preset option value가 실제 코드와 맞는지 확인
  - 필요 시 `attack4/jump4`처럼 option value를 바꾸지 말고, 현재 value 유지 + payload key 정합성만 맞춘다. UI 파괴 금지.

- `tests/test_phase21_sprite_action_matrix.py`
  - 서버 action matrix/normalize 테스트 확장

- 새 테스트 후보
  - `tests/test_phase25_action_preset_contract_static.py`
  - 프론트 JS 문자열 기반 정적 테스트

- 새 보고서
  - `PHASE_25_REPORT.md`

---

## Acceptance Criteria

- UI에서 제공하는 actor animation preset이 서버 canonical action contract와 모두 매핑된다.
- `walk6` 선택 시 실제 frame count가 6으로 간다.
- `jump`, `cast`, `hurt`, `death`가 서버 action matrix에 존재한다.
- `hit` legacy 이름은 `hurt`로 호환된다.
- 각 action prompt에 frame beat sheet가 들어간다.
- 정적 테스트가 normalize/action matrix/frame count 정합성을 검증한다.
- 관련 pytest가 통과한다.
- 브라우저에서 콘솔 JS 에러가 없다.
- `PHASE_25_REPORT.md`에 변경 내용, 검증 명령, 결과, 남은 한계가 기록된다.
- 작업 후 git status와 ahead/changed 상태를 보고한다.

---

## Non-goals

이번 Phase에서 하지 말 것:

- 전체 sprite generation pipeline 재작성
- 새 AI 모델/backend 교체
- 실제 모든 액션을 대량 생성해서 품질 샘플 만들기
- sprite editor/editor UX 기능 추가
- remove background/inpaint/chat 같은 별도 Phase 작업
- public repo push/commit은 사용자가 명시적으로 요청하지 않는 한 하지 않는다

---

## Goal Prompt

아래 프롬프트를 그대로 새 작업자/서브에이전트에게 전달하면 된다.

```text
You are working on the local project `/Users/tajokim/asset-studio-local`.

First read this plan file completely:
`/Users/tajokim/asset-studio-local/docs/plans/PHASE_25_ACTION_PRESET_CONTRACT.md`

Implement Phase 25 exactly as described: align the pixel/game actor animation action preset contract across the frontend UI prompt builders, frontend payload frame counts, server SPRITE_ACTION_MATRIX, server animation-mode normalization, and tests.

Critical requirements:
- Do not change unrelated editor features.
- Do not implement future phases like background removal, inpaint, AI chat, or generic editor UX.
- Keep the current UI values compatible unless a minimal change is required.
- Canonical server actions must include: idle, walk, attack, jump, cast, hurt, death.
- Legacy hit must map to hurt.
- Normalize common payload keys: idle4, walk4, walk6, attack4, jump4, cast4, hurt4, hit, death4, death6, static1.
- walk6 must produce 6 frames in frontend payload/spec, not silently 4.
- Each non-idle action must have explicit frame beat sheets and cell-boundary safety language.
- Include post-generation background cleanup: after frame/sprite-sheet generation, remove the background cleanly, erase leftover cell-border boxes, dark/green residue, chroma spill, and halo/fringe around sprites without damaging the character pixels.
- Treat results like the attached bad example `/Users/tajokim/.hermes/image_cache/img_d02a939b0d1b.png` as a failure case: visible rectangular cell boxes, dark green/black-ish leftovers, or non-transparent background residue must fail QA.
- Add or update tests so the action matrix, normalize behavior, frontend static contract, and cleanup QA are verifiable.
- Create `PHASE_25_REPORT.md` with changes, verification commands, results, and remaining limitations.

Suggested workflow:
1. Inspect `server.py`, `src/main.js`, `index.html`, and existing tests, especially `tests/test_phase21_sprite_action_matrix.py`.
2. Add/adjust server action normalization and matrix entries.
3. Adjust frontend frame-count/default/prompt logic for `walk6`, `attack`, `jump`, `cast`, `hurt`, `death`.
4. Add/extend tests for server and frontend static contract.
5. Run focused pytest commands.
6. If possible, verify in browser that selecting presets updates prompt/frame contract and console has no JS errors.
7. Write `PHASE_25_REPORT.md`.
8. Stop and report. Do not commit or push unless explicitly asked.

Return a concise Korean report with:
- modified files
- exact tests run and pass/fail
- browser verification result
- any limitations
- current git status
```
