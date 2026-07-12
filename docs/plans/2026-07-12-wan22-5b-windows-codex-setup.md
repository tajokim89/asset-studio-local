# Windows Codex용 Wan 2.2 5B 로컬 I2V 설치·검증 지시서

이 문서를 Windows PC의 Codex에 전달한다. Codex는 별도 확인 질문 없이 설치, 서버 기동, API 확인, 1회 저비용 스모크 테스트까지 수행한다.

## 목표

- RTX 5070 Ti 16GB에서 ComfyUI로 `Wan2.2-TI2V-5B` 이미지→영상(I2V)을 로컬 실행한다.
- API나 유료 서비스를 사용하지 않는다.
- 최종 스프라이트 크기와 생성 작업 해상도를 구분한다.
- 최초 검증은 384×384의 짧은 걷기 영상으로 수행한다.
- 기존 ComfyUI 모델, 커스텀 노드, 입력·출력 파일을 보존한다.

## 핵심 결정

- 5B diffusion 모델은 양자화하지 않고 공식 FP16을 사용한다.
- ComfyUI 공식 문서상 5B FP16은 네이티브 오프로딩을 사용하면 8GB VRAM에서도 실행 가능하다.
- 텍스트 인코더만 공식 FP8 파일을 사용한다.
- 5B 결과가 나쁘더라도 이 단계에서 프롬프트 재생성을 반복하지 않는다. 그 경우 후속 작업으로 `Wan2.2 I2V 14B Q4 GGUF`를 검토한다.
- SCAIL-2, ControlNet, OpenPose, 새 커스텀 노드는 이번 작업 범위가 아니다.

공식 참고 자료:

- <https://docs.comfy.org/tutorials/video/wan/wan2_2>
- <https://raw.githubusercontent.com/Comfy-Org/workflow_templates/refs/heads/main/templates/video_wan2_2_5B_ti2v.json>

## 예상 환경

- GPU: NVIDIA RTX 5070 Ti 16GB
- 기존 ComfyUI 후보 경로: `C:\comfyui\ComfyUI`
- Embedded Python 후보 경로: `C:\comfyui\python_embeded\python.exe`
- 서버 후보 주소: `http://100.117.202.14:8188`

실제 경로가 다르면 Codex가 아래 순서로 찾고 발견한 경로를 이후 명령에 사용한다.

```powershell
$candidates = @(
  "C:\comfyui\ComfyUI",
  "C:\ComfyUI_windows_portable\ComfyUI",
  "$env:USERPROFILE\ComfyUI"
)
$ComfyRoot = $candidates | Where-Object { Test-Path "$_\main.py" } | Select-Object -First 1
if (-not $ComfyRoot) { throw "ComfyUI main.py를 찾지 못했습니다." }
$ComfyRoot
```

## 1. 기존 설치 보존 및 상태 기록

서버 프로세스를 정상 종료한 후 상태를 기록한다.

```powershell
Set-Location $ComfyRoot
git status --short
git remote -v
git describe --tags --always
nvidia-smi
```

규칙:

- `models`, `custom_nodes`, `input`, `output`, `user`를 삭제하지 않는다.
- `git reset --hard`, `git clean`, 전체 폴더 재설치를 사용하지 않는다.
- 사용자 변경이 있으면 건드리지 말고 상태만 보고한다.
- ComfyUI가 너무 오래되어 공식 Wan 노드가 없다면 안전한 업데이트만 수행한다.

## 2. 필요한 코어 노드 확인

서버가 실행 중이면 다음 API를 확인한다.

```powershell
$BaseUrl = "http://127.0.0.1:8188"
Invoke-RestMethod "$BaseUrl/object_info/UNETLoader"
Invoke-RestMethod "$BaseUrl/object_info/Wan22ImageToVideoLatent"
Invoke-RestMethod "$BaseUrl/object_info/CreateVideo"
Invoke-RestMethod "$BaseUrl/object_info/SaveVideo"
```

네 노드가 모두 반환되면 업데이트를 생략한다. 하나라도 없을 때만 기존 변경을 보존한 상태에서 ComfyUI 공식 업데이트 절차를 사용하고 `requirements.txt`를 현재 Python 환경에 설치한다. 전체 커스텀 노드 일괄 업데이트는 하지 않는다.

## 3. 공식 모델 다운로드

필요 디렉터리를 만든다.

```powershell
$ModelRoot = Join-Path $ComfyRoot "models"
New-Item -ItemType Directory -Force `
  (Join-Path $ModelRoot "diffusion_models"), `
  (Join-Path $ModelRoot "text_encoders"), `
  (Join-Path $ModelRoot "vae") | Out-Null
```

다음 세 파일만 설치한다.

| 파일 | 저장 위치 | 예상 크기 |
|---|---|---:|
| `wan2.2_ti2v_5B_fp16.safetensors` | `models\diffusion_models` | 9,999,658,848 bytes |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `models\text_encoders` | 6,735,906,897 bytes |
| `wan2.2_vae.safetensors` | `models\vae` | 1,409,400,960 bytes |

중단 재개가 가능한 `curl.exe -C -`를 사용한다.

```powershell
$Diffusion = Join-Path $ModelRoot "diffusion_models\wan2.2_ti2v_5B_fp16.safetensors"
$TextEncoder = Join-Path $ModelRoot "text_encoders\umt5_xxl_fp8_e4m3fn_scaled.safetensors"
$Vae = Join-Path $ModelRoot "vae\wan2.2_vae.safetensors"

curl.exe -L --fail --retry 5 --retry-all-errors -C - -o $Diffusion "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors"
curl.exe -L --fail --retry 5 --retry-all-errors -C - -o $TextEncoder "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"
curl.exe -L --fail --retry 5 --retry-all-errors -C - -o $Vae "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan2.2_vae.safetensors"
```

기존 파일의 크기가 예상값과 같으면 다시 받지 않는다. 크기가 다르면 즉시 삭제하지 말고 `.partial-or-invalid`로 이름을 변경한 뒤 다시 받는다.

```powershell
Get-Item $Diffusion, $TextEncoder, $Vae | Select-Object FullName, Length
```

## 4. 공식 워크플로 설치

공식 JSON을 별도 작업 폴더에 저장한다.

```powershell
$WorkflowDir = Join-Path $ComfyRoot "user\default\workflows"
New-Item -ItemType Directory -Force $WorkflowDir | Out-Null
$WorkflowPath = Join-Path $WorkflowDir "wan2.2_5b_i2v_sprite_smoke.json"
curl.exe -L --fail --retry 5 -o $WorkflowPath "https://raw.githubusercontent.com/Comfy-Org/workflow_templates/refs/heads/main/templates/video_wan2_2_5B_ti2v.json"
```

워크플로에서 다음 모델명이 선택됐는지 확인한다.

- UNET: `wan2.2_ti2v_5B_fp16.safetensors`
- CLIP: `umt5_xxl_fp8_e4m3fn_scaled.safetensors`, type `wan`
- VAE: `wan2.2_vae.safetensors`
- I2V 노드: `Wan22ImageToVideoLatent`

## 5. 서버 기동과 모델 인식 검증

기존에 사용하던 실행 스크립트와 옵션을 우선 사용한다. 직접 실행해야 한다면 실제 embedded Python 경로를 찾아 다음 형태로 실행한다.

```powershell
& $PythonExe -s (Join-Path $ComfyRoot "main.py") --windows-standalone-build --listen 0.0.0.0 --port 8188
```

서버 시작 후 확인한다.

```powershell
Invoke-RestMethod "$BaseUrl/system_stats"
Invoke-RestMethod "$BaseUrl/models/diffusion_models"
Invoke-RestMethod "$BaseUrl/models/text_encoders"
Invoke-RestMethod "$BaseUrl/models/vae"
Invoke-RestMethod "$BaseUrl/object_info/Wan22ImageToVideoLatent"
```

세 모델명과 `Wan22ImageToVideoLatent`가 응답에 존재해야 한다.

## 6. 1회 I2V 스모크 테스트

목표는 화질 평가가 아니라 다음 네 가지를 확인하는 것이다.

1. 모델이 OOM 없이 로드되는가
2. 입력 이미지가 실제 영상 생성에 사용되는가
3. 결과 프레임에 움직임이 존재하는가
4. ComfyUI API 작업이 정상 완료되는가

설정:

- 입력: 단일 캐릭터 전신 이미지 한 장
- 작업 해상도: `384×384`
- 길이: 공식 노드가 허용하는 가장 짧은 유효 길이부터 시작
- FPS: 16 또는 워크플로 기본값
- 카메라: 고정
- 배경: 단색
- 생성 횟수: 정확히 1회
- seed: 기록 가능한 고정값

긍정 프롬프트:

```text
Full-body side-view game character performing one simple walk cycle in place. Fixed orthographic camera. The character alternates the legs with clear left-right foot crossing and naturally counter-swings both arms. Preserve the exact face, hair, skin color, clothing, armor, weapon and body proportions from the input image. Constant scale and position. Solid plain background. No camera motion.
```

부정 프롬프트:

```text
camera movement, zoom, rotation, perspective change, moving forward across the frame, sliding feet, frozen legs, synchronized arms and legs, extra limbs, missing limbs, fused hands, fused feet, changing face, changing clothes, changing weapon, changing body proportions, morphing, duplicate character, text, watermark
```

OOM이면 재시도 전에 다음 순서로 한 항목씩만 낮춘다.

1. 다른 작업과 브라우저 GPU 가속을 종료한다.
2. 해상도를 320×320으로 낮춘다.
3. 프레임 길이를 한 단계 낮춘다.
4. ComfyUI 네이티브 model offloading 설정을 확인한다.

256×256은 최종 비상 스모크 테스트 외에는 사용하지 않는다. 손발과 얼굴 판별력이 크게 떨어질 수 있기 때문이다.

## 7. 스모크 테스트 판정

통과 조건:

- ComfyUI 작업 상태가 성공이다.
- 출력 영상 또는 프레임 시퀀스가 생성됐다.
- OOM 및 CUDA 오류가 없다.
- 입력 캐릭터가 첫 프레임에 반영됐다.
- 정지 이미지 복제가 아니라 프레임 간 움직임이 존재한다.

이번 단계의 실패로 보지 않는 항목:

- 손발이 완벽하지 않음
- 정확한 4프레임 걷기 주기가 아직 아님
- 픽셀 아트 변환이 안 됨
- 배경 제거 및 스프라이트 정렬이 안 됨

이는 설치 검증 이후 Asset Studio 연동 단계에서 평가한다.

## 중단 조건

다음 상황에서는 추가 다운로드나 임의 모델 설치를 중단하고 증거와 함께 보고한다.

- 기존 ComfyUI 사용자 변경과 업데이트가 충돌함
- 디스크 여유 공간이 세 파일과 임시 다운로드를 감당하지 못함
- 다운로드 파일 크기가 재시도 후에도 예상값과 다름
- 최신 ComfyUI에서도 `Wan22ImageToVideoLatent`가 없음
- 동일한 OOM/CUDA 오류가 설정 축소 후에도 반복됨

## 완료 보고 형식

Windows Codex는 아래 항목만 간결하게 보고한다.

1. 실제 ComfyUI 및 Python 경로
2. ComfyUI 버전과 Git 상태
3. GPU 이름, VRAM, 드라이버, PyTorch/CUDA 버전
4. 설치한 세 모델의 실제 경로와 byte 크기
5. 필수 노드 및 모델 API 인식 결과
6. 스모크 테스트 설정, seed, 실행 시간, 최대 VRAM
7. 생성 결과 파일의 실제 경로
8. 발생한 오류와 남은 제한
9. 판정: `SETUP_PASS`, `SETUP_PARTIAL`, `SETUP_FAIL`

## 후속 단계 — 이번에는 수행하지 않음

5B 설치 검증이 통과한 뒤 별도 작업으로 진행한다.

1. 검은색 근육질 오크 입력 이미지로 384×384 걷기 루프 생성
2. 영상에서 contact/down/pass/up 핵심 4프레임 추출
3. 머리 기준점 고정, 최대 너비·높이 공통 캔버스 정렬
4. 발 교차, 팔 반대 스윙, 외형 유지 QA
5. 5B가 반복 실패할 경우 `Wan2.2 I2V 14B Q4 GGUF` 비교 테스트
6. 검증된 ComfyUI workflow를 Asset Studio backend에서 API 호출
