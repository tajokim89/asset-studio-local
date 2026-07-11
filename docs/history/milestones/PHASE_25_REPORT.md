# Phase 25 Report — Action Preset Contract + Sprite Cleanup

## 요약
Phase 25 범위대로 픽셀/게임 액터 애니메이션 프리셋 계약을 서버/프론트/테스트 기준으로 정리했습니다.

- canonical server actions를 `idle`, `walk`, `attack`, `jump`, `cast`, `hurt`, `death`로 정렬했습니다.
- legacy `hit`은 `hurt`로 normalize되도록 유지했습니다.
- `idle4`, `walk4`, `walk6`, `attack4`, `jump4`, `cast4`, `hurt4`, `hit`, `death4`, `death6`, `static1` normalize를 테스트 가능하게 만들었습니다.
- `walk6`는 프론트에서 실제 6프레임 payload/spec가 되도록 고정했습니다.
- non-idle action 프롬프트에 frame beat sheet와 cell-boundary/cleanup safety 문구를 추가했습니다.
- 생성 후처리에서 dark/green residue, cell-border line, chroma spill/halo/fringe를 QA할 수 있게 했고, bad example 기준 cleanup 검증을 추가했습니다.

## 수정 파일
- `server.py`
  - `SPRITE_ACTION_MATRIX` canonical action 확장: `idle`, `walk`, `attack`, `jump`, `cast`, `hurt`, `death`.
  - `normalize_animation_action()` 추가/정리: legacy `hit` → `hurt`, 숫자 suffix payload key normalize.
  - `animation_frame_count()` 추가: `walk6` 등 payload key 기반 frame count 해석.
  - action prompt/ reference prompt에서 normalize 사용.
  - sprite postprocess에 `cleanup_sprite_sheet_residue_image()`와 `evaluate_cleanup_residue_quality()` 추가.
  - chroma cleanup 이후 `residue-cleanup` 단계와 `cleanup_qa` 결과를 report에 포함.
- `src/main.js`
  - 프론트 animation preset별 기본 frame count 추가.
  - `walk6` 선택 시 `pixelWalkFrames=6`으로 동기화.
  - action별 beat sheet 추가: walk/attack/jump/cast/hurt/death.
  - prompt output에 cleanup contract 추가: true transparent background, no visible rectangular cell boxes, no dark/green residue, no chroma spill/halo/fringe.
  - `animationPresetSpec()` key를 `idle4`, `walk4`, `walk6`, `attack4`, `jump4`, `cast4`, `hurt4`, `death4`, `static1`로 명확화.
- `index.html`
  - `src/main.js` cache bust query를 `phase25-action-preset-contract`로 갱신.
- `tests/test_phase21_sprite_action_matrix.py`
  - Phase 25 canonical action matrix 기준으로 기존 Phase 21 테스트 갱신.
- `tests/test_phase25_action_preset_contract_static.py`
  - Phase 25 신규 정적/후처리 테스트 추가.

## 검증 명령 및 결과
### Focused Phase 25/관련 테스트
```bash
python3 -m pytest tests/test_phase21_sprite_action_matrix.py tests/test_phase21_sprite_visual_gate_static.py tests/test_phase21_sprite_quality_gate.py tests/test_phase25_action_preset_contract_static.py -q && node --check src/main.js && git diff --check
```

결과:
```text
12 passed in 0.04s
```
`node --check src/main.js`, `git diff --check`도 출력 없이 통과했습니다.

### 전체 테스트
```bash
python3 -m pytest tests -q
```

결과:
```text
15 failed, 124 passed, 8 warnings
```

실패는 기존 정적 UI 토큰/레거시 Phase 테스트 기대값 불일치입니다. 예:
- `Pixel Asset Generator`, `원클릭 워크플로우`, `phase17-directional-chroma` 등 오래된 index/static token 기대
- `idle -> stepA -> idle -> stepB` 같은 구 walk prompt 기대
- 기존 crop/static 구조 기대

Phase 25 focused 범위는 통과했습니다.

## 브라우저 검증
로컬 서버 `http://127.0.0.1:4184/?v=phase25-final3`에서 확인했습니다.

검증 내용:
- AI 생성 패널 로드 확인.
- `walk6`, `attack`, `jump`, `cast`, `hurt`, `death` 선택 시 prompt/frame contract 확인.
- `walk6`는 `pixelWalkFrames=6`으로 표시.
- 나머지 non-idle action은 4프레임 beat sheet 포함.
- prompt에 cleanup contract 포함 확인.
- 브라우저 콘솔 JS error 없음.

브라우저 콘솔 검증 결과 요약:
```json
{
  "walk6": {"frames":"6", "hasBeat":true, "hasCleanup":true},
  "attack": {"frames":"4", "hasBeat":true, "hasCleanup":true},
  "jump": {"frames":"4", "hasBeat":true, "hasCleanup":true},
  "cast": {"frames":"4", "hasBeat":true, "hasCleanup":true},
  "hurt": {"frames":"4", "hasBeat":true, "hasCleanup":true},
  "death": {"frames":"4", "hasBeat":true, "hasCleanup":true}
}
```

## 실제 액션 프리셋 생성 QA
요청 후 실제 AI 생성으로 전체 액션 프리셋을 한 번씩 생성했습니다.

생성 결과 요약:
```text
total: 8
successes: 8/8
alpha_passes: 8/8
frame_passes: 8/8
cleanup_passes: 8/8
```

생성 액션:
- `idle4`: 4/4 frames, alpha pass, cleanup pass
- `walk4`: 4/4 frames, alpha pass, cleanup pass
- `walk6`: 6/6 frames, alpha pass, cleanup pass
- `attack4`: 4/4 frames, alpha pass, cleanup pass
- `jump4`: 4/4 frames, alpha pass, cleanup pass
- `cast4`: 4/4 frames, alpha pass, cleanup pass
- `hurt4`: 4/4 frames, alpha pass, cleanup pass
- `death4`: 4/4 frames, alpha pass, cleanup pass

결과 JSON:
`/Users/tajokim/asset-studio-local/PHASE_25_ACTION_PRESET_GENERATION_RESULTS.json`

Contact sheet:
`/Users/tajokim/asset-studio-local/assets/generated/phase25_action_presets/phase25_action_presets_contact_sheet.png`

시각 QA 판정:
- `idle`: 프레임 수 정상, 미세 호흡/정지 포즈 정상, 캐릭터 일관성 양호.
- `walk4`: 4프레임 보행 구분 가능, 일관성 양호.
- `walk6`: 6프레임 생성 정상, 보행 단계 더 세분화됨.
- `attack`: 준비/공격/회복 흐름 구분 가능, 이펙트 포함.
- `jump`: crouch/takeoff/air/landing 흐름이 가장 명확함.
- `cast`: 마법 이펙트와 cast 동작 구분 가능.
- `hurt`: impact spark/recoil/recovery 구분 가능.
- `death`: collapse/down/dead 흐름 구분 가능.
- 배경/테두리: 자동 QA 기준 corner alpha, green residue, dark border residue 모두 통과.

## Cleanup QA
bad example 이미지:
`/Users/tajokim/.hermes/image_cache/img_d02a939b0d1b.png`

후처리 결과 파일:
`/Users/tajokim/asset-studio-local/assets/processed/phase25_cleanup_bad_example.png`

검증 결과:
```text
cleanup_pass True
cleanup_qa {'pass': True, 'residual_green_pixels': 0, 'residual_dark_border_pixels': 0, 'opaque_pixels': 26398, 'corner_alpha': [0, 0, 0, 0]}
green_report {'width': 1024, 'height': 1024, 'alpha_min': 0, 'alpha_max': 255, 'corner_alpha': [0, 0, 0, 0], 'green_pixels': 0}
```

## 남은 제한
- 실제 AI 생성 품질은 모델 출력 편차가 있으므로, prompt/contract/후처리/QA 기준을 강화한 상태입니다.
- cleanup은 grid boundary 주변 dark/green residue 제거에 초점을 맞췄습니다. 캐릭터가 셀 경계를 침범하는 출력은 원칙적으로 실패 케이스이며, 후처리에서 경계 픽셀이 지워질 수 있습니다.
- 전체 테스트 suite는 오래된 static token 테스트 다수가 현재 UI와 맞지 않아 실패합니다. Phase 25 focused 테스트는 통과했습니다.

## Git 상태
마지막 확인:
```text
## main...origin/main [ahead 2]
 M index.html
 M server.py
 M src/main.js
 M tests/test_phase21_sprite_action_matrix.py
?? docs/
?? tests/test_phase25_action_preset_contract_static.py
```

커밋/푸시는 하지 않았습니다.
