# Phase 11B Report — Project File Button QA + Large File UX

## Scope
- 실제 `프로젝트 저장` / `불러오기` 버튼 경로 QA.
- Project v2 JSON 파일 크기/요약 표시 UX 보강.
- 큰 프로젝트 경고 기준 추가.

## Changes
- cache bust label: `phase11b-project-file-qa`.
- `formatBytes(bytes)` 추가:
  - B / KB / MB 표시.
- `projectSizeWarning(bytes)` 추가:
  - 20MB 이상: 큰 프로젝트 경고.
  - 50MB 이상: 매우 큰 프로젝트 경고 및 ZIP/압축 포맷 필요 안내.
- `projectSummary(project, bytes)` 추가:
  - 이미지 수, 레이어/오브젝트 수, 히스토리 수, 파일 크기 요약.
- `프로젝트 저장` 버튼 경로 개선:
  - 저장 Blob 크기 계산.
  - 저장 완료 상태에 이미지/오브젝트/히스토리/크기 표시.
  - 큰 파일이면 압축/ZIP 개선 필요 메시지 표시.
- `불러오기` 버튼 경로 개선:
  - 파일 읽기 시작 시 파일명/크기/경고 표시.
  - JSON 파싱 후 프로젝트 요약 표시.
  - `FileReader.onerror` 처리 추가.

## Verification
- Verified external URL:
  - `https://later-work-totally-occurrence.trycloudflare.com/?v=phase11b-project-file-qa`
  - page title: `Pixel Asset Studio`.
  - toolbar/save/load UI visible.
- Static/full tests:
  - `pytest -q`: 76 passed.
  - `node --check src/main.js`: pass.
  - `python3 -m py_compile server.py`: pass.
  - `git diff --check`: pass.
- Browser verification on local URL:
  - URL: `http://127.0.0.1:4184/?v=phase11b-project-file-qa`
  - loaded CSS: `styles/app.css?v=phase11b-project-file-qa`.
  - loaded JS: `src/main.js?v=phase11b-project-file-qa`.
  - Automated real UI handler path:
    - Added test image layer + text layer.
    - Clicked `프로젝트 저장` handler and captured generated Blob.
    - Parsed saved `asset-studio-project-v2.json`.
    - Cleared canvas.
    - Dispatched `불러오기` file input change with the saved JSON File.
  - Restore result:
    - image layers: 1.
    - text layers: 1.
    - layer/object names: `Drawing Layer 1`, `Phase11B test image`, `Phase11B text`.
    - history restored: `3`, `historyIndex: 2`.
    - status summary: `프로젝트 파일 파싱 완료 · 이미지 1개 · 레이어/오브젝트 3개 · 히스토리 3개 · 15.6KB`.

## Not Done
- ZIP/압축 포맷 자체는 아직 구현하지 않음.
- 대형 프로젝트 성능 최적화/dedupe는 다음 별도 Phase 후보.

## Next candidate
- Phase 12: Sprite sheet 추출 도구.
  - 이미지/시트에서 개별 스프라이트 자동/수동 추출.
  - 투명 PNG 조각 레이어/파일로 내보내기.
  - grid/connected component 기반 추출 모드.
