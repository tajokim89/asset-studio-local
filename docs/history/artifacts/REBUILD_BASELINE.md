# Asset Studio Rebuild Baseline

측정일: 2026-07-12
기준 커밋: `3376239`
범위: 현재 작업 트리의 Phase 00 및 Hermes 연결 변경 포함
외부 이미지 생성 호출: 0회

## 실행 환경

| 항목 | 값 |
| --- | --- |
| Python | 3.11.15 (`$HERMES_REPO/venv/bin/python`) |
| Node.js | v22.21.1 |
| Bash | 3.2.57 |
| Hermes | v0.18.2 |
| Hermes Provider | `openai-codex`, health `ready` |

## 정적 검증 결과

실행 명령:

```bash
export HERMES_REPO="$HOME/.hermes/hermes-agent"
./scripts/verify_repo.sh static
```

결과:

```text
python: PASS
javascript: PASS
html: PASS
shell: PASS
diff: PASS
```

검사 범위:

- Python: 저장소의 `*.py` 98개를 `py_compile`로 검사
- JavaScript: `node --check src/main.js`
- HTML: Python `HTMLParser`로 `index.html` 전체 입력 파싱
- Shell: `bash -n scripts/run_server.sh scripts/verify_repo.sh`
- Diff: `git diff --check`

## 저장소 규모 기준값

| 대상 | 기준값 |
| --- | ---: |
| Python 파일 | 98개 |
| Python 전체 | 17,057줄 |
| Python 테스트 파일 | 78개 |
| `server.py` | 3,343줄 |
| `src/main.js` | 6,950줄 |
| `index.html` | 215줄 |
| `styles/app.css` | 698줄 |

이 수치는 품질 점수가 아니라 이후 모듈 이동·삭제 작업의 증감 기준이다.

## 아직 검증하지 못한 항목

- 실행 샌드박스에서 PyPI/DNS가 차단되어 `requirements-dev.txt` 설치와 전체 pytest를 실행하지 못했다.
- 실행 샌드박스가 로컬 포트 bind를 거절해 실제 HTTP socket smoke 대신 Handler 메모리 E2E를 사용했다.
- 보이는 브라우저와 Chrome은 실행하지 않았다.
- Hermes 실제 이미지 생성은 실행하지 않았다.
- HTML 검사는 구문 입력 파싱 기준이며 DOM 의미·접근성·레이아웃 검증을 대신하지 않는다.

전체 pytest 결과와 실패 분류는 각각 `P00-05`, `P00-06`에서 이 문서에 추가한다.

`P00-05` 진입점 확인 결과:

```text
$ ./scripts/verify_repo.sh full
pytest is not installed for /Users/kimtajo/.hermes/hermes-agent/venv/bin/python; install requirements-dev.txt first
exit code: 3
```

검증 스크립트가 테스트를 통과한 것처럼 처리하지 않고 의존성 누락을 명시적으로 차단하는 것까지 확인했다.
