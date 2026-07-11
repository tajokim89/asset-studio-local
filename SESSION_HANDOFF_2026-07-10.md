# Asset Studio Local — 새 세션 인수인계

작성일: 2026-07-10
프로젝트 루트: `/Users/tajokim/asset-studio-local`
로컬 URL: `http://127.0.0.1:4184`

## 1. 새 세션에서 먼저 할 일

1. 아래 문서와 현재 Git 상태를 먼저 확인한다.
   - 이 문서
   - `docs/history/milestones/PHASE_25_REPORT.md`
   - `docs/history/plans/PHASE_25_ACTION_PRESET_CONTRACT.md`
   - `git status --short`
   - `git diff --stat`
2. 현재 작업 트리는 **커밋되지 않은 변경과 실험 스크립트가 많은 dirty 상태**다. 사용자 승인 없이 reset/clean/stash/commit/push하지 않는다.
3. 서버를 다시 실행한다.

```bash
cd /Users/tajokim/asset-studio-local
./scripts/run_server.sh
```

4. 브라우저에서 `http://127.0.0.1:4184`를 열고 콘솔 오류와 실제 UI를 확인한다.

> 2026-07-10 인수인계 작성 시점의 직접 확인에서는 포트 4184가 `Connection refused`였다. 직전 대화에서는 서버 기동 watch 알림이 있었지만 현재는 내려가 있으므로 새 세션에서 재실행해야 한다.

## 2. 프로젝트 성격과 작업 원칙

Asset Studio Local은 Fabric.js 기반 로컬 AI 이미지/게임 에셋 편집기다. 일반 편집 기능, 배경 제거, 선택영역 편집, AI 생성, 방향/액션 스프라이트 생성·정리·미리보기 흐름을 한 페이지 안에서 제공한다.

중요 원칙:

- 페이지/API 파이프라인을 요청받았을 때 외부에서 만든 파일을 끼워 넣지 않는다. 실제 사이트/API 경로로 생성·정리·미리보기까지 검증한다.
- 단계별 작업 후 실제 링크/브라우저/콘솔/테스트를 확인한다.
- 스프라이트 PASS는 alpha/frame count/bbox 같은 배관 지표만으로 판정하지 않는다.
- 사용자에게는 확실한 `PASS`만 전달한다. 애매하면 `FAIL`로 보고하고 실패물을 임의로 첨부하지 않는다.
- 캐릭터 액션 시트에는 VFX를 굽지 않는다. slash arc, hit spark, glow, particle, smoke, shockwave, debris, trail 등은 `effect` 에셋으로 별도 생성한다.

## 3. 기존 구현 범위

프로젝트에는 Phase 0~25 문서가 있으며, 주요 구현 범위는 다음과 같다.

- Fabric.js 캔버스와 레이어 편집
- 업로드, 텍스트, 도형, 브러시/펜/지우개
- 레이어 생성·이름 변경·표시/잠금·순서 변경
- checkerboard/투명 배경, zoom/pan, PNG/프로젝트 저장·불러오기
- 이미지 배경 제거와 alpha 정리
- 영역 선택, mask, copy/cut/paste, 선택영역 AI 편집 연결
- AI Chat 명령 라우팅
- 도트 에셋 생성과 reference-image 생성
- 1/4/8방향, source 방향 + app-side mirror 파이프라인
- 스프라이트 자동 감지/고정 그리드/애니메이션 미리보기
- asset type별 UI 분기와 `effect` 타입
- 액션 프리셋과 cleanup QA

`README.md`의 current milestone/roadmap 문구는 Phase 9 시점이라 현재 상태보다 오래됐다. 인수인계 판단은 README보다 최신 Phase 문서와 실제 코드를 우선한다.

## 4. 최근 핵심 작업 — Phase 25 이후 액션 계약 강화

주요 변경 파일:

- `server.py`
- `src/main.js`
- `index.html`
- `scripts/archive/generate_action_preset_matrix.py`
- `tests/test_phase13_pixel_asset_generator_static.py`
- `tests/test_phase21_sprite_action_matrix.py`
- `tests/test_effect_asset_type_and_no_vfx_static.py`
- `tests/test_phase25_action_preset_contract_static.py`
- `tests/test_phase26_walk_anchor_and_gif_static.py`

반영 내용:

- canonical 액션을 `idle`, `walk`, `attack`, `jump`, `cast`, `hurt`, `death`로 정리했다.
- `hit`은 legacy alias로 `hurt`에 normalize한다.
- 기본 액션 애니메이션은 4프레임 기준이다.
- UI 기본 메뉴에서 `walk6 / walk smooth`를 제거했다. 사용자가 명시적으로 요청하지 않으면 기본 walk는 `walk4`다.
- 공통 animation lock과 액션별 positive PASS contract를 서버/프론트 프롬프트에 넣었다.
- actor 액션에서 baked VFX를 금지하고 `effect` 에셋 타입을 추가했다.
- reference 기반 actor/effect 생성 payload에 `asset_type`, `no_baked_vfx`를 전달한다.
- chroma/green/dark cell residue cleanup 및 `cleanup_qa`를 강화했다.
- UI cache-bust는 현재 `phase25-action-preset-contract`다.

## 5. 가장 중요한 최신 수정 — walk4 계약

사용자가 확정한 기본 grammar:

```text
walk4 = N → L → N → R

1: neutral still
2: left / 한쪽 support 또는 step
3: frame 1과 거의 같은 neutral still 재사용/복귀
4: right / 반대쪽 support 또는 step
```

중요:

- 네 프레임 모두를 새 walk pose로 만들지 않는다.
- frame 3은 frame 1의 neutral planted stance로 돌아와야 한다.
- frame 2와 4는 서로 반대쪽 발/support step이어야 한다.
- 같은 발만 두 번 움직이는 tap, idle fidget, hop, skate, dance는 FAIL이다.
- root/head/torso/contact baseline이 안정돼야 한다.
- prop/hand/equipment identity가 유지돼야 한다.

동기화한 위치:

- `server.py`
- `src/main.js`
- `scripts/archive/generate_action_preset_matrix.py`
- `tests/test_phase25_action_preset_contract_static.py`

관련 지속 문서:

- `/Users/tajokim/.hermes/skills/creative/pixel-art/references/asset-studio-local-walk4-contract.md`

## 6. 액션 QA 기준

공통 gate:

1. Identity Lock
2. Equipment Lock
3. Direction Lock
4. Root Lock
5. Motion Read
6. Loop Read
7. Production Clean

추가 주의:

- walk/idle GIF는 alpha bbox별 자동 recenter로 drift를 숨기지 않는다. fixed-cell 또는 명시적 root/pelvis/foot anchor로 조립한다.
- 약 20px 수준의 bbox center drift도 중형 sprite cell에서는 의심 대상으로 본다.
- attack은 weapon swing 때문에 full-alpha bbox 중심만으로 root를 판정하지 않는다. head/goggle, torso/pelvis, foot baseline을 따로 본다.
- attack4는 `ready → wind-up → strike → recover`가 보여야 하며 head/goggle lock과 no-baked-VFX가 필요하다.
- jump4는 `crouch → takeoff → airborne → landing`으로 읽혀야 한다. 수직 이동은 허용하되 수평 root drift는 별도 판정한다.
- postprocess/GIF 재조립만 했다면 새 그림을 생성했다고 말하지 않는다.

관련 reference:

- `~/.hermes/skills/creative/image-generation-operations/references/asset-studio-action-whitelist-qa.md`
- `~/.hermes/skills/creative/image-generation-operations/references/asset-studio-walk-gif-anchor-qa.md`
- `~/.hermes/skills/creative/image-generation-operations/references/asset-studio-walk4-root-registration-failure.md`
- `~/.hermes/skills/creative/image-generation-operations/references/asset-studio-attack-headlock-and-action-menu.md`
- `~/.hermes/skills/software-development/ai-image-editor-prototyping/references/asset-studio-walk-preview-anchor-pipeline.md`

## 7. 현재 검증 상태

2026-07-10 인수인계 직전 실행:

```bash
cd /Users/tajokim/asset-studio-local
PY=/Users/tajokim/.hermes/hermes-agent/venv/bin/python
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; fi
"$PY" -m pytest \
  tests/test_phase13_pixel_asset_generator_static.py \
  tests/test_effect_asset_type_and_no_vfx_static.py \
  tests/test_phase21_sprite_action_matrix.py \
  tests/test_phase25_action_preset_contract_static.py -q
node --check src/main.js
git diff --check
```

결과:

```text
19 passed in 0.06s
node --check: PASS
git diff --check: PASS
```

주의:

- 시스템 `/usr/bin/python3`에는 pytest가 없다. 프로젝트 `.venv`가 없으면 Hermes venv를 사용한다.
- 과거 `docs/history/milestones/PHASE_25_REPORT.md`에는 전체 suite `15 failed, 124 passed`가 기록돼 있다. 당시 실패는 오래된 정적 UI 토큰/레거시 기대값 불일치였으며 focused Phase 25 범위는 통과했다.
- 최신 전체 suite는 이번 인수인계에서 다시 실행하지 않았다.

## 8. 현재 Git 상태

브랜치/커밋:

```text
branch: main
HEAD: 9af254a Fix sprite grid after canvas resize
origin/main: a670d34 Fix sprite slice export source crop
```

즉 로컬 main은 origin/main보다 2커밋 앞서 있고, 그 위에 미커밋 변경이 쌓여 있다.

Tracked 변경:

```text
M index.html
M server.py
M src/main.js
M tests/test_phase13_pixel_asset_generator_static.py
M tests/test_phase21_sprite_action_matrix.py
```

주요 untracked:

```text
docs/history/artifacts/PHASE_25_ACTION_PRESET_GENERATION_RESULTS.json
docs/history/milestones/PHASE_25_REPORT.md
docs/
scripts/archive/generate_action_preset_matrix.py
scripts/visualqa_regen_actions.py
scripts/generate_*_once.py
tests/test_effect_asset_type_and_no_vfx_static.py
tests/test_phase25_action_preset_contract_static.py
tests/test_phase26_walk_anchor_and_gif_static.py
asset-studio-local/
```

특히 중첩된 아래 경로가 있다.

```text
/Users/tajokim/asset-studio-local/asset-studio-local/...
```

여기에는 walk4 실험 스크립트가 들어 있다. 실수로 생긴 중첩 디렉터리일 가능성이 있지만, 사용자 승인 없이 삭제하지 말고 내용/필요성을 먼저 확인한다.

## 9. 생성/실험 산출물 위치

대표 위치:

- 프로젝트 생성물: `/Users/tajokim/asset-studio-local/assets/generated/`
- 프로젝트 처리물: `/Users/tajokim/asset-studio-local/assets/processed/`
- Phase 25 결과 JSON: `/Users/tajokim/asset-studio-local/docs/history/artifacts/PHASE_25_ACTION_PRESET_GENERATION_RESULTS.json`
- Phase 25 contact sheet: `/Users/tajokim/asset-studio-local/assets/generated/phase25_action_presets/phase25_action_presets_contact_sheet.png`
- Hermes QA/전달 캐시: `/Users/tajokim/.hermes/image_cache/asset-studio-local/`
- Hermes media cache: `/Users/tajokim/.hermes/media_cache/asset-studio-local/`

과거 Phase 25 보고서의 “8/8 alpha/frame/cleanup pass”는 배관/cleanup 결과다. 이후 사용자 피드백으로 motion-read QA가 더 엄격해졌으므로 해당 8개를 현재 production PASS로 간주하면 안 된다.

## 10. 새 세션 권장 진행 순서

1. 서버 재기동 및 브라우저 콘솔 확인.
2. UI에서 기본 액션 메뉴에 `walk4`만 있고 `walk6`가 노출되지 않는지 확인.
3. 프롬프트 미리보기 또는 실제 API 요청으로 walk4가 정확히 `N → L → N → R` 계약을 사용하는지 확인.
4. 사용자가 다음 생성을 요청하면 **한 액션씩** 진행한다. 실제 사이트/API로 생성하고 투명 PNG, checker proof, fixed-cell GIF를 만든 뒤 7-lock 시각 QA를 한다.
5. clear PASS만 전달하고, 실패면 실패 lock만 짧게 보고한다.
6. 코드 정리가 필요하면 먼저 dirty/untracked 상태를 사용자에게 알리고 commit/stash/cleanup 범위를 승인받는다.

## 11. 새 세션 시작용 문구

아래처럼 요청하면 바로 이어가기 쉽다.

```text
/Users/tajokim/asset-studio-local/SESSION_HANDOFF_2026-07-10.md 읽고,
현재 git 상태와 서버/UI를 먼저 검증한 다음 Asset Studio walk4 작업을 이어가자.
walk4 기준은 N→L→N→R이고 실제 사이트/API 결과만 인정한다.
```

## 12. 이펙트 에셋 + 자동 조각 분리 통합 재검증

이 절은 2026-07-10에 다음 두 요청을 합쳐 재검증한 결과다.

1. 캐릭터와 크기·형태가 다른 이펙트에서도 자동 조각 분리가 안전한지 확인한다.
2. 외부 도구의 sprite-sheet/trim/pivot 처리 방식을 참고해 이펙트 가이드라인과 실제 구현 순서를 정리한다.

### 12.1 결론

현재 구현은 **이펙트 애니메이션 자동 분리 기준 FAIL**이다.

이펙트 전용 생성 payload와 서버 후처리 분기는 생겼지만, 프레임 수 계산, 자동 조각 감지, 미리보기, ZIP manifest에는 아직 캐릭터/고정-grid 중심 전제가 남아 있다. 특히 이펙트의 `보이는 픽셀 영역(visible bbox)`과 `애니메이션 프레임 캔버스(frame canvas/envelope)`를 구분하지 않는다.

중요한 원칙은 다음과 같다.

> 이펙트는 프레임마다 보이는 크기가 달라도 된다. 그러나 한 애니메이션 시퀀스 안에서는 공통 프레임 캔버스와 피벗을 유지해야 한다. 프레임을 trim한다면 원본 크기, trim 오프셋, 피벗을 metadata로 보존해야 한다.

서로 다른 이펙트 시퀀스끼리는 셀 크기가 달라도 된다. `베기 128×128`, `폭발 256×256`, `오라 192×256`처럼 **시퀀스별 envelope**를 가져야 하며, 모든 이펙트를 캐릭터의 `one actor cell`에 강제로 맞추면 안 된다.

### 12.2 현재 코드에서 확인된 충돌

파일 위치는 이 문서 작성 시점 기준이며 이후 편집으로 줄 번호가 바뀔 수 있다.

#### A. 이펙트 계약은 다중 프레임인데 기존 도트 워크플로는 1프레임으로 취급한다

- `src/main.js`의 `buildSpriteContract('effect')`는 `effectFrameCount`를 `frame_count`로 보낸다.
- 반면 `effectivePixelAnimationPreset()`은 actor가 아니면 `ui_static`을 반환한다.
- `requestedPixelFrameCount()`는 actor가 아니면 `1`을 반환한다.
- `syncPixelAssetWorkflowUi()`도 non-actor 경로에서 기존 프레임 값을 `1`로 바꾼다.
- `buildPixelAssetPrompt()`의 legacy effect 문구에는 `single asset`, `no sprite sheet`가 남아 있어 다중 프레임 effect contract와 충돌한다.
- `runPixelWorkflow()`는 생성 전후 `applyPixelWorkflowGridDefaults()`와 `buildGridSpriteSlices()`를 호출하므로 effect 전용 frame count가 아니라 actor/static grid 기본값으로 후단이 정리될 수 있다.

즉, 생성 요청에서는 6프레임을 요구하면서 후단 UI/분리에서는 1프레임으로 해석할 수 있다. effect frame count에는 단일 source of truth가 필요하다.

#### B. 연결 성분 탐지를 애니메이션 프레임 탐지로 사용할 수 없다

`extractImageDataComponents()`는 투명 배경에서 서로 연결된 픽셀 덩어리를 각각 하나의 조각으로 본다. 현재 기본 동작에는 다음 조건이 있다.

- alpha `<= 12`는 배경으로 취급
- 기본 최소 면적은 `48px`
- 상하좌우 4-neighbor로 연결된 픽셀을 하나의 component로 묶음

이 방식은 아이템 시트의 독립 오브젝트 탐지에는 쓸 수 있지만, 이펙트 시퀀스의 프레임 경계 탐지에는 부적합하다.

예:

- 폭발 본체와 떨어진 불티 5개 → 한 프레임이 6개 조각으로 오탐
- 연기 본체와 분리된 작은 입자 → 작은 입자가 최소 면적 미만으로 유실
- 낮은 alpha의 외곽 glow → alpha threshold 때문에 잘림
- 마법진의 끊어진 링/룬 → 한 프레임이 여러 component로 분리
- 여러 프레임을 가로지르는 잔여 배경 → 전체가 거대한 한 component가 됨

따라서 다음 규칙을 고정한다.

> `connected component count`를 `effect animation frame count`로 해석하지 않는다.

#### C. component 개수가 기대 프레임 수와 다르면 고정 grid로 fallback한다

`detectSpriteSlices()`는 탐지 개수가 설정된 grid count와 다르면 `buildGridSpriteSlices()`로 fallback한다. 이 자체는 최후 안전장치로 쓸 수 있지만 다음 전제가 필요하다.

- 생성 결과가 정확한 행/열 구조여야 함
- 프레임 간 gutter가 명확해야 함
- 셀 크기가 계약에 기록돼 있어야 함
- 어느 픽셀도 셀 경계를 넘어가면 안 됨

현재 effect는 후단에서 1프레임으로 취급될 수 있으므로 기대 grid count 자체가 틀릴 수 있다. 또한 모델이 가변 간격으로 프레임을 배치하면 단순히 `전체 폭 ÷ 프레임 수`로 자르는 것도 안전하지 않다.

#### D. 가변 bbox 미리보기에서 피벗이 흔들릴 수 있다

`buildAnimationFramesFromGrid()`는 각 slice의 `width × height`로 별도 캔버스를 만든다. component/bbox 기반으로 잘린 프레임을 그대로 재생하면 프레임마다 캔버스 원점과 크기가 달라진다.

그 결과:

- 폭발 중심이 좌우로 이동
- 연기 기둥이 순간 이동
- slash arc의 시작점이 흔들림
- 실제 게임 엔진에서 배치했을 때와 미리보기가 다름

미리보기는 trim 이미지 자체를 좌상단에 놓으면 안 된다. 공통 `sourceSize` 캔버스 위에 `trimOffset`과 `pivot`을 적용해 재합성해야 한다.

#### E. 현재 manifest만으로 trim 프레임을 복원하기 어렵다

현재 조각 ZIP manifest에는 주로 다음 값만 있다.

- `x`, `y`
- `width`, `height`
- `canvasX`, `canvasY`
- grid export의 `row`, `col`, `cellWidth`, `cellHeight`

가변 크기 이펙트 trim 복원에 필요한 다음 값이 없다.

- `sourceSize`: trim 전 공통 프레임 크기
- `spriteSourceSize` 또는 `trimRect`: 원래 셀 안에서 보이는 영역의 위치
- `trimOffset`
- 정규화된 `pivot`
- effect의 `anchorKind`/impact point
- playback mode, fps, duration

`canvasX/canvasY`는 편집기 Fabric 캔버스 좌표이므로 게임 엔진의 프레임 복원 좌표로 대신 쓰면 안 된다.

#### F. 서버 effect 후처리는 분리기가 아니다

`server.py`의 `postprocess_effect_generation_bytes()`는 effect 전용 alpha/chroma cleanup 분기다. actor direction-cell collapse를 우회하는 것은 맞지만, 다음 기능은 하지 않는다.

- effect frame boundary 판정
- frame count 검증
- per-frame trim/offset 계산
- pivot 보존
- sequence preview assembly

따라서 서버에 effect 분기가 있다는 이유만으로 자동 분리가 완료됐다고 판단하면 안 된다.

## 13. 외부 도구 조사에서 가져올 원칙

### 13.1 Aseprite

공식 sprite-sheet 문서는 import 시 다음 값을 명시적으로 받는다.

- offset `x`, `y`
- sprite `width`, `height`
- sprite 사이의 padding
- sheet type/order

이는 이미지의 연결된 픽셀을 보고 프레임을 추측하는 것이 아니라 **프레임 구조를 명시적으로 알고 자르는 방식**이다. Export에서도 layer와 tag별 frame을 선택한다.

적용 원칙:

- effect 생성 계약에서 frame count/layout/cell size/gap을 후단까지 보존한다.
- animation tag/sequence 순서를 manifest에 기록한다.
- image-only 추측보다 명시적 sheet contract를 우선한다.

공식 문서: <https://www.aseprite.org/docs/sprite-sheet/>

### 13.2 Unity Sprite Editor

Unity Sprite Editor는 큰 texture/sprite sheet를 별도 sprite로 slicing하는 기능과 sprite의 shape/size/pivot 편집을 분리해 제공한다. 자동 slicing과 pivot 조정은 같은 문제가 아니다.

적용 원칙:

- `어디서 자를지(frame rect)`와 `게임에서 어디에 고정할지(pivot)`를 별도 데이터로 관리한다.
- 자동 분리 후에도 사용자가 frame rect와 pivot을 검토·수정할 수 있어야 한다.
- 자동 탐지 결과를 무조건 확정하지 않고 preview/review 단계를 둔다.

공식 문서: <https://docs.unity3d.com/2023.2/Documentation/Manual/SpriteEditor.html>

### 13.3 Godot SpriteFrames

Godot의 sprite-sheet animation 흐름은 sheet의 horizontal/vertical image count를 지정하고 필요한 frame을 선택해 `SpriteFrames` animation에 추가한다.

적용 원칙:

- Godot export에서는 rows/columns/frame order가 명확해야 한다.
- 동일한 sequence는 공통 셀 크기를 유지하는 untrimmed export를 기본값으로 제공한다.
- trim export를 추가한다면 Godot 재조립용 offset/pivot metadata 또는 import helper가 필요하다.

공식 문서: <https://docs.godotengine.org/en/stable/tutorials/2d/2d_sprite_animation.html>

### 13.4 libGDX Texture Packer

공식 문서는 `stripWhitespaceX/Y`가 투명 여백을 제거하며, 애플리케이션이 제거된 영역을 올바르게 그리도록 특별히 처리해야 한다고 경고한다. `alphaThreshold` 아래 값은 trim 시 투명으로 처리된다. padding/bleed 설정도 별도로 존재한다.

적용 원칙:

- trim은 단순 crop이 아니라 원래 위치를 복원할 metadata와 한 묶음이다.
- glow/smoke 같은 낮은 alpha 이펙트에 actor/item용 고정 threshold를 그대로 사용하지 않는다.
- nearest filtering을 쓰더라도 atlas padding/edge bleed 문제를 별도로 검사한다.

공식 문서: <https://libgdx.com/wiki/tools/texture-packer>

## 14. 이펙트 에셋 제작 가이드라인

### 14.1 공통 계약

모든 effect sequence는 다음을 가져야 한다.

- effect category
- frame count
- layout: rows/columns/order
- playback: one-shot/loop/ping-pong
- fps 또는 per-frame duration
- sequence envelope width/height
- pivot/anchor
- padding/gutter
- background/alpha mode
- trim mode: untrimmed/trimmed

한 sequence 내부에서는 다음 값을 고정한다.

- canvas/envelope 크기
- pivot 좌표
- 기준 scale
- frame order

프레임마다 달라도 되는 값:

- visible bbox
- alpha 분포
- 파티클 수
- 밝기/발광 범위
- 실제로 차지하는 실루엣 크기

### 14.2 이펙트별 권장 피벗

| 유형 | 기본 피벗/anchor | 주의점 |
|---|---|---|
| Slash/Trail | source 또는 weapon attachment | arc bbox 중심으로 재정렬하지 않음 |
| Impact/Hit Spark | impact center | 프레임마다 폭발 크기가 변해도 중심 고정 |
| Explosion | center 또는 ground impact | 지면형이면 bottom-center/ground anchor 사용 |
| Smoke/Fire | bottom-center/source | 위로 퍼져도 발생 지점은 고정 |
| Aura | actor root/bottom-center | actor bbox가 아니라 actor root에 결합 |
| Magic Circle | center 또는 ground-center | 원근/회전 중에도 중심 고정 |
| Projectile | source + travel direction | 투사체와 impact sequence를 분리 가능 |
| Screen/Weather | screen/world anchor | actor cell 기준을 사용하지 않음 |

피벗 preset만 저장하지 말고 최종적으로 정규화 좌표도 저장한다.

```json
"pivot": { "preset": "bottom-center", "x": 0.5, "y": 1.0 }
```

### 14.3 크기 기준

`one actor cell` 하나만 제공하지 않는다. 최소한 다음 기준을 지원한다.

- explicit pixels: `width × height`
- tile multiple: `1×1`, `2×2`, `3×3` tiles
- actor relative: actor height/width 대비 비율
- world area/radius
- screen-space/full-screen

`actor relative`는 합성 preview용 기준일 뿐, 원본 effect frame canvas의 유일한 크기 규칙이 되어서는 안 된다.

### 14.4 생성 프롬프트의 셀 안전 규칙

다중 프레임 시퀀스를 한 이미지로 생성할 경우 다음을 명시한다.

- 정확한 rows/columns/frame count
- 모든 셀의 동일한 크기
- 공통 pivot 위치
- 셀 사이의 넓고 투명한 gutter
- glow/particle/debris도 자기 셀 안에 완전히 포함
- 인접 프레임으로 픽셀을 넘기지 않음
- caster/target/character/floor/UI/text/watermark 금지

다만 프롬프트 준수만 믿지 말고 후단에서 셀 경계 침범과 gutter alpha를 검사한다.

## 15. 자동 조각 분리 모드 설계

자동 분리는 하나의 버튼/알고리즘으로 통합하지 말고 목적에 따라 분기한다.

### Mode A — Effect Sequence Grid: 기본 권장

대상: 하나의 애니메이션 이펙트 시퀀스.

1. payload의 `frame_count`, `rows`, `columns`, `cell_size`, `gap`을 읽는다.
2. 전체 sheet와 계약이 나누어떨어지는지 검사한다.
3. 각 셀의 **전체 투명 여백을 포함해** 동일 크기로 자른다.
4. 셀 내부 alpha bbox는 QA용으로만 계산하고 프레임 원점을 바꾸지 않는다.
5. 공통 피벗으로 미리보기한다.
6. 기본 export는 untrimmed same-size frames다.

연결 성분 탐지를 frame boundary 결정에 사용하지 않는다.

### Mode B — Trimmed Effect Sequence: 선택 최적화

대상: atlas 용량 최적화가 필요한 동일 시퀀스.

1. Mode A로 먼저 정확한 셀을 확정한다.
2. 각 셀 내부에서만 alpha bbox를 계산한다.
3. bbox에 안전 padding을 추가한다.
4. PNG는 trim하되 `sourceSize`, `trimRect`, `pivot`을 manifest에 기록한다.
5. 미리보기에서는 공통 source canvas에 offset대로 재합성한다.
6. untrimmed 결과와 비교해 픽셀 위치가 동일한지 round-trip 검증한다.

권장 schema:

```json
{
  "kind": "effect_sequence",
  "name": "impact_fire_01",
  "frameCount": 6,
  "layout": { "rows": 1, "columns": 6, "gapX": 8, "gapY": 0 },
  "sourceSize": { "w": 192, "h": 192 },
  "pivot": { "preset": "center", "x": 0.5, "y": 0.5 },
  "playback": { "mode": "one-shot", "fps": 12 },
  "frames": [
    {
      "file": "impact_fire_01_000.png",
      "index": 0,
      "durationMs": 83,
      "trimmed": true,
      "trimRect": { "x": 71, "y": 73, "w": 42, "h": 39 }
    }
  ]
}
```

### Mode C — Loose Asset Components

대상: 서로 독립된 정적 아이템/아이콘/이펙트 여러 개가 놓인 sheet.

- 기존 connected-component 탐지를 사용할 수 있다.
- 이 모드는 animation frame detector가 아님을 UI에 명시한다.
- 떨어진 파티클을 하나의 에셋으로 묶을 수 있도록 component 병합/그룹 선택이 필요하다.
- 최소 면적과 alpha threshold를 effect용으로 조절할 수 있어야 한다.

### Mode D — Metadata Atlas Import

대상: Aseprite/TexturePacker 등에서 나온 atlas.

- sidecar JSON/atlas metadata가 있으면 이미지 추측보다 우선한다.
- frame rect, source size, offset, pivot, duration, frame order를 그대로 가져온다.
- metadata와 PNG 크기가 불일치하면 자동 진행하지 않고 FAIL 처리한다.

## 16. 구현 작업 방법과 순서

아래 순서는 Phase 2 리뷰/보정 범위에서 먼저 처리하고, 결과 tray/project save/export 단계와 결합한다.

### Step 0 — 기존 상태 보호

- `git status --short`, `git diff --stat`, 관련 diff를 먼저 기록한다.
- 현재 dirty/untracked 파일을 임의로 reset/clean/stash/삭제하지 않는다.
- 문서 작업과 실제 코드 변경 범위를 분리한다.

### Step 1 — effect contract를 단일 source of truth로 만든다

- `effectFrameCount`가 생성 prompt, payload, grid, preview, export 전체에 동일하게 전달되게 한다.
- effect에서 `ui_static`, `1 frame`, `single asset`, `no sprite sheet`로 떨어지는 legacy 경로를 제거하거나 명시적으로 분리한다.
- actor의 animation preset/frame count helper를 effect가 공유하지 않게 한다.
- effect sequence와 static effect를 별도 mode로 구분한다.

### Step 2 — effect 전용 frame envelope/pivot 설정을 추가한다

- width/height 또는 size-reference를 실제 셀 크기로 resolve한다.
- tile/actor/world/screen 기준을 분리한다.
- pivot preset + normalized x/y를 payload에 포함한다.
- rows/columns/gap/padding/playback/fps를 계약에 포함한다.

### Step 3 — slicer를 목적별 전략으로 분기한다

- actor grid
- effect sequence grid
- trimmed effect sequence
- loose component assets
- metadata atlas import

함수 이름과 manifest의 `kind/mode`도 구분해, `spriteSlices` 하나의 전역 배열에 의미가 섞이지 않게 한다.

### Step 4 — effect sequence validator를 구현한다

최소 검사:

- 실제 프레임 수 = 요청 프레임 수
- sheet 크기와 rows/columns/cell/gap 계약 일치
- 각 셀이 비어 있지 않음
- 셀 경계/외곽 안전 padding 침범 없음
- gutter alpha가 허용치 이하
- 낮은 alpha glow가 threshold 때문에 유실되지 않음
- 공통 pivot 기준 visible bbox drift 측정
- loop일 경우 첫/마지막 전환 pop 검사

검사 결과는 단순 boolean이 아니라 reason과 metrics를 남긴다.

### Step 5 — 공통 캔버스 미리보기를 구현한다

- untrimmed frame은 그대로 재생한다.
- trimmed frame은 sourceSize 캔버스에 trimRect 위치로 복원한다.
- CSS의 자동 중앙 정렬로 drift를 숨기지 않는다.
- pivot/root overlay를 표시해 프레임별 흔들림을 눈으로 확인할 수 있게 한다.
- effect-only preview와 actor 합성 preview를 분리한다.

### Step 6 — export/manifest를 확장한다

필수 필드:

- asset/effect kind
- frame count/order
- playback/fps/duration
- common source size
- frame rect 또는 trim rect
- pivot/anchor
- rows/columns/gap/padding
- alpha/trim mode

기본 제공:

1. 동일 크기 untrimmed PNG sequence
2. sprite sheet + manifest
3. 선택적으로 trimmed PNG + 복원 metadata
4. Godot 등 대상 엔진용 import 정보

### Step 7 — 테스트를 먼저 추가하고 브라우저에서 검증한다

필수 synthetic fixture:

1. 프레임마다 visible bbox 크기가 다른 6프레임 폭발
2. 본체와 떨어진 불티가 있는 impact
3. alpha 1~20의 희미한 외곽 glow
4. bottom-center 피벗의 세로 연기
5. 빈 프레임이 포함된 one-shot
6. 셀 경계를 1px 침범한 실패 sheet
7. 가변 trimRect지만 sourceSize/pivot이 같은 sequence
8. loose component sheet와 animation sheet가 시각적으로 비슷한 경우

필수 자동 검증:

- exact frame count
- no particle-as-frame split
- no clipped alpha/glow
- manifest round-trip
- untrimmed와 trimmed 복원 결과의 픽셀 위치 일치
- preview common canvas 유지
- syntax/static/API tests

필수 브라우저 검증:

- effect 선택 시 actor 방향/장비 controls가 숨겨지는지
- 설정한 frame count가 생성 후에도 유지되는지
- 자동 분리 mode가 effect sequence로 표시되는지
- frame guide가 올바른 셀에 놓이는지
- 공통 pivot preview가 흔들리지 않는지
- ZIP/manifest를 다시 읽어 동일하게 복원되는지
- 콘솔 error가 없는지

### Step 8 — PASS 판정

다음이 모두 확인돼야 effect auto-slicing을 PASS라고 말한다.

1. 다중 프레임 contract가 생성부터 export까지 보존됨
2. visible bbox가 달라도 공통 pivot에서 안정적으로 재생됨
3. 분리 파티클이 별도 프레임으로 오탐되지 않음
4. 작은 입자와 낮은 alpha glow가 보존됨
5. trim 결과를 manifest로 원위치 복원 가능
6. untrimmed/trimmed round-trip 비교 통과
7. 실제 브라우저 UI/API 파이프라인에서 재현됨
8. 관련 테스트와 콘솔 검증 통과

배관 지표만 통과하거나 프롬프트에 frame count가 들어간 것만으로는 PASS가 아니다.

## 17. Phase 계획에 반영할 범위

이 문제는 별도 후순위 polish가 아니라 **Phase 2 분류별 계약/조건부 설정/정규화의 필수 보정 항목**이다.

Phase 2 리뷰에서 최소한 다음을 끝낸 뒤 Phase 3 결과 tray로 넘어간다.

- effect frame count 단일화
- effect sequence/static 분리
- effect 전용 envelope/pivot/layout 계약
- 자동 분리 mode 분기
- 공통 캔버스 preview
- sourceSize/trimRect/pivot manifest
- synthetic effect fixture 테스트
- 실제 브라우저 검증

Phase 5 family별 QA/export에서는 이 계약을 사용해 effect 전용 QA provider와 엔진 export를 완성한다.

이 절 작성 시점에는 분석과 문서화만 수행했으며, 위 코드 변경은 아직 실행하지 않았다.

## 18. 전체 에셋 패밀리 구조 통합 분석

이 절은 이펙트 재검증보다 앞서 수행한 **스프라이트·타일/맵·UI·오브젝트 전체 설계 분석**을 통합한 것이다. Sections 12~17의 이펙트 분석은 이 전체 구조에서 `sprite/effect`가 가져야 할 세부 계약이다.

### 18.1 현재 설계에서 근본적으로 잘못된 부분

현재 구조는 사실상 다음과 같다.

```text
스프라이트:
생성할 내용 + 스타일 + 레퍼런스 + 방향 + 액션 + 프레임 + 제작 흐름 전체

타일/UI/오브젝트:
하위 종류 + 몇 가지 설정 + 생성 버튼
```

이것은 완전한 분류별 제작 시스템이 아니라 **스프라이트 생성기에 세 개의 껍데기 탭을 추가한 상태**다.

탭, subtype 목록, 조건부 controls, 분리된 payload가 존재하는 것만으로 해당 패밀리가 구현됐다고 판단하면 안 된다. 패밀리별로 아래 전체 제작 루프가 보여야 한다.

```text
패밀리별 생성 요청
→ 공통 프로젝트 스타일/레퍼런스
→ 패밀리 전용 제작 설정
→ 모든 설정을 소비하는 provider prompt
→ 패밀리 전용 후처리
→ 패밀리 전용 결과 preview
→ 패밀리 전용 QA
→ 엔진에서 바로 쓸 수 있는 export + metadata
```

이 중 하나라도 빠지면 `완료`가 아니라 `PARTIAL / facade`로 기록한다.

### 18.2 분류별 반드시 있어야 하는 핵심

| 분류 | 반드시 있어야 하는 제작 계약 | 반드시 있어야 하는 검증/사용 흐름 |
|---|---|---|
| Sprite Actor | 정체성, reference/target 방향, action, frame count/FPS, cell, root/foot/pivot, 장비·팔레트 lock | fixed-cell 재생, 방향·액션 비교, root/pivot overlay, motion-read QA, sheet/frame export |
| Sprite Effect | category, sequence/static, frame count, loop, FPS, sequence envelope, pivot/anchor, size basis | 공통 캔버스 재생, detached particle/glow 보존, actor 합성 preview, trim 복원 QA |
| Tile/Map | 환경·재질·용도, tile size/shape, atlas margin/spacing, terrain topology, edge/corner transition, variants, collision/navigation | 3×3 반복, random repeat, terrain brush paint, rule coverage, collision/navigation overlay, atlas/rule export |
| UI | component 목적, 실제 source size, 9-slice, slice margins, safe area, padding, states, stretch/tile mode | 1:1 preview, resize 3종 비교, guide, 임시 콘텐츠 조립, state 비교, text-free component export |
| World Object | world/icon 용도, view, world scale, source canvas, pivot, ground/Y-sort, shadow, states, collision, interaction | tile grid/character scale placement, pivot·ground·collision overlay, state/variant scene, map placement, metadata export |

핵심 차이는 “무엇을 생성하느냐”뿐 아니라 **게임에서 어떻게 배치·반복·리사이즈·애니메이션·상호작용하는가**다.

## 19. 공통 정보 구조와 Anti-Facade Gate

### 19.1 공통 셸

네 패밀리는 같은 AI 생성 패널을 사용할 수 있지만, form contract는 분리한다.

```text
family
→ subtype
→ 생성할 내용(core request)
→ 프로젝트 스타일/레퍼런스
→ family-only settings
→ output/background
→ Generate
→ result preview/tray
→ family QA
→ family export
```

공통으로 지켜야 할 조건:

- 모든 패밀리에 필수 `생성할 내용`이 보인다.
- 하나의 공통 입력을 쓰더라도 family별 label/placeholder/help가 바뀐다.
- 탭을 바꿀 때 family별 입력 초안을 보존한다.
- 타일/UI/오브젝트가 숨겨진 sprite subject를 참조하거나 빈 값 때문에 `character`로 fallback하지 않는다.
- 프로젝트 스타일, palette, reference policy, output/background는 모든 패밀리에서 보이고 실제 prompt에 반영된다.
- primary Generate 버튼은 입력과 설정 뒤에 놓인다.
- 탭 전환이 canvas/layers/history/adopted result를 초기화하지 않는다.

패밀리별 core request 예:

- Sprite: 캐릭터/이펙트 정체성, 동작, 방향, 프레임 의도
- Tile: 환경, 재질, terrain 관계, 실제 map 용도
- UI: component 기능, 담을 정보, visual concept
- Object: 형태, 재질, world 기능, 상호작용/상태

### 19.2 완료 판정

다음 질문에 모두 `예`라고 답해야 패밀리가 구현된 것이다.

1. 사용자가 해당 패밀리에서 무엇을 만들지 직접 입력할 수 있는가?
2. 보이는 모든 설정이 payload뿐 아니라 provider prompt까지 도달하는가?
3. 다른 패밀리의 actor/idle/direction 설정이 섞이지 않는가?
4. 결과를 그 패밀리의 실제 사용 방식으로 preview할 수 있는가?
5. 패밀리 전용 QA가 있는가?
6. 게임 엔진에서 재사용 가능한 PNG/atlas/metadata를 export하는가?
7. 실제 브라우저 UI에서 생성 전 단계와 비유료 payload debug가 검증됐는가?

정적 payload 테스트만 통과하고 visible production loop가 없으면 FAIL이다.

## 20. 패밀리별 실제 제작·사용 흐름

### 20.1 Sprite Actor

#### 입력

- character/monster/NPC subtype
- subject와 reference image
- reference direction과 target direction
- single/4/8-direction mode
- action과 frame count/FPS
- cell width/height, rows/columns, spacing
- pivot/root/foot contact
- identity/equipment/palette/silhouette lock

#### Preview/QA

- fixed-cell sheet preview
- animation playback
- frame strip 비교
- pivot/root/foot baseline overlay
- 방향 비교
- 실제 게임 배율 preview
- motion-read와 7-lock QA

alpha/frame count/bbox 지표만으로 PASS하지 않는다. 걷기·공격·점프 등이 실제로 해당 동작으로 읽혀야 한다.

#### Export

- sheet PNG
- frame PNG ZIP
- frame order/tags
- cell geometry와 spacing
- FPS/duration
- pivot/root metadata

### 20.2 Sprite Effect

Effect는 animated sprite일 수 있지만 actor가 아니다.

#### 입력

- Slash/Impact/Explosion/Smoke/Particle/Aura 등 category
- static/sequence
- one-shot/loop/ping-pong
- frame count와 FPS/duration
- sequence envelope
- pivot/anchor
- pixels/tile/actor-relative/world/screen size basis
- composite reference

actor direction, gait, body, equipment controls는 제외한다. reference actor가 있더라도 scale/palette/composite context로만 사용하며 source actor를 복사하거나 변형하지 않는다.

#### Preview/QA/Export

Sections 12~17의 effect sequence grid, trim metadata, common-canvas preview, detached-particle/glow QA를 따른다.

### 20.3 Tile/Map

타일은 한 장의 반복 가능한 이미지가 아니라 **terrain 규칙과 map painting을 위한 데이터 단위**다.

#### 입력

- 환경, 재질, map 용도
- tile size와 tile shape
- atlas margin/spacing
- single/tile-set/autotile
- rows/columns
- seamless/repeat
- edge/inner corner/outer corner
- terrain type와 transition
- variants와 출현 빈도
- collision/occlusion/navigation
- tile custom metadata

`tile size + seamless`만으로 terrain 제작을 끝내면 안 된다. Tiled terrain set은 corner matching, edge matching, corner+edge matching을 구분한다. 두 terrain의 완전한 전이 집합은 방식에 따라 16개부터 최대 256개 조합이 필요할 수 있고, blob 방식에서는 축약된 47-tile 계열을 사용하기도 한다. 제품은 선택한 topology에서 필요한 rule coverage를 계산·표시해야 한다.

#### Preview/QA

- 3×3 repeat preview
- 더 넓은 random repeat
- seam 확대 검사
- inner/outer corner 연결
- terrain brush painting simulation
- transition/rule coverage
- variant 분포와 반복 티 검사
- collision/occlusion/navigation overlay

#### Export

- atlas PNG
- individual tile ZIP
- tile index와 atlas coordinates
- margin/spacing
- terrain rule/transition data
- variant/frequency
- collision/navigation/custom properties
- 가능하면 Godot/TSX 친화 metadata

Godot TileSet은 tile 이미지뿐 아니라 collision, occlusion, navigation, terrain, alternative tile 데이터를 함께 사용하고 TileMap layer에서 paint된다. 그러므로 “예쁜 tileset PNG 생성”만으로는 제작 흐름이 끝나지 않는다.

### 20.4 UI Component

UI는 완성 화면 mockup이 아니라 게임에서 조립·리사이즈할 **재사용 component pack**이어야 한다.

#### 입력

- panel/button/slot/gauge/icon/cursor 등 component 종류
- component 목적과 정보 구조
- 실제 source width/height
- fixed/9-slice
- left/top/right/bottom slice margins
- content safe area와 internal padding
- border/corner/decor density
- center/edge stretch 또는 tile mode
- opacity
- target resolution/device safe area
- state set: normal/hover/pressed/disabled/selected/focused
- text-free source 기본값

UI 소스에 가짜 글자, 숫자, 완성 문구를 굽지 않는다. 실제 텍스트와 수치는 엔진의 font/layout으로 조립한다.

#### Preview/QA

- 원본 1:1 pixel preview
- 9-slice guide
- content safe-area guide
- small/medium/large resize 비교
- 임시 텍스트·아이콘·게이지 콘텐츠 조립
- state 비교
- HUD/full-screen context
- pixel UI integer-scale preview
- corner가 늘어나지 않고 edge/center가 의도대로 stretch/tile되는지 검사

#### Export

- text-free transparent PNG
- state별 PNG/ZIP
- source size
- 9-slice margins
- safe area/padding
- edge/center stretch/tile modes
- actual-size icon/cursor

Unity/Godot의 9-slice/NinePatch는 corner를 보존하고 edge와 center만 stretch/tile한다. tiled center/edge는 seamless해야 한다.

### 20.5 World Object

Object는 UI icon과 구분한다. 동일 물체라도 `world sprite`와 `inventory icon`은 별도 derivative다.

#### 입력

- world/icon 사용 목적
- item/equipment/weapon/furniture/machine/prop/interactable/destructible subtype
- 형태, 재질, 기능
- front/side/3-quarter/top-down view
- tile/character-relative world scale
- source canvas와 transparent padding
- pivot
- ground contact/Y-sort point
- shadow included/separate/none
- normal/open/closed/used/active/broken/destroyed states
- variants
- collision shape
- interaction point
- placement/snap rules
- custom properties

#### Preview/QA

- transparent original
- tile grid placement
- character와 scale 비교
- pivot/ground/Y-sort overlay
- collision overlay
- interaction point
- states/variants를 한 scene에 배치
- shadow included와 separate 비교
- world sprite와 icon derivative 비교

#### Export

- transparent world PNG
- state/variant ZIP 또는 atlas
- pivot와 ground point
- collision shape
- interaction point
- world scale/tile footprint
- custom properties
- 별도 icon derivative
- 가능하면 별도 shadow layer

Unity는 sprite pivot을 transform 기준으로 사용하고 custom pivot을 지원한다. Godot Sprite2D는 centered/offset을 제공하며 pixel alignment에 주의해야 한다. Tiled object는 alignment, collision shape, template, object link, typed custom property를 사용한다. 따라서 PNG만 내보내고 placement/interaction metadata가 없으면 완성된 world-object workflow가 아니다.

## 21. Payload·Prompt·후처리 격리

### 21.1 권장 payload

한 요청에는 정확히 하나의 family contract만 포함한다.

```json
{
  "asset_family": "ui",
  "asset_type": "button",
  "prompt": "어두운 판타지 게임의 확인 버튼",
  "style": {
    "preset": "32bit_refined",
    "notes": "black plate, muted brass"
  },
  "output": {
    "width": 160,
    "height": 48,
    "background": "transparent"
  },
  "ui": {
    "nine_slice": true,
    "slice_margins": {"left": 12, "top": 12, "right": 12, "bottom": 12},
    "states": ["normal", "hover", "pressed", "disabled"]
  }
}
```

규칙:

- browser builder는 선택한 family nested key 하나만 추가한다.
- 서버는 `dict(data)` 전체를 신뢰하지 말고 allow-list로 새 normalized object를 만든다.
- enum, 숫자 범위, text length를 검증한다.
- `0 opacity`, `0 padding`, `0 density` 같은 정상적인 0을 `value || fallback`으로 덮지 않는다.
- 보이는 모든 control이 prompt 또는 postprocess/export 계약에 실제로 사용돼야 한다.
- 수집만 하고 provider prompt에서 버리는 field는 dead UI다.
- legacy flat payload는 actor 호환 등 좁은 branch에서만 허용한다.
- hidden subtype가 비어서 `character`로 fallback하는 경로를 차단한다.

### 21.2 Prompt 격리

- Actor prompt: identity/action/direction/frame/root/production locks
- Effect prompt: sequence/category/pivot/envelope/compositing, no actor body
- Tile prompt: terrain/material/topology/transition/variant, no actor/action/UI
- UI prompt: component function/size/9-slice/safe area/state, no scene mockup/text
- Object prompt: world use/view/scale/pivot/state/material, no UI card/mockup

패밀리별 visible setting이 prompt에 반영되지 않으면 해당 설정은 구현된 것이 아니다.

### 21.3 Postprocess 격리

- actor sprite만 actor chroma/direction/action cleanup 사용
- effect는 effect sequence/alpha-safe path 사용
- tile은 edge/seam/atlas 보존 path 사용
- UI는 원본 size·corner·alpha를 보존하고 sprite trim/candidate cleanup 우회
- object는 alpha padding/pivot/shadow/state를 보존하고 actor cell collapse 우회

타일/UI/오브젝트가 actor cleanup을 거치거나 effect가 `ui_static`으로 normalize되면 FAIL이다.

## 22. 전체 Phase 2 구현 작업 방법

이 순서는 Sections 12~17의 effect 보정과 함께 수행한다.

### Step 1 — 현재 facade 범위 고정

- family별 visible inputs, payload, prompt, server branch, preview, QA, export를 표로 추적한다.
- 각 항목을 `DONE / PARTIAL / MISSING / CONTRADICTORY`로 기록한다.
- 기존 dirty tree를 보호하고 임의 reset/clean/stash를 하지 않는다.

### Step 2 — 공통 생성 셸 완성

- family/subtype/core request/shared style/output/Generate 순서를 정리한다.
- family별 core request label/placeholder/help와 draft 보존을 구현한다.
- tabs를 실제 ARIA tabs로 구현한다.
- `aria-controls`, matching tabpanel, roving `tabindex`, ArrowLeft/Right/Home/End를 검증한다.
- 실제 클릭한 Generate 버튼과 하나의 in-flight Promise를 묶어 중복 유료 요청을 차단한다.

### Step 3 — family contract와 정규화 완성

- sprite actor/effect, tile, UI, object schema를 분리한다.
- visible controls를 모두 nested payload에 연결한다.
- 서버 allow-list normalization과 bounds/enum validation을 추가한다.
- legacy actor compatibility가 다른 family로 새지 않게 한다.
- 대표 payload를 비용 없이 볼 수 있는 debug builder를 둔다.

### Step 4 — family prompt와 postprocess 연결

- 대표 subtype별 prompt snapshot/static test를 먼저 작성한다.
- 모든 visible setting이 prompt에 소비되는지 검사한다.
- actor/effect/tile/UI/object postprocess branch를 분리한다.
- tile/UI/object 요청에 character/idle/direction 문구가 없는지 검사한다.

### Step 5 — family preview와 QA 구현

- Sprite: animation/direction/root preview
- Effect: common envelope/pivot/composite preview
- Tile: repeat/paint/topology/collision preview
- UI: 9-slice/safe area/resize/state/assembly preview
- Object: map placement/scale/pivot/ground/collision/state preview

각 preview가 단순 이미지 썸네일이면 부족하다. 실제 사용 중 발생하는 실패를 보여줘야 한다.

### Step 6 — engine-usable export 구현

- Sprite: sheet/frames/order/FPS/pivot
- Effect: full-cell 또는 trim+sourceSize/offset/pivot
- Tile: atlas/index/rules/collision/navigation
- UI: states/9-slice/safe area/stretch mode
- Object: states/pivot/ground/collision/interaction/world scale

family별 manifest에 `schema_version`, coordinate convention, source size를 넣는다.

### Step 7 — 테스트와 실제 브라우저 검증

정적 테스트:

- family/subtype 목록
- required controls
- builder/normalizer
- payload isolation
- backward compatibility
- prompt completeness
- postprocess gating
- export manifest schema

실제 브라우저 smoke:

1. AI 생성 도구를 실제로 연다.
2. 네 family를 모두 전환한다.
3. 정확히 하나의 settings panel만 보이는지 확인한다.
4. family별 `생성할 내용`, style, output, Generate가 모두 보이는지 확인한다.
5. sprite actor/effect/tile/UI/object 대표 payload를 debug builder로 확인한다.
6. effect에 actor direction/equipment가 없는지 확인한다.
7. tile/UI/object에 actor/idle fallback이 없는지 확인한다.
8. keyboard tab navigation을 확인한다.
9. console error가 0인지 확인한다.
10. 유료 생성을 생략했다면 생략 사실을 명확히 기록한다.

주의: DOM이 보인다는 것만으로 app이 정상이라는 뜻이 아니다. 초기화 순서에서 아직 선언되지 않은 `let/const`를 참조하면 event wiring이 중단돼도 정적인 UI는 표시될 수 있다. 최종 app initialization은 모든 선언과 listener 뒤에서 실행하고 실제 클릭으로 검증한다.

### Step 8 — Phase Gate

Phase 2 완료 조건:

- 공통 생성 셸이 네 family에서 실제로 사용 가능
- 패밀리별 payload/prompt/postprocess 격리
- 패밀리별 preview/QA/export 계약이 최소 한 개의 실제 slice로 동작
- effect sequence 자동 분리 보정 완료
- focused/full tests 결과 기록
- 실제 브라우저 console 0건
- 외부 또는 검증 가능한 실제 URL에서 authoring path 확인

그 전에는 Phase 2를 “탭/설정/payload 구현 완료”라고 보고하지 않는다. Phase 3 결과 tray는 이 패밀리 결과 계약을 받아야 하므로 Phase 2/Phase 2-review에서 facade를 먼저 제거한다.

## 23. 전체 구조 공식 참고 자료

- Aseprite sprite-sheet import/export: <https://www.aseprite.org/docs/sprite-sheet/>
- Godot 2D sprite animation: <https://docs.godotengine.org/en/stable/tutorials/2d/2d_sprite_animation.html>
- Godot TileSets: <https://docs.godotengine.org/en/stable/tutorials/2d/using_tilesets.html>
- Godot TileMaps: <https://docs.godotengine.org/en/stable/tutorials/2d/using_tilemaps.html>
- Tiled Terrain: <https://doc.mapeditor.org/en/stable/manual/terrain/>
- Tiled Editing Tilesets: <https://doc.mapeditor.org/en/stable/manual/editing-tilesets/>
- Unity 9-slicing: <https://docs.unity3d.com/Manual/9SliceSprites.html>
- Godot NinePatchRect: <https://docs.godotengine.org/en/stable/classes/class_ninepatchrect.html>
- Godot UI size and anchors: <https://docs.godotengine.org/en/stable/tutorials/ui/size_and_anchors.html>
- Godot GUI containers: <https://docs.godotengine.org/en/stable/tutorials/ui/gui_containers.html>
- Unity Sprite Editor/pivot: <https://docs.unity3d.com/Manual/sprite/sprite-editor/sprite-editor-window-reference.html>
- Godot Sprite2D: <https://docs.godotengine.org/en/stable/classes/class_sprite2d.html>
- Tiled Working with Objects: <https://doc.mapeditor.org/en/stable/manual/objects/>
- Tiled Custom Properties: <https://doc.mapeditor.org/en/stable/manual/custom-properties/>

Sections 18~23과 Sections 12~17을 함께 읽어야 전체 Phase 2 설계가 된다. 전자는 네 패밀리 전체 제작 구조이고, 후자는 그중 effect sequence와 자동 조각 분리의 세부 규격이다.
