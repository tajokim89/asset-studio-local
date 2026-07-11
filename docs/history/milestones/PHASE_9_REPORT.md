# Phase 9 Report — AI Chat to selected-region edit

## Scope
- Phase 9: AI Chat이 현재 선택 이미지 + 선택영역 상태를 읽고, 사용자의 자연어 수정 명령을 `선택영역 AI 수정` 플로우로 연결하도록 개선.
- 실제 AI 생성은 자동 실행하지 않음. 기존 안전 흐름처럼 제안/확인 후 프롬프트 입력칸까지 준비하고, 사용자가 `선택영역 직접 재생성` 버튼으로 실행.

## Changes
- cache bust label: `phase9-ai-chat-region-edit`.
- AI Chat 안내 문구를 선택영역 수정 중심으로 갱신.
- `canvasChatContext()`에 `regionSelection` 추가:
  - 선택영역 개수
  - 선택영역 bbox
- AI Chat 상태줄에 `선택영역 N` 표시.
- `/api/chat` command router 개선:
  - 선택 이미지 + 선택영역이 있는 상태에서 `수정/재생성/inpaint/바꿔/고쳐` 계열 명령 → `prepare_region_inpaint` 액션 반환.
  - 선택영역만 언급하면 `activate_region`으로 영역 도구 전환.
  - 마스크 언급은 기존 `activate_mask`와 분리.
- frontend action executor 개선:
  - `prepare_region_inpaint` 실행 시 `prepareSelectedRegionAiEdit()` 브리지 호출.
  - AI 편집 패널 열기, 프롬프트 입력, bbox 요약 표시까지 연결.
  - `activate_region` 액션 추가.

## Verification
- RED static/server regression: `tests/test_phase9_ai_chat_region_static.py`가 구현 전 4 failures 확인.
- Static/full tests:
  - `node --check src/main.js`: pass.
  - `python3 -m py_compile server.py`: pass.
  - `pytest -q`: 56 passed.
  - `git diff --check`: pass.
- Browser verification on external URL:
  - page title: `Pixel Asset Studio`.
  - AI Chat 상태줄: `선택영역 0` 표시 확인.
  - runtime fixture로 이미지 레이어 + selection overlay 생성.
  - `/api/chat` 응답 action: `prepare_region_inpaint`.
  - chat confirm 후:
    - direct inpaint details open: true.
    - `inpaintPrompt`: `선택영역 얼굴 자연스럽게 수정해줘`.
    - summary: `선택영역 AI 수정 준비: Phase9 Chat Fixture · 38×36`.
  - Console JS errors: 0.

## External URL
https://characterized-educational-steering-submitting.trycloudflare.com/?v=phase9-ai-chat-region-edit-2

## Next candidate
- Phase 10: AI Chat의 실행 계획을 더 실사용형으로 확장.
  - 예: “이거 누끼따고 선택영역만 고친 뒤 PNG로 빼줘” 같은 다단계 플랜을 region/edit/export까지 연결.
  - 또는 먼저 `/api/inpaint` 결과 preview/apply/retry UX polish를 진행.
