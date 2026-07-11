# Phase 17 Hotfix — Pixel Generate Button

## Bug
`도트 에셋 생성`을 눌러도 생성이 시작되지 않았다.

## Root Cause
Phase 17에서 AI 패널 HTML을 정리하면서 legacy controls (`generateBtn`, `aiPrompt`, `aiPreset`, `aiAspect`)를 제거했는데, `generatePixelAsset` click handler는 여전히 `$('generateBtn')?.click()`만 호출했다.

결과:
- `도트 에셋 생성` 클릭 → 프롬프트만 조립됨
- 실제 `generateAiAsset()` 호출 없음
- 하단 `$('generateBtn').onclick = ...`도 null element 때문에 로드 중 예외 가능

## Fix
- `도트 에셋 생성` 버튼이 직접 `generateAiAsset()`을 호출하도록 변경.
- `generateAiAsset()`이 legacy hidden fields 없이도 동작하도록 fallback 추가:
  - prompt 없으면 `buildPixelAssetPrompt()` 사용
  - preset 없으면 pixel/ui fallback
  - aspect 없으면 `square`
  - disable target은 `generateBtn` 없으면 `generatePixelAsset`
- `generateBtn` binding은 element가 있을 때만 수행.
- 기준 이미지 체크가 켜져 있어도 선택 이미지가 없으면 일반 `/api/generate`로 fallback해서 버튼이 막히지 않게 함.

## Verification
- Regression/static tests: `107 passed`
- JS syntax: `node --check src/main.js`
- Python syntax: `python3 -m py_compile server.py`
- `git diff --check`
- Browser UI event-path test:
  - Opened external tunnel page.
  - Clicked visible `AI 생성` tool.
  - Typed subject into visible Subject field.
  - Stubbed `/api/generate` to avoid spending real generation.
  - Clicked visible `도트 에셋 생성` button.
  - Verified `/api/generate` was called with payload:
    - `background_mode: chroma_green`
    - `direction_mode: 8dir`
    - `reference_direction: S`
    - `animation_mode: idle`
    - `chroma_mode: global`
  - Verified canvas got new image layer named `AI 생성 에셋`.
  - Console errors: none.
