# Phase 11A Report — Project Format v2 Save/Load

## Scope
- Project Format v2 도입.
- 단일 JSON 저장 파일 안에 업로드/생성/처리 이미지 dataURL snapshot, canvas, history, editor state를 포함.
- 향후 sprite/ui/map 기능 확장을 위한 빈 module 슬롯 포함.
- 기존 v1 canvas JSON load 호환 유지.

## Changes
- cache bust label: `phase11-project-v2`.
- `canvasJsonSnapshot()` 분리:
  - history/export guide metadata를 보존한 Fabric JSON snapshot 생성.
- `buildProjectV2()` 추가:
  - `app/version/kind` 메타데이터.
  - `document.canvas` 저장.
  - `assets.images[]`에 이미지 dataURL embed.
  - `editor.canvasJson`, `editor.history`, `editor.historyIndex`, `editor.state` 저장.
  - `modules.sprite/ui/map` 빈 구조 포함.
- 이미지 embed:
  - 현재 canvas image object를 dataURL로 snapshot.
  - history canvasJson 안 image src도 dataURL로 치환.
  - `_assetId`, `_assetName` 메타데이터 보존.
- v2 load:
  - `loadProjectV2()`가 history/historyIndex 복원.
  - selectedLayerId, activeDrawingLayerId, canvas size/background/checkerboard/view/mask state 복원.
  - 레이어/히스토리/AI Chat 상태 재렌더.
- legacy v1 load:
  - version 없는 기존 Fabric JSON은 `loadLegacyProjectV1()`로 유지.
- 저장 파일명:
  - `asset-studio-project-v2.json`.

## Verification
- Static/full tests:
  - `node --check src/main.js`: pass.
  - `python3 -m py_compile server.py`: pass.
  - `pytest -q`: 66 passed.
  - `git diff --check`: pass.
- Browser verification on external URL:
  - page title: `Pixel Asset Studio`.
  - loaded cache bust: `phase11-project-v2`.
  - runtime fixture 생성:
    - embedded test image layer.
    - text layer.
    - checkerboard on.
    - history 3 entries.
  - `buildProjectV2()` 결과:
    - version `2`.
    - image assets `1`.
    - history `3`.
    - history image src가 `data:image/png;base64,...`로 embed됨.
    - modules: `sprite`, `ui`, `map`.
  - `loadProjectV2(project)` 후:
    - image/text/drawing layers 복원.
    - image src remains `data:image/png;base64,...`.
    - history `3/3` 복원.
    - checkerboard state 복원.
    - selectedLayerId 복원.

## External URL
https://picture-turtle-citation-holly.trycloudflare.com/?v=phase11-project-v2-b

## Next candidate
- Phase 11B: 실제 파일 버튼 경로 QA + 큰 프로젝트 UX.
  - 실제 `프로젝트 저장` 다운로드 파일을 다시 `불러오기`로 여는 브라우저 수동 경로 검증.
  - 파일 크기 표시/경고 UI 개선.
  - base64 중복 dedupe/압축 또는 ZIP 포맷 검토.
- 이후 Phase 12: Sprite sheet 추출 도구.
