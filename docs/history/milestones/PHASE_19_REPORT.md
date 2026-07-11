# Phase 19 — Web 8-Direction Mirror Pipeline

## 요청
- 8방향을 전부 독립 생성하지 말 것.
- 웹페이지 생성 경로에 `4/5 source + flip` 방식을 적용할 것.
- 앞/뒤는 따로 만들고, 오른쪽 방향은 flip으로 만들 것.

## 적용 내용
- `/api/generate-reference`에서 `direction_mode=8dir`, `animation_mode=idle` 요청 시 새 파이프라인 사용.
- 모델 생성 source 방향은 `S`, `N`, `W`, `SW`, `NW`만 허용.
- `E`, `SE`, `NE`는 절대 모델에 독립 생성 요청하지 않고 앱에서 horizontal flip으로 생성.
- 최종 order: `N, NE, E, SE, S, SW, W, NW`.
- 프론트엔드 payload를 명시 변수화하여 direction/reference/target mode가 웹 요청에 안정적으로 포함되도록 정리.

## 구현 파일
- `server.py`
  - `build_8dir_mirror_sheet_from_source_pngs()` 추가
  - `generate_reference_8dir_mirror_sheet()` 추가
  - `/api/generate-reference` 8dir idle branch 추가
- `src/main.js`
  - `directionMode`, `targetDirection`, `referenceDirection`, `animationMode` 변수화
- `tests/conftest.py`
  - 테스트 import path 안정화
- `tests/test_phase19_mirror_8dir_pipeline.py`
  - 5-source + exact flip 회귀 테스트
- `tests/test_phase19_web_mirror_pipeline_static.py`
  - 웹 API route/static wiring 테스트

## 실제 웹 API 생성 결과
Endpoint:
- `POST http://127.0.0.1:4184/api/generate-reference`
- `direction_mode=8dir`
- `animation_mode=idle`

결과:
- `/Users/tajokim/asset-studio-local/assets/generated/reference_8dir_mirror_1783395590.png`
- method: `reference-image-8dir-mirror+5-source+mirror`
- order: `N, NE, E, SE, S, SW, W, NW`
- source directions: `S, N, W, SW, NW`
- mirrored pairs: `NW→NE`, `W→E`, `SW→SE`
- corner alpha: `[0,0,0,0]`
- green pixels: `0`

## 산출물
- Proof: `assets/generated/phase19_web_mirror_result/goblin_8dir_web_mirror_checker_proof.png`
- Sheet: `assets/generated/phase19_web_mirror_result/goblin_8dir_web_mirror_order_N_NE_E_SE_S_SW_W_NW.png`
- Atlas: `assets/generated/phase19_web_mirror_result/goblin_8dir_web_mirror_atlas_2x4.png`
- ZIP: `assets/generated/phase19_web_mirror_result/goblin_8dir_web_mirror_assets.zip`

## 검증
- Browser load: `http://127.0.0.1:4184/?v=phase19-web-mirror`
- Browser console JS errors: `0`
- `pytest tests/ -q`: `116 passed`
- `node --check src/main.js`: pass
- `python3 -m py_compile server.py`: pass
- `git diff --check`: pass
