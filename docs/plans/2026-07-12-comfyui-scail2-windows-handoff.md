# Windows ComfyUI SCAIL-2 설치 작업 지시서

이 문서를 Windows PC의 Codex에 전달하고, 아래 작업을 순서대로 수행시킨다.

## 목표

- 기존 ComfyUI 데이터와 커스텀 노드를 보존한다.
- ComfyUI를 `v0.27.1` 이상으로 업데이트한다.
- `WanSCAILToVideo`, `SCAIL2ColoredMask` 코어 노드를 활성화한다.
- RTX 5070 Ti 16GB용 SCAIL-2 모델을 설치한다.
- 이미지 생성은 하지 않고 노드 및 모델 인식까지만 검증한다.

## 현재 상태

- ComfyUI 경로: `C:\comfyui\ComfyUI`
- 서버: `http://100.117.202.14:8188`
- 현재 버전: `v0.11.1`
- Python: `3.13.11` embedded
- PyTorch: `2.10.0+cu130`
- GPU: RTX 5070 Ti 16GB
- ComfyUI Manager: `V3.39.2`
- 기존 `WanAnimateToVideo`는 있으나 SCAIL-2 노드는 없음
- Manager 스냅샷: `2026-07-12_14-56-28_snapshot`
- Manager 자동 업데이트는 로컬 `master` 브랜치가 없어서 중단됐으며 실제 변경은 없었음

## 1. 업데이트 전 보존

ComfyUI 서버를 종료한 다음 아래를 확인한다.

```powershell
cd C:\comfyui\ComfyUI
git status --short
git remote -v
git branch -a
git tag --points-at HEAD
```

- 사용자 변경 파일이 있으면 별도 폴더에 복사한다.
- `models`, `custom_nodes`, `input`, `output`, `user`를 삭제하거나 초기화하지 않는다.
- `git reset --hard`, `git clean`, 전체 재설치는 사용하지 않는다.

## 2. ComfyUI 코어 업데이트

`v0.27.1`에는 필요한 SCAIL-2 노드가 포함돼 있다.

```powershell
cd C:\comfyui\ComfyUI
git fetch --tags origin
git checkout --detach v0.27.1
C:\comfyui\python_embeded\python.exe -s -m pip install -r requirements.txt
```

기존 실행 옵션을 유지해 서버를 다시 실행한다.

```powershell
C:\comfyui\python_embeded\python.exe -s C:\comfyui\ComfyUI\main.py --windows-standalone-build --listen 100.117.202.14 --port 8188
```

전체 커스텀 노드 업데이트는 하지 않는다. 업데이트 후 특정 노드만 실패하면 해당 노드만 처리한다.

## 3. 코어 노드 검증

다음 주소가 `{}`가 아닌 노드 정의를 반환해야 한다.

```powershell
Invoke-RestMethod http://100.117.202.14:8188/object_info/WanSCAILToVideo
Invoke-RestMethod http://100.117.202.14:8188/object_info/SCAIL2ColoredMask
```

로그에서 ComfyUI 코어 로딩 실패가 없는지 확인한다.

```powershell
Invoke-RestMethod http://100.117.202.14:8188/internal/logs
```

기존 `argostranslate` 및 `opencv-contrib-python` 경고는 이번 작업 이전부터 있던 별도 문제다.

## 4. SCAIL-2 모델 설치

다음 디렉터리를 만든다.

```powershell
$root = "C:\comfyui\ComfyUI\models"
New-Item -ItemType Directory -Force "$root\diffusion_models", "$root\text_encoders", "$root\vae", "$root\clip_vision", "$root\checkpoints\sam3" | Out-Null
```

다음 파일을 `curl.exe -L --retry 5 --retry-all-errors -C -`로 다운로드한다.

| 파일 | 저장 위치 | URL |
|---|---|---|
| `wan2.1_14B_SCAIL_2_nvfp4_mxpf8_mix.safetensors` | `models\diffusion_models` | `https://huggingface.co/Comfy-Org/SCAIL-2/resolve/main/diffusion_models/wan2.1_14B_SCAIL_2_nvfp4_mxpf8_mix.safetensors` |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `models\text_encoders` | `https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors` |
| `wan_2.1_vae.safetensors` | `models\vae` | `https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors` |
| `clip_vision_h.safetensors` | `models\clip_vision` | `https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors` |
| `sam3.1_multiplex_fp16.safetensors` | `models\checkpoints\sam3` | `https://huggingface.co/Comfy-Org/sam3.1/resolve/main/checkpoints/sam3.1_multiplex_fp16.safetensors` |

예시:

```powershell
curl.exe -L --retry 5 --retry-all-errors -C - -o "$root\diffusion_models\wan2.1_14B_SCAIL_2_nvfp4_mxpf8_mix.safetensors" "https://huggingface.co/Comfy-Org/SCAIL-2/resolve/main/diffusion_models/wan2.1_14B_SCAIL_2_nvfp4_mxpf8_mix.safetensors"
```

나머지 파일도 같은 방식으로 각 저장 위치에 받는다. 다운로드가 중단되면 동일 명령을 다시 실행해 이어받는다.

## 5. 모델 인식 검증

서버 재시작 후 다음 API 결과에 설치 파일명이 보여야 한다.

```powershell
Invoke-RestMethod http://100.117.202.14:8188/models/diffusion_models
Invoke-RestMethod http://100.117.202.14:8188/models/text_encoders
Invoke-RestMethod http://100.117.202.14:8188/models/vae
Invoke-RestMethod http://100.117.202.14:8188/models/clip_vision
Invoke-RestMethod http://100.117.202.14:8188/models/checkpoints
```

## 완료 보고 형식

Windows Codex는 작업 후 다음만 보고한다.

1. 업데이트 전후 ComfyUI 버전
2. `WanSCAILToVideo`, `SCAIL2ColoredMask` 인식 여부
3. 설치된 다섯 모델의 실제 경로와 파일 크기
4. 서버 재시작 및 API 응답 여부
5. 새로 발생한 오류 로그

## 실패 시 복구

업데이트 후 서버가 시작되지 않으면 다음 순서로 복구한다.

```powershell
cd C:\comfyui\ComfyUI
git checkout --detach v0.11.1
C:\comfyui\python_embeded\python.exe -s -m pip install -r requirements.txt
```

필요하면 Manager의 `2026-07-12_14-56-28_snapshot`을 복원한다. 사용자 모델과 결과물은 삭제하지 않는다.
