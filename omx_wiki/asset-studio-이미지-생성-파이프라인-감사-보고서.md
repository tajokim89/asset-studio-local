---
title: "Asset Studio 이미지 생성 파이프라인 감사 보고서"
tags: ["asset-studio", "image-generation", "sprite", "pipeline-audit", "dungeon-cleanup-inc", "ui", "qa", "export"]
created: 2026-07-11T14:29:56.759Z
updated: 2026-07-11T23:58:55+09:00
sources: []
links: ["asset-studio-저장소-감사-및-개선-백로그.md", "asset-studio-제품-목적과-스프라이트-합격-기준.md", "asset-studio-최신-제품-방향-및-생성-검증-재설계.md", "asset-studio-기존-문서-통합-및-정리-판정.md"]
category: architecture
confidence: high
schemaVersion: 1
---

# Asset Studio 이미지 생성 파이프라인 감사 보고서

> 기준일: 2026-07-11
> 조사 방식: 브라우저와 서버를 실행하지 않고 Asset Studio 코드, 테스트, 소비 게임 코드, 실제 PNG 메타데이터와 픽셀을 교차 검사했다.
> 변경 범위: 분석만 수행했으며 제품 소스는 수정하지 않았다.
>
> **정정:** 이 문서의 코드·픽셀 감사 결과는 유효하지만, `dungeon-cleanup-inc`를 유일한 제품 목표로 둔 결론은 폐기한다. 해당 저장소와 88×88 규격은 프로토타입 출력 프로필·회귀 사례로만 사용한다. 범용 제품 방향과 최신 우선순위는 [[asset-studio-최신-제품-방향-및-생성-검증-재설계]], 기존 내용의 유지·폐기 판정은 [[asset-studio-기존-문서-통합-및-정리-판정]]을 따른다.

## 결론

전체 이미지 생성 프로세스는 변경해야 한다. 특히 스프라이트 제작부는 사실상 전면 재설계가 필요하다.

현재 시스템은 게임용 애니메이션을 제작하는 파이프라인이라기보다 다음 흐름에 가깝다.

    모델에게 시트 한 장을 그려 달라고 요청
      -> 제한적인 배경 제거와 이미지 검사
      -> 서버 응답 성공
      -> 결과를 자동으로 캔버스에 채택

이 구조로는 idle, walk, attack의 실제 동작, 프레임 연결, 방향, 발 위치, 캐릭터 동일성, 게임 파일 규격을 보장할 수 없다.

다만 저장소 전체를 폐기할 필요는 없다.

| 영역 | 판단 |
| --- | --- |
| Fabric.js 캔버스 편집기 | 유지 |
| 마스크 편집과 로컬 영역 합성 | 유지 |
| 결과 저장, rollback, 프로젝트 히스토리 | 유지 |
| PNG 분할과 ZIP 저수준 유틸 | 유지 |
| 생성 요청과 Provider 연결 | 교체 |
| 스프라이트 생성 | 전면 재설계 |
| QA, 승인, 결과 채택 | 재연결 |
| 프로필 기반 내보내기 | 공통 manifest와 교체 가능한 출력 프로필로 재구축 |
| Tile, UI, Object 계약 UI | 검증된 레시피만 기본 화면에 두고 미검증 기능은 Lab으로 격리 |

제품 목적과 스프라이트 합격 기준은 [[asset-studio-제품-목적과-스프라이트-합격-기준]]을 따른다. 저장소 전반의 정리 후보는 [[asset-studio-저장소-감사-및-개선-백로그]]과 함께 관리한다.

## 저장소가 현재 하는 일

Asset Studio는 로컬 이미지 편집기와 AI 게임 에셋 생성기를 합친 도구다.

- index.html: 편집기와 모든 에셋 유형 설정 UI
- src/main.js: 캔버스, 생성 요청, 결과 관리, QA, 미리보기, 내보내기
- server.py: 로컬 HTTP 서버, 외부 이미지 Provider, 후처리
- scripts/: 특정 고블린과 액션을 생성하기 위한 일회성 스크립트
- tests/: 계약, 정적 문자열, 후처리 테스트

근거:

- README.md:3-14
- src/main.js
- server.py
- index.html

문제는 범용 범위 자체가 아니라, 각 에셋 계열의 생성·검증·내보내기 계약이 연결되지 않은 상태에서 미완성 메뉴가 한꺼번에 노출됐다는 것이다.

## 프로토타입 출력 프로필의 실제 스프라이트 계약

아래 값은 범용 제품 규격이 아니라 `dungeon-cleanup-inc/actor-v1` 프로필을 만들 때 재사용할 수 있는 사례 근거다.

/Users/kimtajo/git/dungeon-cleanup-inc/scripts/PlayerController.gd:17-117 기준:

- 프레임 크기: 88x88 RGBA
- 방향: 8방향
  - south
  - south-east
  - east
  - north-east
  - north
  - north-west
  - west
  - south-west
- Idle
  - 폴더: Breathing_Idle
  - 방향당 4프레임
  - 4 FPS
  - loop
- Walk
  - 폴더: Walking
  - 방향당 6프레임
  - 8 FPS
  - loop
- 파일명: frame_000.png, frame_001.png 형식
- 로딩 경로:

    animations/{action}/{direction}/frame_%03d.png

현재 실제 캐릭터 에셋 88개도 모두 88x88 RGBA다.

- Breathing_Idle: 8방향 x 4프레임 = 32
- Walking: 8방향 x 6프레임 = 48
- rotations: 8방향 x 1프레임 = 8

픽셀 검사 결과:

- 캐릭터 실루엣 높이: 약 40~44px
- 알파 bbox 하단: y=63~65
- 고정 contact/root 기준은 대략 전체 캔버스 높이의 0.73~0.75

Asset Studio에는 이 규격을 나타내는 프로젝트 프로필이 없다. 기본 출력은 512x512이고 방향 이름, 폴더명, 액션명, FPS, Godot 경로가 전부 범용값이다.

과거 문서 /Users/kimtajo/git/dungeon-cleanup-inc/docs/05_PIXCELLAB_PROMPTS.md의 48x48, 4방향, 3프레임 권장은 현재 런타임 코드와 충돌하므로 더 이상 source of truth로 사용하면 안 된다.

## 확인된 P0 문제

### P0-1. 상세 스프라이트 프롬프트가 실제 일반 생성 요청에 연결되지 않는다

src/main.js:1146의 buildPixelAssetPrompt는 idle, walk, attack 동작을 자세히 작성한다.

그러나 src/main.js:1179의 syncPixelAssetPrompt는 결과를 aiPrompt에 기록하며, 현재 index.html에는 aiPrompt 요소가 없다.

실제 생성은 다음 경로에서 assetCorePrompt 원문을 사용한다.

- src/main.js:925 buildAssetGenerationPayload
- src/main.js:6364 generateAiAsset

따라서 UI의 상세 동작 규칙, 프레임별 수락 조건, 프롬프트 미리보기 상당 부분은 실제 일반 생성 경로에서 우회된다. action, direction, frame_count의 간단한 계약은 서버로 전달되지만 상세 포즈 문법은 전달되지 않는다.

### P0-2. 선택 이미지 기반 attack, hurt, death 요청이 idle로 변질된다

선택 이미지 생성 경로는 src/main.js:6441-6512와 src/main.js:6563-6610에서 다음 값을 보낸다.

- idle4
- attack4
- jump4
- cast4
- hurt4
- death4

하지만 server.py:1065-1083의 payload 정규화는 base action 이름만 허용한다.

- idle
- walk, walk4, walk6
- attack
- jump
- cast
- hurt
- death

직접 정규화 결과:

    idle4   -> idle
    walk4   -> walk4
    walk6   -> walk6
    attack4 -> idle
    jump4   -> idle
    cast4   -> idle
    hurt4   -> idle
    death4  -> idle

따라서 사용자가 선택 이미지 기준으로 attack을 요청해도 서버 계약에는 idle이 들어간다. 원문 prompt에는 attack이 남을 수 있어 한 요청 안에서 attack 문구와 idle 계약이 충돌할 가능성도 있다.

### P0-3. Green Chroma 기본값이 녹색 고블린 픽셀을 삭제한다

UI 기본값은 global green 제거다. server.py:1418-1427의 판정은 정확한 #00FF00뿐 아니라 녹색 우세 픽셀을 폭넓게 chroma로 간주한다.

현재 dungeon-cleanup-inc의 88개 캐릭터 PNG에 동일 판정식을 적용한 결과:

- 불투명 픽셀: 69,109
- chroma로 판정되는 실제 캐릭터 픽셀: 6,183
- 비율: 8.95%
- 일부 프레임: 약 17.7%

현재 기본 후처리는 배경만이 아니라 고블린 피부와 의상 픽셀을 실제로 지울 수 있다.

관련 코드:

- src/main.js:790-796
- server.py:1418-1427
- server.py:1900-1928

### P0-4. 일반 액션은 전체 애니메이션을 이미지 한 장으로 생성한다

server.py:2466-2528의 기준 이미지 생성은 한 번의 image generation 요청으로 전체 시트 한 장을 요구한다.

- 크기: 대체로 1024x1024 정사각형
- 배경: opaque
- partial_images: 1

8방향 idle에만 5방향 생성 후 미러링하는 특수 경로가 있다. walk, attack, hurt, death 등 일반 액션은 시트 한 장 생성에 의존한다.

이 방식으로는 다음을 보장할 수 없다.

- 프레임마다 동일한 캐릭터 정체성
- 정확한 액션 단계
- 동일한 root와 발 기준선
- 동일한 크기와 팔레트
- 자연스러운 loop
- 정확한 방향과 프레임 셀

### P0-5. 출력 W/H는 실제 생성 크기나 게임 캔버스를 강제하지 않는다

src/main.js:925-946은 output.width와 output.height를 payload에 넣고 server.py:1227-1252는 이를 정규화한다.

그러나 server.py:3247-3293의 실제 일반 생성은 다음 호출만 수행한다.

    provider.generate(prompt, aspect_ratio=aspect)

88x88 resize, 공통 캔버스 정규화, anchor 배치가 없다. 따라서 UI에서 88x88을 입력해도 88x88 게임 프레임을 보장하지 않는다.

### P0-6. QA가 생성 승인과 채택을 차단하지 않는다

현재 기본 스프라이트 QA는 주로 다음을 검사한다.

- 셀 분할 가능 여부
- 프레임이 전부 같은지
- 이미지가 비어 있지 않은지
- 일부 배경과 방향 상태

이 결과가 실제로 attack으로 보이는지, walk의 다리 지지가 교차하는지, 동일 캐릭터인지, loop가 자연스러운지는 생성 차단 조건이 아니다.

server.py:383의 route_family_qa는 더 강한 구조를 가지고 있지만 생성 API에서는 호출되지 않고 테스트에서만 사용된다.

클라이언트의 resultWalkQaGate도 src/main.js:383에 정의되어 있으나 adoptResult에서는 사용되지 않는다. 테스트도 이 gate가 adoptResult에 없음을 요구한다.

생성 성공 직후 src/main.js:6411-6417에서 adoptResult를 자동 호출한다. 재시도 결과도 src/main.js:429-435에서 자동 채택한다.

즉 모델 응답 성공과 제품 에셋 승인 성공이 구분되지 않는다.

### P0-7. 생성, 배경 제거, 그리드 자동 워크플로가 중간에서 종료된다

src/main.js:6650-6675의 runPixelWorkflow는 generateAiAsset 결과에서 result.img를 요구한다.

그러나 generateAiAsset은 다음 값만 반환한다.

- url
- result
- data
- referenceObj

따라서 다음 조건에서 바로 종료된다.

    if (!result?.img) return null;

화면에는 생성, 배경 제거, 그리드 값 맞춤으로 보이지만 실제 자동 배경 제거와 그리드 정리는 실행되지 않는다.

### P0-8. 현재 환경에서는 외부 이미지 Provider를 찾을 수 없다

server.py:33-35의 기본 Provider 경로:

    /Users/tajokim/.hermes/hermes-agent

현재 셸 기준:

- HERMES_REPO 환경변수 없음
- 기본 Hermes 저장소 없음
- plugins/image_gen/openai-codex/__init__.py 없음

server.py:452-468의 시작 검사는 Pillow, numpy, httpx만 검사하고 Provider 파일 존재 여부와 인증 상태는 검사하지 않는다.

따라서 현재 환경에서는 정적 편집기는 실행할 수 있어도 생성 요청 시점에 실패한다.

## 8방향 미러 전략 문제

server.py:636-648과 server.py:1851-1896은 다음 전역 규칙을 사용한다.

- 직접 생성: S, N, W, SW, NW
- 미러 생성: E <- W, SE <- SW, NE <- NW

현재 승인된 캐릭터 에셋을 픽셀 단위 비교한 결과:

- Breathing_Idle
  - E/W: 전 프레임 정확한 미러
  - SE/SW: 전 프레임 정확한 미러
  - NE/NW: 미러 아님
- Walking
  - E/W: 전 프레임 정확한 미러
  - SE/SW: 전 프레임 정확한 미러
  - NE/NW: 미러 아님
- rotations
  - E/W: 미러 아님
  - SE/SW: 미러 아님
  - NE/NW: 미러 아님

따라서 미러 사용 여부는 전역 상수가 아니라 캐릭터, 액션, 방향쌍별 정책이어야 한다. 장비 손잡이와 비대칭 디자인이 있는 캐릭터는 미러로 handedness가 뒤집힐 수 있다.

## UI, Tile, Object 계약 불일치

src/main.js:562-567의 화면 노출 subtype과 src/main.js:167-170의 AssetResult 허용 subtype이 다르다.

교집합:

- UI: 화면 11개 중 2개만 결과 저장 가능
- Tile: 화면 8개 중 3개만 가능
- Object: 화면 9개 중 3개만 가능

나머지는 서버 생성에 성공해도 클라이언트 createAssetResult 단계에서 실패할 수 있다.

src/main.js:6200-6222의 export route도 또 다른 subtype 목록을 사용한다. UI, 결과 저장, 내보내기가 하나의 계약을 공유하지 않는다.

Object 내보내기 src/main.js:6196은 objectFamilyMetadata를 요구한다. 그러나 생성 결과 채택 코드 src/main.js:337-343은 resultId, resultFamily, resultType만 설정하며 objectFamilyMetadata를 할당하지 않는다. 따라서 생성한 Object 결과를 현재 전용 미리보기와 export 흐름으로 넘길 수 없다.

## 생성 후처리의 family별 실효성

### Sprite

- chroma 제거
- residue cleanup
- single idle일 때만 방향 후보 선택
- 다른 action의 방향 QA는 skipped

근거: server.py:1900-1928

### Effect

- alpha 또는 chroma cleanup
- status를 effect-isolated로 기록
- 실제 프레임 진행 의미와 VFX 동작 검증 없음

근거: server.py:1932-1947

### UI

- 이미지 bytes 보존
- source_size와 실제 크기 비교
- 상태별 생성, 동일 캔버스, 9-slice 안전성, text-free 여부를 강제하지 않음

근거: server.py:1973-1988

### Object

- 한 장의 이미지 크기와 alpha 존재 여부 검사
- 여러 states를 요청해도 actual_image_count는 항상 1
- state ID에는 이미지가 할당되지 않음

근거: server.py:1991-2023

### Tile

- atlas 예상 크기와 실제 크기 비교
- geometry_matches가 false여도 status는 validated
- API는 HTTP 성공으로 반환

근거: server.py:2026-2034, server.py:3247-3293

## dungeon-cleanup-inc의 UI 계약과 현재 에셋 문제

DESIGN.md:65-95 기준:

- 생성 UI 아트는 frame과 icon으로 사용
- 한국어 텍스트는 Godot Label로 렌더링
- 투명 배경 pixel icon
- 읽을 수 있는 텍스트를 이미지에 굽지 않음

실제 UiAssetStyles.gd:4-13은 다음 상태 이미지를 사용한다.

- black brass plate: normal, hover, pressed, disabled
- contract card: normal, selected
- item slot: normal, hover, selected, disabled

현재 상태 이미지 크기:

- Plate: 323~326 x 78~83
- Item Slot: 159~160 x 155~167
- Contract Card: 333x195, 336x189

UiAssetStyles.gd:132-165는 동일한 9-slice margin을 상태별 이미지에 적용한다.

- Plate texture margin: 22
- Contract Card texture margin: 24
- Item Slot texture margin: 18

같은 컴포넌트의 상태 이미지가 서로 다른 캔버스를 사용하면 hover, pressed, disabled 전환 시 경계와 내용 위치가 흔들릴 수 있다.

UI 생성 파이프라인은 다음을 강제해야 한다.

- 상태별 동일한 W/H
- 동일한 9-slice 경계
- 동일한 content safe area
- 투명 PNG
- text-free
- 상태별 장식만 변화
- Godot preload 경로와 상태 이름 그대로 패키징

large_empty_modal_panel_frame은 메타데이터 외 런타임 참조를 찾지 못했으므로 현재 미사용 후보다.

## 목표 스프라이트 제작 파이프라인

    Dungeon 프로젝트 프로필
      -> 캐릭터 Identity Reference 승인
      -> 방향별 Master Pose 승인
      -> 동작별 Pose와 Frame 후보 생성
      -> 프레임별 선택 또는 재생성
      -> 88x88 공통 캔버스 정규화
      -> 동작, 방향, 루프 QA
      -> 사용자 시각 승인
      -> Godot 경로 그대로 ZIP

### 1. 프로젝트 프로필

dungeon-cleanup-inc/actor-v1 같은 versioned profile을 단일 진실 공급원으로 둔다.

프로필이 가져야 할 항목:

- canvas: 88x88 RGBA
- root와 contact baseline
- 실루엣 목표 높이와 여백
- 방향 slug와 순서
- action별 폴더명
- action별 frame count
- FPS와 loop 여부
- 파일명 형식 frame_%03d.png
- palette와 outline 규칙
- 미러 허용 정책
- export root

### 2. Identity Reference 승인

컨셉 이미지와 production sprite reference를 구분한다.

한 캐릭터에 대해 승인된 기준 이미지를 고정하고 다음을 추적한다.

- 얼굴과 종족
- 체형과 비율
- 의상
- 장비와 부착 위치
- 팔레트
- outline 두께
- pixel density
- 카메라 각도

### 3. 방향별 Master Pose

한 번에 8방향 시트를 생성하지 않는다. 방향별 후보를 만들고 승인한다.

미러는 profile이 허용한 방향쌍만 사용하며 mirror provenance를 기록한다.

### 4. 동작과 프레임 생성

전체 시트 한 장 생성을 기본값으로 사용하지 않는다.

각 프레임 생성은 최소한 다음을 참조한다.

- identity reference
- 해당 방향 master pose
- action pose beat
- 이전 또는 인접 프레임
- 고정 88x88 root/contact guide

모델은 후보를 생성하고, 애플리케이션은 후보를 프레임 단위로 비교, 재시도, 선택할 수 있어야 한다.

### 5. 결정적 정규화

- 직접 alpha 출력을 우선 사용
- 필요할 때만 reference palette에 없는 key color 사용
- 전역 색상 삭제 금지
- border-connected flood fill만 사용
- bbox마다 독립 중앙 정렬 금지
- 고정 root/contact로 88x88 canvas에 배치
- nearest-neighbor pixel quantization
- palette와 outline 검사
- 프레임 alpha가 캔버스 경계에 닿으면 실패

### 6. QA와 승인

Deterministic QA:

- 정확한 방향, 액션, 프레임 수
- 정확한 88x88 RGBA
- 고정 root/contact
- scale과 bbox 변화 한계
- alpha containment
- palette drift
- 동일 프레임 반복
- loop closing transition
- walk support alternation
- idle motion 범위
- attack anticipation, strike, recovery 변화량

Semantic 또는 visual QA:

- 같은 캐릭터인가
- 요청한 방향으로 보이는가
- 요청한 동작으로 읽히는가
- 장비와 손이 유지되는가
- loop가 튀지 않는가

생성 성공, QA 통과, 사용자 승인은 서로 다른 상태여야 한다.

권장 상태:

    Draft -> Generated Candidates -> Deterministic QA
      -> Visual Review -> Approved -> Normalized -> Packaged

자동 adopt는 제거하고 승인된 결과만 캔버스, 라이브러리, export 대상으로 허용한다.

### 7. 게임 경로 전용 내보내기

현재 Actor ZIP의 frames/S/walk-000.png 형식은 소비 게임과 맞지 않는다.

목표 구조:

    animations/
      Breathing_Idle/
        south/
          frame_000.png
          frame_001.png
      Walking/
        south/
          frame_000.png

manifest에는 다음을 포함한다.

- project profile version
- model과 provider
- reference digest
- prompt와 negative
- action, direction, frame index
- FPS와 loop
- pivot, root, contact
- mirror provenance
- QA 결과
- 사용자 승인 digest
- 파일 hash

## Attack은 소비 게임 계약도 함께 추가해야 한다

현재 /Users/kimtajo/git/dungeon-cleanup-inc/scripts/BattleTest.gd:4는 전투에서 rotations/south.png 정적 이미지를 사용한다.

/Users/kimtajo/git/dungeon-cleanup-inc/docs/09_REMAINING_WORK_AND_PROJECT_MEMORY.md:172-183에도 다음이 명시되어 있다.

- 사무실과 던전: 8방향 idle, walk
- 전투: 정적인 남쪽 방향 이미지
- 전투 방향, 포즈, 피격, 방어, 스킬 애니메이션 없음

따라서 Asset Studio가 attack 이미지를 잘 생성해도 현재 게임은 이를 재생할 계약과 코드가 없다.

초기 액션 계약 제안이며 아직 확정값은 아니다.

| Action | 초기 제안 |
| --- | --- |
| Idle | 기존 4프레임, 4 FPS, loop |
| Walk | 기존 6프레임, 8 FPS, loop |
| Attack | 6프레임, 10~12 FPS, non-loop |
| Hurt | 3프레임, non-loop |
| Defend | 진입 프레임과 hold pose |
| Skill | 6프레임, non-loop |
| Death | collapse 시퀀스, 마지막 프레임 hold |

정확한 프레임 수, 방향 정책, hit event frame은 게임 playback 코드와 함께 확정해야 한다. 그 전에는 생성된 attack을 game-ready asset으로 표시하면 안 된다.

## 유지할 코드

### 유지 가치가 높은 부분

- src/main.js:144-280 AssetResult 저장과 JSON-safe 검증
- src/main.js:288-354 이미지 preflight, transactional adoption rollback, history
- Fabric.js 레이어 편집과 수동 보정
- server.py:2226-2305 마스크 결과를 로컬에서 제한 합성하는 영역 편집 패턴
- PNG encode, ZIP build, CRC, SHA, inventory 유틸
- Effect, Tile, UI, Actor의 결정적 geometry와 budget 검사
- 프로젝트 저장과 히스토리

특히 모델은 후보를 만들고 로컬 코드가 적용 경계를 강제한다는 마스크 편집 패턴은 새 생산 파이프라인에도 유지할 가치가 있다.

## 삭제, 통합, 격리 후보

### 연결하거나 삭제해야 하는 코드

- HTML에 존재하지 않는 aiPrompt 호환 경로
- 런타임에서 호출되지 않는 클라이언트 buildAssetFamilyPrompt
- 테스트에서만 호출되는 server build_sprite_action_prompt
- 생성 API와 연결되지 않은 route_family_qa
- adoptResult와 연결되지 않은 resultWalkQaGate
- 실제 결과와 연결되지 않은 actorFramesFromImageData
- objectFamilyMetadata 할당 없는 Object export

### 교체해야 하는 코드

- generateFrontIdleFromSelected
- runPixelWorkflow
- 8dir idle 전용 5-source+mirror 전역 전략
- 모델 한 장 결과를 production sheet로 간주하는 경로
- global chroma 기본값
- 서버 성공 즉시 자동 adopt

### UI에서 제거하거나 Lab으로 옮길 항목

- 숨겨진 레거시 pixel controls
- 중복 생성 버튼
- Synthetic 4dir/walk Actor preview
- 실제 게임 계약이 없는 Tile topology와 Object multi-state production controls
- 서로 다른 subtype 목록을 사용하는 UI와 export facade

정적 DOM 집계상 index.html에는 ID 421개와 button, input, select, textarea, canvas 계열 control 328개가 있다. production 핵심 흐름과 실험용 계약 UI가 한 화면에 혼재한다.

권장 UI 분리:

- Production
  - 프로젝트 프로필
  - Actor
  - UI Component
  - Effect
  - Candidates와 Approval
  - Game Export
- Lab 또는 Manual Editor
  - 범용 이미지 생성
  - 캔버스 편집
  - Tile 실험
  - Object 실험
  - 상세 contract JSON

### 일회성 스크립트

특정 고블린과 액션을 한 번 생성하는 scripts/generate_*_once.py 파일은 production 코드로 유지하면 안 된다.

중첩 복제 경로도 존재한다.

- asset-studio-local/asset-studio-local/scripts/generate_bottom_right_goblin_walk4_true_lr_once.py
- asset-studio-local/scripts/generate_bottom_right_goblin_walk4_once.py

바로 삭제하기보다 실패 사례, prompt, 기대 결과를 regression fixture로 추출한 뒤 archive 또는 제거한다.

### 테스트 정리

테스트 파일은 76개다.

- 55개가 src/main.js를 읽음
- 42개가 index.html을 읽음
- 21개가 Node snippet을 실행
- 22개가 server를 import
- 실제 HTTP 서버 수준 테스트는 2개

정적 문자열과 함수 존재 여부 테스트가 많아 각 기능이 실제 생성, QA, 채택, export로 연결되는지 보장하지 못한다.

필요한 통합 테스트:

- UI 선택 -> canonical payload
- payload -> server normalize
- normalize -> provider request
- provider artifact -> postprocess
- postprocess -> QA
- QA fail -> adopt 차단
- approved artifact -> exact Godot package
- package -> dungeon-cleanup-inc loader

## 전체 이미지 계열별 우선순위

### 1순위: Actor Sprite

현재 게임에서 직접 사용 중이고 가장 큰 실패가 확인된 영역이다.

- 프로젝트 profile
- identity와 direction master
- idle와 walk 재구축
- attack 계약과 game loader 연결
- 88x88 exact export

### 2순위: UI Component States

현재 게임에서 black brass plate, contract card, item slot을 실제 사용한다.

- 공통 canvas
- text-free
- alpha
- 9-slice
- state alignment
- exact Godot path

### 3순위: Effect

전투와 상호작용 기능이 굳은 뒤 action event와 함께 계약한다.

- frame envelope
- pivot
- source event frame
- one-shot 또는 loop
- full-cell export

### 4순위: Object

게임에서 실제 placement, collision, states가 확정된 유형부터 추가한다.

### 보류: Tile

소비 게임에서 TileSet 또는 atlas importer 계약이 확정되기 전에는 한 장의 모델 이미지에 정확한 topology를 기대하면 안 된다.

/Users/kimtajo/git/dungeon-cleanup-inc/docs/work_packages/06_visual_assets_and_code_cleanup.md:10-35도 기능이 굳은 뒤 비주얼 자산을 진행하고, 기능 확정 전 대량 생성을 제외한다고 명시한다.

## 권장 실행 우선순위

1. dungeon-cleanup-inc 프로젝트 프로필과 공통 계약 스키마 확정
2. Provider adapter와 시작 시 health check
3. 자동 채택 제거와 Candidate, QA, Approval 상태 모델
4. 스프라이트 생성기를 프레임과 포즈 기반으로 전면 교체
5. 88x88 anchor, palette, alpha 정규화
6. Godot 경로 전용 export와 소비 게임 loader 테스트
7. 게임 전투 action 계약과 playback 추가
8. UI 상태 공통 캔버스 생성 파이프라인
9. Effect와 Object를 실제 소비 계약 순서대로 추가
10. Tile은 소비 게임 계약 전까지 Lab으로 유지

## 검증 상태와 한계

- 브라우저와 Chrome 실행 안 함
- 서버 실행 안 함
- 제품 소스 수정 안 함
- node --check src/main.js 통과
- python3 -m py_compile server.py 통과
- 현재 Asset Studio assets 디렉터리가 비어 있어 기존 생성 결과의 주관적 화질 비교는 수행하지 못함
- 대신 소비 게임의 실제 88개 캐릭터 PNG를 메타데이터와 픽셀 단위로 검사함
- 현재 환경에 pytest가 설치되어 있지 않고 requirements.txt에도 없어 전체 pytest 실행은 불가능

## 최종 판단

현재 문제는 프롬프트 몇 줄을 보강하는 수준으로 해결되지 않는다.

교체 대상은 저장소 전체가 아니라 production image orchestration이다.

- 프로젝트 계약
- 생성 job
- provider
- 프레임 후보
- 결정적 정규화
- QA
- 사용자 승인
- 게임 전용 package

이 일곱 단계를 하나의 연결된 파이프라인으로 다시 만들고, 캔버스 편집과 저수준 이미지 유틸은 그 위에 재사용하는 방향이 가장 타당하다.
