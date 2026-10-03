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

## 이미지 생성과 스프라이트

이미지 생성·UI·오브젝트는 설치된 Codex의 ChatGPT 로그인과 기본 이미지 생성 기능을 사용합니다. Hermes나 별도 API 키는 필요하지 않습니다.

```powershell
codex login
codex login status
.\.venv\Scripts\python.exe server.py
```

Codex CLI는 현재 계정의 모델을 지원하는 최신 버전을 사용하세요. 다른 위치의 실행 파일을 사용할 때는 `ASSET_STUDIO_CODEX_COMMAND`를 네이티브 `codex.exe` 경로로 지정합니다. 인증은 Codex가 관리하며 Asset Studio는 토큰을 읽거나 복사하지 않습니다. 연결 상태 확인은 로컬 준비 상태이며 실제 사용 가능 여부는 이미지 생성 결과로 확인됩니다.

스프라이트는 선택된 이미지를 로컬 ComfyUI의 H3/H3 Fast로 움직입니다. 기본 출력은 25프레임이며 생성 길이와 재생 FPS를 따로 조절할 수 있습니다. ComfyUI 주소와 폴더는 `ASSET_STUDIO_COMFY_URL`, `ASSET_STUDIO_COMFY_ROOT`로 지정합니다.

기존 모션·3D 작업공간은 앱에서 제거했습니다. 이전 자동 시각 검수 경로는 새 제공자에서 지원하지 않으며, 결과를 직접 재생해 확인하세요.

## 게임 에셋 작업 재사용

다른 게임에서 요청하는 방법, 프레임 추출, 느린 검수 GIF, 일관성 검수와 실패 사례는 [스프라이트 작업 가이드](docs/SPRITE_WORKFLOW.ko.md)를 참고하세요. 생성 이미지·GIF와 모델·인증정보는 저장소에 보관하지 않습니다.

## 개발 환경과 테스트

Python 3.11 이상으로 저장소 전용 가상환경을 만든 뒤 개발 의존성을 설치합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Windows에서는 `.venv/Scripts/python.exe` 경로를 사용합니다.

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
