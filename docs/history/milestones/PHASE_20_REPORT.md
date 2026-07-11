# Phase 20 — Direction-Validated 8dir Pipeline

## 문제
이전 Phase 19는 `5-source + mirror` 구조는 맞았지만, source로 채택한 `W/SW/NW` 자체가 잘못된 방향이면 그대로 실패했다. 즉, “오른쪽은 flip”은 보장했지만 “왼쪽 source가 진짜 왼쪽인지”를 파이프라인이 검수하지 못했다.

## 교체한 파이프라인
`/api/generate-reference`에서 `direction_mode=8dir`, `animation_mode=idle`일 때:

1. Source 방향만 생성: `S`, `N`, `W`, `SW`, `NW`
2. 각 source마다 후보 생성
3. 생성된 투명 PNG를 vision 방향 QA에 투입
4. QA가 expected direction과 다르면 reject
5. 최대 `ASSET_STUDIO_DIRECTION_QA_ATTEMPTS`회 재시도, 기본 3회
6. 통과한 source만 채택
7. `NW→NE`, `W→E`, `SW→SE` exact horizontal flip
8. 최종 order: `N, NE, E, SE, S, SW, W, NW`
9. 통과 후보가 없으면 fail closed: 결과를 만들지 않음

## 구현 파일
- `server.py`
  - `classify_direction_candidate_with_codex_vision()` 추가
  - `select_valid_direction_candidate()` 추가
  - `_json_from_text()` 다중 JSON/SSE 파싱 보강
  - `generate_reference_8dir_mirror_sheet()`를 후보 생성 + vision 방향검수 + fail-closed 구조로 교체
- `tests/test_phase20_direction_validated_pipeline.py`
  - 재시도 후 통과 후보 채택 테스트
  - 모든 후보 실패 시 fail-closed 테스트
- `tests/test_phase20_web_direction_gate_static.py`
  - 웹 route가 direction QA/retry loop를 포함하는지 검증

## 실제 웹 API 생성 결과
Endpoint:
- `POST http://127.0.0.1:4184/api/generate-reference`
- `direction_mode=8dir`
- `animation_mode=idle`

Output:
- `/Users/tajokim/asset-studio-local/assets/generated/reference_8dir_mirror_1783399677.png`
- method: `reference-image-8dir-mirror+5-source+mirror`

QA:
- order: `N, NE, E, SE, S, SW, W, NW`
- source directions: `S, N, W, SW, NW`
- mirrored pairs: `NW→NE`, `W→E`, `SW→SE`
- corner alpha: `[0,0,0,0]`
- visible green pixels: `0`

Direction QA results:
- `S`: pass attempt 1
- `N`: attempt 1 rejected as `S`; pass attempt 2
- `W`: pass attempt 1
- `SW`: pass attempt 1
- `NW`: pass attempt 1

## 산출물
- Proof: `assets/generated/phase20_direction_validated_result/goblin_8dir_validated_checker_proof.png`
- Sheet: `assets/generated/phase20_direction_validated_result/goblin_8dir_validated_order_N_NE_E_SE_S_SW_W_NW.png`
- Atlas: `assets/generated/phase20_direction_validated_result/goblin_8dir_validated_atlas_2x4.png`
- ZIP: `assets/generated/phase20_direction_validated_result/goblin_8dir_validated_assets.zip`

## 검증
- 실제 W 후보에 대해 `classify_direction_candidate_with_codex_vision(..., 'W')` pass 확인
- Browser load: `http://127.0.0.1:4184/?v=phase20-direction-validated`
- Browser console JS errors: `0`
- `pytest tests/ -q`: `119 passed`
- `node --check src/main.js`: pass
- `python3 -m py_compile server.py`: pass
- `git diff --check`: pass

## 남은 한계
- Pivot/발 위치/스케일은 아직 완전 자동 표준화가 아니다. 다음 개선은 validated source를 받은 뒤 skeleton/pivot 기준선으로 정렬하는 postprocess다.
