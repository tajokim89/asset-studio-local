# Asset Studio Local — Autonomous Execution Goal Prompt

아래 블록 전체를 새 Hermes 세션이나 작업 에이전트의 Goal로 그대로 사용한다.

```text
/Users/tajokim/asset-studio-local 프로젝트에서 Asset Family Production Overhaul을 자율적으로 끝까지 실행하라.

프로젝트 루트:
/Users/tajokim/asset-studio-local

반드시 먼저 읽을 문서:
1. /Users/tajokim/asset-studio-local/SESSION_HANDOFF_2026-07-10.md
2. /Users/tajokim/asset-studio-local/docs/plans/2026-07-10-asset-family-production-overhaul.md

사용할 작업 방식:
- ai-image-editor-prototyping 스킬
- subagent-driven-development 스킬
- test-driven-development 스킬
- requesting-code-review 스킬
- 필요하면 systematic-debugging 스킬

목표:
현재 sprite 중심 facade를 제거하고 sprite actor/effect, tile/map, UI component, world object가 각각 다음 전체 제작 루프를 갖도록 완성한다.

family-specific core request
→ shared style/reference
→ family-only production settings
→ isolated normalized payload
→ prompt consuming every visible setting
→ family-specific postprocess
→ family-specific preview
→ family-specific QA
→ engine-usable export + metadata

실행 규칙:
1. 계획 파일의 Milestone A부터 J까지 task 순서를 그대로 따른다.
2. 계획 파일을 한 번 읽고 전체 task와 acceptance criteria를 파악한다.
3. 각 task는 strict TDD로 진행한다.
   - failing test를 먼저 작성한다.
   - focused test를 실행해 예상 이유로 RED인지 확인한다.
   - 최소 production code를 작성한다.
   - focused test를 GREEN으로 만든다.
   - syntax와 regression을 확인한다.
4. 각 task 후 독립적인 spec compliance review를 먼저 수행한다.
5. spec PASS 후 독립적인 code quality review를 수행한다.
6. 두 review가 모두 통과해야 다음 task로 진행한다.
7. task가 완료되면 계획 MD의 checkbox를 [x]로 바꾸고 RED/GREEN/test/browser/review 증거를 바로 기록한다.
8. 사용자가 전체 계획의 연속 실행을 승인했다. task가 통과하면 승인 질문 없이 다음 task로 계속 진행한다.
9. 실제 브라우저 기능은 static token test로 끝내지 말고 실제 UI를 클릭하고 console을 확인한다.
10. 다운로드 산출물은 실제 browser UI가 만든 PNG/ZIP/JSON을 검사한다.
11. 유료 AI 생성은 static/focused/browser wiring이 모두 통과한 뒤 family당 최대 1개의 저비용 smoke로 제한한다. 실패를 무한 재시도하지 않는다.
12. 각 milestone 종료 시 보고서를 docs/history/milestones 아래에 작성한다.
13. 최종적으로 full pytest, py_compile, node --check, git diff --check, browser integration을 수행한다.

가장 중요한 안전 규칙:
- 이 저장소는 시작부터 dirty 상태다.
- 먼저 git status --short, git diff --stat, 관련 task 파일 diff를 baseline으로 기록하라.
- pre-existing changes와 이번 task delta를 분리해서 판단하라.
- 기존 tracked 수정/삭제와 untracked 파일을 임의로 정리하지 마라.
- git reset, git clean, git stash, unrelated restore, rm -rf를 하지 마라.
- git add -A, commit, push를 하지 마라. 사용자가 별도로 승인하기 전까지 변경은 검증된 uncommitted 상태로 남겨라.
- task가 허용한 파일과 필요한 새 test/report 파일만 수정하라.

멈추고 사용자에게 보고해야 하는 경우:
- 비밀키·비밀번호·권한 입력 필요
- 결제 또는 반복 유료 호출 필요
- 파일 삭제/reset/clean/stash/대량 이동 필요
- 기존 사용자 변경과 task 변경을 안전하게 분리할 수 없음
- 사양끼리 실제 충돌함
- 같은 blocker가 두 번의 원인 분석·수정 후에도 해결되지 않음

그 외에는 사소한 선택을 물어보지 말고 문서와 기존 convention에 맞는 안전한 기본값으로 계속 실행하라.

완료 판정:
- 패밀리 탭/설정/payload만 존재하면 완료가 아니다.
- actor/effect/tile/ui/object 각각 실제 authoring path, preview, QA, export가 있어야 한다.
- Effect는 effect_sequence가 ui_static/1 frame으로 collapse되면 안 된다.
- Effect frame 분리는 connected-component count가 아니라 declared sequence grid를 기본으로 한다.
- Trim 시 sourceSize/trimRect/pivot을 보존하고 common canvas로 복원한다.
- Tile은 terrain topology, repeat/paint preview, rule coverage와 engine metadata를 포함한다.
- UI는 9-slice, safe area, states, resize/assembly preview와 metadata를 포함한다.
- Object는 pivot, ground/Y-sort, collision, interaction, states, map-placement preview와 metadata를 포함한다.
- 모든 visible setting은 payload와 provider prompt까지 도달해야 한다.
- 다른 family의 actor/idle/direction 상태가 섞이면 FAIL이다.
- Browser console error는 0이어야 한다.
- 신규 regression은 0이어야 한다.

진행 보고는 간결하게 하되, 매 milestone마다 다음을 남겨라.
- 적용
- RED/GREEN 검증
- focused/full test 결과
- browser 검증
- review verdict
- 남은 blocker

지금 즉시 다음 순서로 시작하라.
1. 두 문서 읽기
2. git baseline 기록
3. 계획 task 전체를 todo로 변환
4. Task A1 감사표 작성
5. Task A2부터 strict TDD 실행
6. 이후 Milestone J까지 승인 질문 없이 계속 진행

최종 산출물:
- 완료 체크와 evidence가 갱신된 master plan
- Phase 2/3/4/5 milestone reports
- final integration report
- 갱신된 SESSION_HANDOFF_2026-07-10.md
- 검증된 source/tests/browser workflow
- commit/push하지 않은 정확한 final git status
```
