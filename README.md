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

`server.py`는 로컬 Hermes 이미지 제공자를 사용할 수 있습니다. Hermes 경로가 기본 위치와 다르면 다음처럼 지정합니다.

```bash
export HERMES_REPO=/path/to/hermes-agent
python3 server.py
```

이미지 제공자를 사용할 수 없어도 정적 편집기는 실행되지만 AI 생성 API는 실패합니다.

## 프로젝트 문서

- 완료된 개발 이력과 QA 보고서: [`docs/history/`](docs/history/)
- 설계 문서와 작업 계획: [`docs/plans/`](docs/plans/)
- 최신 세션 인수인계: [`SESSION_HANDOFF_2026-07-10.md`](SESSION_HANDOFF_2026-07-10.md)

개발 이력 문서는 참고용이며 런타임 코드나 테스트의 버전 키로 사용하지 않습니다.
