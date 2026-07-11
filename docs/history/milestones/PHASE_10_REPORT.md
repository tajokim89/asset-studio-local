# Phase 10 Report — Inpaint preview/apply UX

## Scope
- Phase 10: 선택영역 AI 직접 재생성 결과를 즉시 덮어쓰지 않고, 미리보기 후 적용 방식을 고르는 UX로 고정.
- 다음 단계 다단계 AI Chat/자동 export는 포함하지 않음.

## Changes
- cache bust label: `phase10-inpaint-preview-apply`.
- AI inpaint 실행은 `apply_mode: 'preview'`로 요청하고 `pendingInpaintResult`에 보관.
- 결과 tray 유지:
  - `AI 결과 미리보기`
  - `새 레이어 적용`
  - `선택 이미지 교체`
  - `다시 생성`
  - `취소`
- `새 레이어 적용`: patch PNG를 bbox 위치의 새 레이어로 추가.
- `선택 이미지 교체`: 원본 이미지 레이어를 숨김 보존하고 replacement 레이어 생성.
- `다시 생성`: 기존 prompt/negative로 재요청.
- `취소`: pending preview 제거.
- 적용 시 history 저장/Undo 경로 유지.

## Verification
- Static/full tests:
  - `node --check src/main.js`: pass.
  - `python3 -m py_compile server.py`: pass.
  - `pytest -q`: 61 passed.
  - `git diff --check`: pass.
- Browser verification on external URL:
  - page title: `Pixel Asset Studio`.
  - loaded CSS/JS cache bust: `phase10-inpaint-preview-apply`.
  - `inpaintPreviewPanel` exists and is hidden initially.
  - preview action buttons exist and are disabled before a result:
    - `새 레이어 적용`
    - `선택 이미지 교체`
    - `다시 생성`
    - `취소`
  - Console JS errors: 0.

## External URL
https://picture-turtle-citation-holly.trycloudflare.com/?v=phase10-inpaint-preview-apply

## Next candidate
- Phase 11: 실사용형 AI Chat 플랜 확장.
  - 예: “누끼 따고, 선택영역 고치고, PNG로 빼줘” 같은 다단계 명령을 `remove-bg → region/inpaint 준비 → export` 계획으로 분해.
  - 각 단계는 자동 실행 전 확인 버튼을 거치게 유지.
