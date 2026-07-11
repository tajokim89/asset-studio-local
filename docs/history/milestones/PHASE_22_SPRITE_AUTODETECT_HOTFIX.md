# Phase 22 Hotfix — Sprite Auto Detect / Grid Preview Geometry

## 문제

사용자가 `자동 조각 찾기`를 실행하면 4프레임 스프라이트 시트에서 조각 박스가 프레임 단위로 잡히지 않고, 큰 덩어리/부분 조각처럼 보이는 문제가 있었다.

## 원인

- 자동 탐지가 선택 이미지의 로컬 좌표가 아니라 전체 캔버스 기준 PNG를 분석했다.
- 선택 이미지가 캔버스 원점이 아닌 위치에 있을 때 slice 좌표와 guide/render/export 좌표가 섞였다.
- 잔여 배경/노이즈가 있으면 connected-component 탐지가 프레임이 아니라 배경 덩어리 또는 몸/무기 부분 조각을 잡았다.
- 자동 탐지 후 guide가 active object가 되면 이후 preview/export가 원본 이미지 레이어를 잃을 수 있었다.

## 수정

- `spriteSourceLayerId`를 저장해서 guide 선택 후에도 원본 이미지 레이어를 유지.
- 자동 탐지는 선택 이미지의 로컬 픽셀에서 수행하도록 변경.
  - slice `x/y`는 선택 이미지 기준 상대좌표.
  - guide 표시/export/crop 시에만 이미지의 캔버스 위치를 더함.
- 자동 탐지 결과가 현재 설정된 프레임 그리드와 맞지 않으면 그리드 프레임으로 fallback.
  - 예: 4×1 시트에서 component가 8개로 쪼개지면 4개 프레임 박스로 자동 전환.
  - 큰 배경 덩어리 1개로 감지되어도 4×1 프레임 박스로 자동 전환.
- 애니메이션 preview는 현재 grid slice를 그대로 사용하도록 유지.

## 검증

### 브라우저 실제 UI 경로

테스트 fixture:

- 이미지 레이어 위치: `left=300`, `top=220`
- 이미지 크기: `560×199`
- 그리드: `4×1`
- 기대 셀: `140×199`

`자동 조각 찾기` 실행 결과:

```txt
프레임 수 불일치 감지(8개 탐지) → 현재 그리드 4×1 기준 4개 프레임으로 분할
```

생성 guide:

```json
[
  {"left":300,"top":220,"width":140,"height":199},
  {"left":440,"top":220,"width":140,"height":199},
  {"left":580,"top":220,"width":140,"height":199},
  {"left":720,"top":220,"width":140,"height":199}
]
```

`애니메이션 재생` 결과:

```txt
frameCount=4
stripImgs=4
firstFrameSize=140×199
stageText=3/4 · loop
firstFrame pixel(50,60)=rgba(139,90,43,255)
console JS errors=0
```

### Static / syntax

```txt
pytest tests/test_phase12_sprite_extract_static.py tests/test_phase14_animation_preview_static.py -q
13 passed

python3 -m py_compile server.py
node --check src/main.js
git diff --check
passed
```

### Full suite 참고

```txt
pytest -q
118 passed, 11 failed, 8 warnings
```

11개 실패는 이번 hotfix 범위 밖의 기존 stale static-token 테스트들이다. 이번 수정 대상인 sprite extract / animation preview subset은 통과했다.
