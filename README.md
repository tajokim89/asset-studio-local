# Asset Studio Local

로컬 브라우저에서 이미지와 픽셀 게임 에셋을 편집·생성하는 도구입니다.

## 주요 기능

- Fabric.js 기반 캔버스 편집, 이동·크기 조절·회전·좌우/상하 반전
- 이미지 업로드, 텍스트·도형·드로잉 레이어
- 레이어 표시/잠금/정렬/복제/그룹/내보내기
- 영역 선택, 복사·잘라내기·붙여넣기, 마스크 편집
- AI 배경 제거, 선택 영역 수정, 오브젝트 교체
- 픽셀 에셋 생성과 기준 이미지 기반 방향·동작 스프라이트 생성
- 스프라이트 자동 탐지, 고정 그리드 분할, 애니메이션 미리보기
- PNG 내보내기와 JSON 프로젝트 저장/불러오기

## 로컬 실행

권장 실행 방법:

```bash
./scripts/run_server.sh
```

수동 실행:

```bash
python3 -m pip install -r requirements.txt
python3 server.py
```

브라우저에서 다음 주소를 엽니다.

```text
http://127.0.0.1:4184
```

## AI 생성 설정

`server.py`는 실행 중인 컴퓨터에 설치된 Hermes의 `openai-codex` 이미지 제공자를 사용합니다. Hermes 설치와 `hermes auth codex` 인증을 먼저 완료하세요. 설치 위치는 `HERMES_REPO`, `HERMES_HOME`, PATH의 `hermes`, 표준 설치 경로 순서로 자동 탐색합니다.

Hermes 경로를 명시적으로 고정해야 할 때만 다음처럼 지정합니다.

```bash
export HERMES_REPO=/path/to/hermes-agent
python3 server.py
```

이미지 제공자를 사용할 수 없어도 정적 편집기는 실행되지만 AI 생성 API는 실패합니다.
페이지 상단의 `Hermes 준비됨` 배지에서 설치·인증 상태를 확인할 수 있습니다.
권장 실행 스크립트는 기본 이미지 모델을 `gpt-image-2-high`로 설정합니다. 비용·속도를 우선할 때만 `OPENAI_IMAGE_MODEL` 환경변수로 다른 tier를 지정하세요.

## 개발 환경과 테스트

Python 3.11 이상으로 저장소 전용 가상환경을 만든 뒤 개발 의존성을 설치합니다.

```bash
export HERMES_REPO="${HERMES_REPO:-$HOME/.hermes/hermes-agent}"
"$HERMES_REPO/venv/bin/python" -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Hermes와 무관한 환경에서는 첫 번째 명령 대신 설치된 Python 3.11 이상의
`python3 -m venv .venv`를 사용하면 됩니다.

저장소 검증은 한 스크립트에서 실행합니다.

```bash
./scripts/verify_repo.sh static
./scripts/verify_repo.sh focused tests/test_hermes_environment.py
./scripts/verify_repo.sh full
```

## 프로젝트 문서

- 완료된 개발 이력과 QA 보고서: [`docs/history/`](docs/history/)
- 설계 문서와 작업 계획: [`docs/plans/`](docs/plans/)
- 최신 세션 인수인계: [`SESSION_HANDOFF_2026-07-10.md`](SESSION_HANDOFF_2026-07-10.md)

개발 이력 문서는 참고용이며 런타임 코드나 테스트의 버전 키로 사용하지 않습니다.
