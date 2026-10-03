"""Local ComfyUI pipeline for turning one 3D animation view into pixel frames.

The browser owns GLB playback and rendering.  This module receives a 4x2 guide
sheet plus an optional 2D identity reference, runs the reviewed local ComfyUI
workflows, and normalizes the result into a game-ready atlas.  It deliberately
does not depend on Hermes or a hosted GPT/image provider.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import os
import shutil
import statistics
import time
import urllib.error
import urllib.request
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path


DEFAULT_COMFY_URL = "http://127.0.0.1:8188"
DEFAULT_COMFY_ROOT = Path(r"C:\ComfyUI\ComfyUI")
REQUIRED_COMFY_NODES = frozenset(
    {
        "LoadImage",
        "SaveImage",
        "DWPreprocessor",
        "DownloadAndLoadDepthAnythingV3Model",
        "DepthAnything_V3",
        "UnetLoaderGGUF",
        "LoraLoaderModelOnly",
        "ModelSamplingAuraFlow",
        "CLIPLoader",
        "VAELoader",
        "TextEncodeQwenImageEditPlus",
        "ReferenceLatent",
        "KSampler",
        "BiRefNetRMBG",
    }
)
SUPPORTED_ACTIONS = frozenset({"idle", "walk", "run"})
SUPPORTED_DIRECTIONS = frozenset({"N", "NE", "E", "SE", "S", "SW", "W", "NW"})
SUPPORTED_RESOLUTIONS = frozenset({48, 64, 96})
SUPPORTED_PALETTES = frozenset({16, 24, 32})
SUPPORTED_STYLES = frozenset({"32-bit refined RPG", "16-bit classic RPG", "Dark fantasy"})


@dataclass(frozen=True)
class ComfyPaths:
    root: Path
    input: Path
    output: Path


def comfy_paths(root: str | Path | None = None) -> ComfyPaths:
    configured = root or os.environ.get("ASSET_STUDIO_COMFY_ROOT") or DEFAULT_COMFY_ROOT
    resolved = Path(configured).expanduser().resolve()
    return ComfyPaths(root=resolved, input=resolved / "input", output=resolved / "output")


def _request_json(url: str, payload: dict | None = None, *, timeout: int = 60) -> dict:
    encoded = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="GET" if encoded is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ComfyUI HTTP {exc.code}: {detail[:800]}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"ComfyUI에 연결할 수 없습니다: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError("ComfyUI가 올바르지 않은 응답을 반환했습니다.")
    return result


class ComfyClient:
    def __init__(
        self,
        url: str | None = None,
        *,
        root: str | Path | None = None,
        timeout_seconds: int = 900,
    ) -> None:
        self.url = (url or os.environ.get("ASSET_STUDIO_COMFY_URL") or DEFAULT_COMFY_URL).rstrip("/")
        self.paths = comfy_paths(root)
        self.timeout_seconds = max(30, int(timeout_seconds))

    def object_info(self) -> dict:
        return _request_json(f"{self.url}/object_info", timeout=20)

    def run(self, prompt: dict) -> dict:
        queued = _request_json(
            f"{self.url}/prompt",
            {"prompt": prompt, "client_id": str(uuid.uuid4())},
            timeout=60,
        )
        if queued.get("error"):
            raise RuntimeError(json.dumps(queued, ensure_ascii=False)[:1200])
        prompt_id = queued.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise RuntimeError("ComfyUI 작업 ID를 받지 못했습니다.")
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            history = _request_json(f"{self.url}/history/{prompt_id}", timeout=30)
            record = history.get(prompt_id)
            if isinstance(record, dict):
                status = record.get("status") if isinstance(record.get("status"), dict) else {}
                if status.get("status_str") == "error":
                    messages = status.get("messages") or []
                    raise RuntimeError(f"ComfyUI 작업이 실패했습니다: {json.dumps(messages, ensure_ascii=False)[-1600:]}")
                if status.get("completed") or status.get("status_str") == "success":
                    return record
            time.sleep(1.0)
        raise TimeoutError(f"ComfyUI 작업이 {self.timeout_seconds}초를 초과했습니다.")

    def output_path(self, record: dict, node_id: str) -> Path:
        outputs = record.get("outputs") if isinstance(record.get("outputs"), dict) else {}
        node = outputs.get(str(node_id)) if isinstance(outputs, dict) else None
        images = node.get("images") if isinstance(node, dict) else None
        if not isinstance(images, list) or not images:
            raise RuntimeError(f"ComfyUI 노드 {node_id}의 이미지 결과가 없습니다.")
        image = images[0]
        if not isinstance(image, dict) or image.get("type") != "output":
            raise RuntimeError(f"ComfyUI 노드 {node_id}의 출력 형식이 올바르지 않습니다.")
        filename = str(image.get("filename") or "")
        subfolder = str(image.get("subfolder") or "")
        relative = Path(subfolder) / filename
        if not filename or relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("ComfyUI 출력 경로가 안전하지 않습니다.")
        resolved = (self.paths.output / relative).resolve()
        try:
            resolved.relative_to(self.paths.output.resolve())
        except ValueError as exc:
            raise RuntimeError("ComfyUI 출력 경로가 output 폴더 밖을 가리킵니다.") from exc
        if not resolved.is_file():
            raise RuntimeError(f"ComfyUI 출력 파일을 찾을 수 없습니다: {relative.as_posix()}")
        return resolved


def local_3d_pipeline_health(*, client: ComfyClient | None = None) -> dict:
    client = client or ComfyClient()
    try:
        info = client.object_info()
        missing = sorted(REQUIRED_COMFY_NODES.difference(info))
        paths_ready = client.paths.input.is_dir() and client.paths.output.is_dir()
        available = not missing and paths_ready
        return {
            "available": available,
            "provider": "local-comfyui",
            "display_name": "로컬 ComfyUI · Qwen Image Edit",
            "url": client.url,
            "root": str(client.paths.root),
            "missing_nodes": missing,
            "paths_ready": paths_ready,
            "codex_optional": True,
            "hermes_required": False,
            "reason": None if available else ("missing_nodes" if missing else "comfy_paths_missing"),
        }
    except Exception as exc:
        return {
            "available": False,
            "provider": "local-comfyui",
            "display_name": "로컬 ComfyUI · Qwen Image Edit",
            "url": client.url,
            "root": str(client.paths.root),
            "missing_nodes": [],
            "paths_ready": False,
            "codex_optional": True,
            "hermes_required": False,
            "reason": "comfy_unreachable",
            "error": str(exc),
        }


def _decode_image_data_url(value: object, name: str, *, byte_limit: int = 12_000_000):
    from PIL import Image

    if not isinstance(value, str) or not value.startswith("data:image/") or "," not in value:
        raise ValueError(f"{name} must be an image data URL")
    if len(value) > byte_limit * 4 // 3 + 256:
        raise ValueError(f"{name} exceeds the request budget")
    try:
        raw = base64.b64decode(value.split(",", 1)[1], validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} contains invalid base64") from exc
    if len(raw) > byte_limit:
        raise ValueError(f"{name} exceeds the request budget")
    try:
        image = Image.open(io.BytesIO(raw)).convert("RGBA")
        image.load()
    except Exception as exc:
        raise ValueError(f"{name} is not a valid image") from exc
    if image.width < 64 or image.height < 64 or image.width > 4096 or image.height > 4096:
        raise ValueError(f"{name} dimensions must be between 64 and 4096 pixels")
    return image


def normalize_local_action_payload(data: object) -> dict:
    if not isinstance(data, dict):
        raise ValueError("local 3D action payload must be an object")
    guide = _decode_image_data_url(data.get("guide_sheet"), "guide_sheet")
    if guide.width % 4 or guide.height % 2:
        raise ValueError("guide_sheet must be divisible into a 4x2 grid")
    identity_value = data.get("identity_image") or data.get("guide_sheet")
    identity = _decode_image_data_url(identity_value, "identity_image")
    action = str(data.get("action", "walk")).strip().lower()
    if action not in SUPPORTED_ACTIONS:
        raise ValueError("action must be idle, walk, or run")
    direction = str(data.get("direction", "S")).strip().upper() or "S"
    if direction not in SUPPORTED_DIRECTIONS:
        raise ValueError("direction must be one of the eight compass directions")
    style = str(data.get("style", "32-bit refined RPG")).strip()
    if style not in SUPPORTED_STYLES:
        raise ValueError("unsupported local 3D pixel style")
    try:
        resolution = int(data.get("resolution", 64))
        palette_colors = int(data.get("palette_colors", 24))
        seed = int(data.get("seed", 0))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("resolution, palette_colors, and seed must be integers") from exc
    if resolution not in SUPPORTED_RESOLUTIONS:
        raise ValueError("resolution must be 48, 64, or 96")
    if palette_colors not in SUPPORTED_PALETTES:
        raise ValueError("palette_colors must be 16, 24, or 32")
    if seed < 0 or seed > 2**63 - 1:
        raise ValueError("seed is outside the supported range")
    try:
        shape_lock = max(0, min(100, int(data.get("shape_lock", 82))))
        pixel_simplify = max(0, min(100, int(data.get("pixel_simplify", 68))))
        max_attempts = int(data.get("max_attempts", 3))
        min_qa_score = int(data.get("min_qa_score", 90))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("shape_lock, pixel_simplify, max_attempts, and min_qa_score must be integers") from exc
    strict_validation = data.get("strict_validation", True)
    if not isinstance(strict_validation, bool):
        raise ValueError("strict_validation must be a boolean")
    if max_attempts < 1 or max_attempts > 4:
        raise ValueError("max_attempts must be between 1 and 4")
    if min_qa_score < 75 or min_qa_score > 100:
        raise ValueError("min_qa_score must be between 75 and 100")
    if not strict_validation:
        max_attempts = 1
    if seed == 0:
        seed_material = guide.tobytes()[:1_000_000] + action.encode("ascii")
        seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big") & (2**63 - 1)
    return {
        "guide": guide,
        "identity": identity,
        "action": action,
        "direction": direction,
        "resolution": resolution,
        "palette_colors": palette_colors,
        "style": style,
        "shape_lock": shape_lock,
        "pixel_simplify": pixel_simplify,
        "seed": seed,
        "strict_validation": strict_validation,
        "max_attempts": max_attempts,
        "min_qa_score": min_qa_score,
    }


def build_controls_prompt(guide_name: str, output_prefix: str) -> dict:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": guide_name}},
        "2": {
            "class_type": "DWPreprocessor",
            "inputs": {
                "image": ["1", 0],
                "detect_hand": "enable",
                "detect_body": "enable",
                "detect_face": "enable",
                "resolution": 1024,
                "bbox_detector": "yolox_l.torchscript.pt",
                "pose_estimator": "dw-ll_ucoco_384.onnx",
                "scale_stick_for_xinsr_cn": "disable",
            },
        },
        "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0], "filename_prefix": f"{output_prefix}/pose"}},
        "4": {"class_type": "ImageScaleToMegapixels", "inputs": {"images": ["1", 0], "megapixels": 2.0}},
        "5": {
            "class_type": "DownloadAndLoadDepthAnythingV3Model",
            "inputs": {"model": "da3mono_large.safetensors", "precision": "auto", "attention": "sdpa"},
        },
        "6": {
            "class_type": "DepthAnything_V3",
            "inputs": {
                "da3_model": ["5", 0],
                "images": ["4", 0],
                "normalization_mode": "Standard",
                "resize_method": "resize",
                "invert_depth": False,
                "keep_model_size": False,
            },
        },
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": f"{output_prefix}/depth"}},
    }


def _identity_prompt(action: str, direction: str, style: str, shape_lock: int, pixel_simplify: int) -> str:
    action_copy = {
        "idle": "eight evenly spaced poses from one seamless idle/breathing loop",
        "walk": "eight evenly spaced poses from one seamless walk cycle",
        "run": "eight evenly spaced poses from one seamless run cycle",
    }[action]
    direction_copy = {
        "N": "a strict back view: show only the back of the head, jacket, arms, pants, and shoes; no face, eyes, eyebrows, nose, mouth, chest, or front pockets may be visible in any cell",
        "NE": "a back-right three-quarter view: the back must dominate and only a narrow right-side profile may be visible",
        "E": "a strict right-facing side profile: the nose and toes point screen-right in every cell",
        "SE": "a front-right three-quarter view: the face and chest are visible while the body points screen-right",
        "S": "a strict front view: the face, chest, and front of both legs are visible in every cell",
        "SW": "a front-left three-quarter view: the face and chest are visible while the body points screen-left",
        "W": "a strict left-facing side profile: the nose and toes point screen-left in every cell",
        "NW": "a back-left three-quarter view: the back must dominate and only a narrow left-side profile may be visible",
    }[direction]
    motion_copy = {
        "idle": "Keep the idle alive but restrained: small breathing and weight-shift changes must remain visible without changing the planted stance.",
        "walk": "Preserve the supplied UAL walk exactly, including its original arm counter-swing, hand path, elbow bend, contact poses, and timing. Do not exaggerate, damp, or redesign the motion.",
        "run": "Preserve the supplied UAL run exactly, including its original arm drive, airborne/contact phases, shoulder motion, hip motion, and timing. Do not exaggerate, damp, or redesign the motion.",
    }[action]
    return f"""Use the character in image 1 as the only identity, face, clothing, equipment, color, and proportion reference.
Redraw that exact same character in {action_copy}, following the supplied pose, depth, and 3D guide controls.
The starting 4x2 sheet already contains eight copies of the real character. Keep those complete clothes and proportions, and gently articulate those copies into the target poses instead of rebuilding a body from the mannequin.
Every character must be one clean, fully connected silhouette. Keep every face, hair shape, sleeve, hand, trouser leg, and shoe intact; there must be no green holes, rectangular seams, displaced fragments, or sliced facial features inside the character.
This is appearance transfer only: copy the face, hair, skin, clothing, patches, pockets, cuffs, pants, and shoes from image 1 onto the supplied body without changing any joint position, limb angle, foot contact, root position, camera, or motion timing.
If image 1 has long sleeves, they must cover both shoulders and both upper arms in every cell; never expose mannequin muscles through the clothing. Preserve loose pant volume instead of tightening it to the mannequin legs.
The 3D mannequin is authoritative only for joint positions, limb angles, foot contact, motion phase, and camera. It is not an appearance or silhouette reference.
The character image is authoritative for body proportions and the complete outer silhouette: preserve the exact garment length and looseness, hems, cuffs, patches, pockets, pant width, shoes, hair, face, and all asymmetrical details. Never tighten, shorten, simplify, or replace the original clothing to match the mannequin.
Keep the exact 4 columns by 2 rows sheet layout, one complete full-body character per cell, equal scale, equal root position, and the same {direction} camera direction in every cell.
Direction lock for all eight cells: {direction_copy}. Never flip to another view for even one frame.
Preserve identity and equipment across all eight frames. Make the motion read clearly and loop without a pop.
{motion_copy}
Rendering style: {style}; clean hand-painted 2D game-character art with crisp edges. Follow the supplied joint pose at about {shape_lock}% strictness while keeping the identity image's clothing silhouette and proportions. Prepare forms for about {pixel_simplify}% simplification, but do not pixelate yet.
Use a perfectly flat #00FF00 background edge-to-edge. No floor, cast shadow, scenery, props not in the reference, text, border, labels, or watermark.""".strip()


def build_qwen_prompt(
    identity_name: str,
    identity_sheet_name: str,
    pose_name: str,
    depth_name: str,
    guide_name: str,
    output_prefix: str,
    *,
    action: str,
    direction: str,
    style: str,
    shape_lock: int,
    pixel_simplify: int,
    seed: int,
    prompt_text: str | None = None,
    denoise: float | None = None,
    megapixels: float = 2.0,
) -> dict:
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "qwen-image-edit-2511-Q5_K_S.gguf"}},
        "2": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["1", 0],
                "lora_name": "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
                "strength_model": 1.0,
            },
        },
        "3": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["2", 0], "shift": 3.1}},
        "4": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"},
        },
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "low quality, blur, shadow, duplicate subject in one cell, missing limbs, extra limbs, identity drift, clothing drift, pose drift, changed limb angle, changed foot contact, changed root position, split face, sliced head, green holes inside body, rectangular seams, detached fragments, broken silhouette, text, watermark, floor, scenery",
                "clip": ["4", 0],
            },
        },
        "7": {"class_type": "LoadImage", "inputs": {"image": identity_name}},
        "8": {
            "class_type": "TextEncodeQwenImageEditPlus",
            "inputs": {
                "clip": ["4", 0],
                "vae": ["5", 0],
                "image1": ["7", 0],
                "prompt": prompt_text or _identity_prompt(action, direction, style, shape_lock, pixel_simplify),
            },
        },
        "9": {"class_type": "LoadImage", "inputs": {"image": pose_name}},
        "10": {"class_type": "ImageScaleToMegapixels", "inputs": {"images": ["9", 0], "megapixels": megapixels}},
        "11": {"class_type": "VAEEncode", "inputs": {"pixels": ["10", 0], "vae": ["5", 0]}},
        "12": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["8", 0], "latent": ["11", 0]}},
        "13": {"class_type": "LoadImage", "inputs": {"image": depth_name}},
        "14": {"class_type": "ImageScaleToMegapixels", "inputs": {"images": ["13", 0], "megapixels": megapixels}},
        "15": {"class_type": "VAEEncode", "inputs": {"pixels": ["14", 0], "vae": ["5", 0]}},
        "16": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["12", 0], "latent": ["15", 0]}},
        "17": {"class_type": "LoadImage", "inputs": {"image": guide_name}},
        "18": {"class_type": "ImageScaleToMegapixels", "inputs": {"images": ["17", 0], "megapixels": megapixels}},
        "19": {"class_type": "VAEEncode", "inputs": {"pixels": ["18", 0], "vae": ["5", 0]}},
        "20": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["3", 0],
                "seed": seed,
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "positive": ["23", 0],
                "negative": ["6", 0],
                "latent_image": ["26", 0],
                "denoise": denoise if denoise is not None else (0.88 if action == "idle" else (0.90 if action == "walk" else 0.92)),
            },
        },
        "21": {"class_type": "VAEDecode", "inputs": {"samples": ["20", 0], "vae": ["5", 0]}},
        "22": {"class_type": "SaveImage", "inputs": {"images": ["21", 0], "filename_prefix": f"{output_prefix}/painted"}},
        "23": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["16", 0], "latent": ["19", 0]}},
        "24": {"class_type": "LoadImage", "inputs": {"image": identity_sheet_name}},
        "25": {"class_type": "ImageScaleToMegapixels", "inputs": {"images": ["24", 0], "megapixels": megapixels}},
        "26": {"class_type": "VAEEncode", "inputs": {"pixels": ["25", 0], "vae": ["5", 0]}},
    }


def build_background_prompt(image_name: str, output_prefix: str) -> dict:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {
            "class_type": "BiRefNetRMBG",
            "inputs": {
                "image": ["1", 0],
                "model": "BiRefNet_toonout",
                "sensitivity": 1.0,
                "mask_blur": 0,
                "mask_offset": -1,
                "invert_output": False,
                "refine_foreground": False,
                "background": "Alpha",
                "background_color": "#222222",
            },
        },
        "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0], "filename_prefix": f"{output_prefix}/cutout"}},
    }


def _main_component(frame):
    """Return the largest opaque component plus fail-closed isolation metrics."""
    from PIL import Image

    rgba = frame.convert("RGBA")
    width, height = rgba.size
    alpha = rgba.getchannel("A")
    source = alpha.load()
    visited = bytearray(width * height)
    largest: list[tuple[int, int]] = []
    component_count = 0
    visible_pixels = 0
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if source[x, y] >= 80:
                visible_pixels += 1
            if visited[index] or source[x, y] < 80:
                continue
            component_count += 1
            component: list[tuple[int, int]] = []
            queue = deque([(x, y)])
            visited[index] = 1
            while queue:
                px, py = queue.popleft()
                component.append((px, py))
                for nx, ny in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    neighbor = ny * width + nx
                    if visited[neighbor] or source[nx, ny] < 80:
                        continue
                    visited[neighbor] = 1
                    queue.append((nx, ny))
            if len(component) > len(largest):
                largest = component
    if not largest:
        raise ValueError("ComfyUI 결과 셀에서 캐릭터를 찾지 못했습니다.")
    xs = [point[0] for point in largest]
    ys = [point[1] for point in largest]
    bbox = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    isolated = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    output_pixels = isolated.load()
    input_pixels = rgba.load()
    for x, y in largest:
        output_pixels[x, y] = input_pixels[x, y]
    touches_edge = bbox[0] == 0 or bbox[1] == 0 or bbox[2] == width or bbox[3] == height
    return isolated.crop(bbox), {
        "bbox": list(bbox),
        "bbox_width": bbox[2] - bbox[0],
        "bbox_height": bbox[3] - bbox[1],
        "component_pixels": len(largest),
        "visible_pixels": visible_pixels,
        "component_ratio": len(largest) / max(1, visible_pixels),
        "component_count": component_count,
        "touches_edge": touches_edge,
        "cell_size": [width, height],
    }


def _largest_component(frame):
    return _main_component(frame)[0]


def _sheet_cells(sheet):
    if sheet.width % 4 or sheet.height % 2:
        raise ValueError("action sheet must be divisible into a 4x2 grid")
    width, height = sheet.width // 4, sheet.height // 2
    return [
        sheet.crop(((index % 4) * width, (index // 4) * height, (index % 4 + 1) * width, (index // 4 + 1) * height))
        for index in range(8)
    ]


def build_reference_idle_sheet(identity, *, width: int = 1024, height: int = 1024):
    """Create a drift-free front idle by subtly breathing the exact reference cutout."""
    from PIL import Image

    source = identity.convert("RGBA")
    alpha = Image.new("L", source.size, 255)
    source_data = source.get_flattened_data() if hasattr(source, "get_flattened_data") else source.getdata()
    alpha.putdata([
        0 if min(red, green, blue) >= 225 and max(red, green, blue) - min(red, green, blue) <= 18 else 255
        for red, green, blue, _ in source_data
    ])
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError("identity image does not contain a visible character")
    subject = source.crop(bbox)
    subject.putalpha(alpha.crop(bbox))

    cell_width = width // 4
    cell_height = height // 2
    base_scale = min((cell_width * 0.82) / subject.width, (cell_height * 0.90) / subject.height)
    base_width = max(1, round(subject.width * base_scale))
    base_height = max(1, round(subject.height * base_scale))
    breath_heights = (0, 3, 6, 3, 0, -3, -6, -3)
    breath_widths = (0, 1, 2, 1, 0, -1, -2, -1)
    sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for index, (height_delta, width_delta) in enumerate(zip(breath_heights, breath_widths)):
        frame_subject = subject.resize(
            (base_width + width_delta, base_height + height_delta),
            Image.Resampling.LANCZOS,
        )
        column, row = index % 4, index // 4
        x = column * cell_width + (cell_width - frame_subject.width) // 2
        baseline = row * cell_height + round(cell_height * 0.96)
        sheet.alpha_composite(frame_subject, (x, baseline - frame_subject.height))
    return sheet


def _foreground_figure(image):
    """Extract a subject from transparent or plain-corner reference imagery."""
    from PIL import Image

    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] < 240:
        return _largest_component(rgba)

    corners = [
        rgba.getpixel((0, 0)),
        rgba.getpixel((rgba.width - 1, 0)),
        rgba.getpixel((0, rgba.height - 1)),
        rgba.getpixel((rgba.width - 1, rgba.height - 1)),
    ]
    background = tuple(round(statistics.median(pixel[channel] for pixel in corners)) for channel in range(3))
    keyed = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    source_pixels = rgba.load()
    keyed_pixels = keyed.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            pixel = source_pixels[x, y]
            distance = math.sqrt(sum((pixel[channel] - background[channel]) ** 2 for channel in range(3)))
            if distance >= 28:
                keyed_pixels[x, y] = pixel[:3] + (255,)
    return _largest_component(keyed)


def _normalized_figure(image, size: tuple[int, int] = (64, 128)):
    from PIL import Image

    figure = _foreground_figure(image)
    padding_x = max(2, round(size[0] * 0.06))
    padding_y = max(2, round(size[1] * 0.04))
    scale = min(
        (size[0] - padding_x * 2) / max(1, figure.width),
        (size[1] - padding_y * 2) / max(1, figure.height),
    )
    resized = figure.resize(
        (max(1, round(figure.width * scale)), max(1, round(figure.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((size[0] - resized.width) // 2, size[1] - padding_y - resized.height))
    return canvas


def _mask_bits(image, size: tuple[int, int] = (32, 64)) -> tuple[int, ...]:
    from PIL import Image

    normalized = _normalized_figure(image, (64, 128))
    alpha = normalized.getchannel("A").resize(size, Image.Resampling.NEAREST)
    values = alpha.get_flattened_data() if hasattr(alpha, "get_flattened_data") else alpha.getdata()
    return tuple(1 if value >= 96 else 0 for value in values)


def _upper_body_motion_bits(image) -> tuple[int, ...]:
    """Capture the arm/hand silhouette while excluding most torso and leg motion."""
    normalized = _normalized_figure(image, (64, 128))
    alpha = normalized.getchannel("A")
    pixels = alpha.load()
    lateral_x = (*range(0, 22), *range(42, 64))
    return tuple(1 if pixels[x, y] >= 96 else 0 for y in range(18, 80) for x in lateral_x)


def _mask_delta(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    return sum(a != b for a, b in zip(left, right)) / max(1, len(left))


def _mask_iou(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    intersection = sum(a and b for a, b in zip(left, right))
    union = sum(a or b for a, b in zip(left, right))
    return intersection / max(1, union)


def _region_median(image, box: tuple[float, float, float, float]) -> tuple[int, int, int] | None:
    normalized = _normalized_figure(image, (64, 128))
    left = round(box[0] * normalized.width)
    top = round(box[1] * normalized.height)
    right = round(box[2] * normalized.width)
    bottom = round(box[3] * normalized.height)
    region = normalized.crop((left, top, right, bottom))
    values = region.get_flattened_data() if hasattr(region, "get_flattened_data") else region.getdata()
    pixels = [pixel[:3] for pixel in values if pixel[3] >= 96]
    if len(pixels) < 8:
        return None
    return tuple(round(statistics.median(pixel[channel] for pixel in pixels)) for channel in range(3))


def _color_distance(left: tuple[int, int, int] | None, right: tuple[int, int, int] | None) -> float:
    if left is None or right is None:
        return 441.7
    return math.sqrt(sum((left[channel] - right[channel]) ** 2 for channel in range(3)))


def _signature(image) -> dict[str, tuple[int, int, int] | None]:
    return {
        "hair": _region_median(image, (0.22, 0.02, 0.78, 0.20)),
        "torso": _region_median(image, (0.23, 0.27, 0.77, 0.52)),
        "legs": _region_median(image, (0.26, 0.58, 0.74, 0.86)),
    }


def _signature_spread(signatures: list[dict], key: str) -> float:
    values = [signature[key] for signature in signatures if signature.get(key) is not None]
    if not values:
        return 441.7
    center = tuple(round(statistics.median(value[channel] for value in values)) for channel in range(3))
    return max(_color_distance(value, center) for value in values)


def _arm_clothing_coverage(
    image,
    skin_color: tuple[int, int, int] | None,
    clothing_color: tuple[int, int, int] | None,
) -> float:
    normalized = _normalized_figure(image, (64, 128))
    pixels = normalized.load()
    samples = []
    lateral_x = (*range(1, 21), *range(43, 63))
    for y in range(26, 64):
        for x in lateral_x:
            pixel = pixels[x, y]
            if pixel[3] < 96:
                continue
            samples.append(
                _color_distance(pixel[:3], clothing_color)
                <= _color_distance(pixel[:3], skin_color)
            )
    return sum(samples) / max(1, len(samples))


def evaluate_action_sheet_quality(
    master,
    *,
    guide,
    identity,
    pixel_frames,
    palette_limit: int,
    minimum_score: int = 90,
    action: str = "walk",
) -> dict:
    """Strictly score identity, clothing, motion, framing, and pixel contracts."""
    cells = _sheet_cells(master.convert("RGBA"))
    extracted = [_main_component(cell) for cell in cells]
    figures = [item[0] for item in extracted]
    metrics = [item[1] for item in extracted]

    heights = [item["bbox_height"] for item in metrics]
    widths = [item["bbox_width"] for item in metrics]
    height_drift = (max(heights) - min(heights)) / max(1, statistics.median(heights))
    width_drift = (max(widths) - min(widths)) / max(1, statistics.median(widths))
    min_component_ratio = min(item["component_ratio"] for item in metrics)
    edge_frames = [index + 1 for index, item in enumerate(metrics) if item["touches_edge"]]

    signatures = [_signature(figure) for figure in figures]
    reference = _signature(identity)
    torso_spread = _signature_spread(signatures, "torso")
    legs_spread = _signature_spread(signatures, "legs")
    hair_spread = _signature_spread(signatures, "hair")
    reference_distances = []
    for signature in signatures:
        reference_distances.append(statistics.mean(_color_distance(signature[key], reference[key]) for key in ("hair", "torso", "legs")))
    reference_distance = statistics.median(reference_distances)
    reference_skin = _region_median(identity, (0.34, 0.08, 0.66, 0.23))
    reference_clothing = reference["torso"]
    reference_arm_coverage = _arm_clothing_coverage(identity, reference_skin, reference_clothing)
    arm_coverages = [
        _arm_clothing_coverage(figure, reference_skin, reference_clothing)
        for figure in figures
    ]
    if reference_arm_coverage >= 0.55:
        minimum_arm_coverage = reference_arm_coverage * 0.65
        median_arm_coverage = reference_arm_coverage * 0.75
        sleeve_pass = min(arm_coverages) >= minimum_arm_coverage and statistics.median(arm_coverages) >= median_arm_coverage
    else:
        minimum_arm_coverage = 0.0
        median_arm_coverage = 0.0
        sleeve_pass = True

    candidate_masks = [_mask_bits(figure) for figure in figures]
    guide_masks = [_mask_bits(cell) for cell in _sheet_cells(guide.convert("RGBA"))]
    pose_ious = [_mask_iou(candidate, expected) for candidate, expected in zip(candidate_masks, guide_masks)]
    adjacent_deltas = [_mask_delta(candidate_masks[index], candidate_masks[index + 1]) for index in range(7)]
    half_cycle_delta = _mask_delta(candidate_masks[0], candidate_masks[4])
    idle_excursion = max(_mask_delta(candidate_masks[0], mask) for mask in candidate_masks[1:])
    unique_masks = len(set(candidate_masks))

    guide_adjacent_deltas = [_mask_delta(guide_masks[index], guide_masks[index + 1]) for index in range(7)]
    guide_idle_excursion = max(_mask_delta(guide_masks[0], mask) for mask in guide_masks[1:])
    if action == "idle":
        idle_mean_min = max(0.001, statistics.mean(guide_adjacent_deltas) * 0.25)
        idle_mean_max = max(0.025, statistics.mean(guide_adjacent_deltas) * 3.5)
        idle_excursion_min = max(0.002, guide_idle_excursion * 0.25)
        idle_excursion_max = max(0.04, guide_idle_excursion * 3.5)
        motion_pass = (
            idle_mean_min <= statistics.mean(adjacent_deltas) <= idle_mean_max
            and idle_excursion_min <= idle_excursion <= idle_excursion_max
            and unique_masks >= 3
        )
        motion_threshold = {
            "mean_delta": [round(idle_mean_min, 4), round(idle_mean_max, 4)],
            "excursion": [round(idle_excursion_min, 4), round(idle_excursion_max, 4)],
            "unique": 3,
        }
    else:
        motion_pass = (
            min(adjacent_deltas) >= 0.006
            and statistics.mean(adjacent_deltas) >= 0.02
            and half_cycle_delta >= 0.025
            and unique_masks >= 6
        )
        motion_threshold = {"min_delta": 0.006, "mean_delta": 0.02, "half_cycle": 0.025, "unique": 6}

    upper_body_masks = [_upper_body_motion_bits(figure) for figure in figures]
    upper_body_deltas = [_mask_delta(upper_body_masks[index], upper_body_masks[index + 1]) for index in range(7)]
    upper_body_half_cycle = _mask_delta(upper_body_masks[0], upper_body_masks[4])
    upper_body_unique = len(set(upper_body_masks))
    guide_upper_body_masks = [_upper_body_motion_bits(cell) for cell in _sheet_cells(guide.convert("RGBA"))]
    guide_upper_body_deltas = [
        _mask_delta(guide_upper_body_masks[index], guide_upper_body_masks[index + 1])
        for index in range(7)
    ]
    guide_upper_body_half_cycle = _mask_delta(guide_upper_body_masks[0], guide_upper_body_masks[4])
    if action == "idle":
        upper_body_excursion = max(_mask_delta(upper_body_masks[0], mask) for mask in upper_body_masks[1:])
        guide_upper_body_excursion = max(
            _mask_delta(guide_upper_body_masks[0], mask) for mask in guide_upper_body_masks[1:]
        )
        upper_mean_min = max(0.001, statistics.mean(guide_upper_body_deltas) * 0.25)
        upper_mean_max = max(0.04, statistics.mean(guide_upper_body_deltas) * 3.5)
        upper_excursion_min = max(0.002, guide_upper_body_excursion * 0.25)
        upper_excursion_max = max(0.06, guide_upper_body_excursion * 3.5)
        upper_body_pass = (
            upper_mean_min <= statistics.mean(upper_body_deltas) <= upper_mean_max
            and upper_excursion_min <= upper_body_excursion <= upper_excursion_max
            and upper_body_unique >= 3
        )
        upper_body_threshold = {
            "guide_retention": 0.25,
            "mean_delta": [round(upper_mean_min, 4), round(upper_mean_max, 4)],
            "excursion": [round(upper_excursion_min, 4), round(upper_excursion_max, 4)],
            "unique": 3,
        }
    else:
        retention_factor = 0.70 if action == "run" else 0.65
        minimum_delta = max(0.004, min(guide_upper_body_deltas) * retention_factor)
        mean_delta = max(0.008, statistics.mean(guide_upper_body_deltas) * retention_factor)
        half_cycle = max(0.008, guide_upper_body_half_cycle * retention_factor)
        upper_body_pass = (
            min(upper_body_deltas) >= minimum_delta
            and statistics.mean(upper_body_deltas) >= mean_delta
            and upper_body_half_cycle >= half_cycle
            and upper_body_unique >= 7
        )
        upper_body_threshold = {
            "guide_retention": retention_factor,
            "min_delta": round(minimum_delta, 4),
            "mean_delta": round(mean_delta, 4),
            "half_cycle": round(half_cycle, 4),
            "unique": 7,
        }

    visible_colors = {
        pixel[:3]
        for frame in pixel_frames
        for pixel in (frame.convert("RGBA").get_flattened_data() if hasattr(frame, "get_flattened_data") else frame.convert("RGBA").getdata())
        if pixel[3]
    }
    binary_alpha = all(
        set(
            frame.convert("RGBA").getchannel("A").get_flattened_data()
            if hasattr(frame.convert("RGBA").getchannel("A"), "get_flattened_data")
            else frame.convert("RGBA").getchannel("A").getdata()
        ).issubset({0, 255})
        for frame in pixel_frames
    )
    pixel_nonempty = all(frame.convert("RGBA").getchannel("A").getbbox() is not None for frame in pixel_frames)

    checks = [
        {"id": "frame-count", "label": "8프레임 완성", "pass": len(figures) == 8 and len(pixel_frames) == 8, "value": len(pixel_frames), "threshold": 8, "weight": 5, "critical": True},
        {"id": "single-actor", "label": "한 캐릭터만 유지", "pass": min_component_ratio >= 0.94, "value": round(min_component_ratio, 3), "threshold": ">= 0.94", "weight": 10, "critical": True},
        {"id": "safe-crop", "label": "잘림 없는 여백", "pass": not edge_frames, "value": edge_frames, "threshold": "0 edge frames", "weight": 5, "critical": False},
        {"id": "scale-lock", "label": "캐릭터 크기 고정", "pass": height_drift <= 0.16, "value": round(height_drift, 3), "threshold": "<= 0.16", "weight": 10, "critical": True},
        {"id": "width-lock", "label": "체형 폭 일관성", "pass": width_drift <= 0.30, "value": round(width_drift, 3), "threshold": "<= 0.30", "weight": 5, "critical": True},
        {"id": "clothing-lock", "label": "옷 색과 머리색 고정", "pass": torso_spread <= 72 and legs_spread <= 68 and hair_spread <= 82, "value": {"torso": round(torso_spread, 1), "legs": round(legs_spread, 1), "hair": round(hair_spread, 1)}, "threshold": {"torso": 72, "legs": 68, "hair": 82}, "weight": 15, "critical": True},
        {"id": "sleeve-retention", "label": "소매·작업복 범위 유지", "pass": sleeve_pass, "value": {"reference": round(reference_arm_coverage, 3), "min": round(min(arm_coverages), 3), "median": round(statistics.median(arm_coverages), 3)}, "threshold": {"min": round(minimum_arm_coverage, 3), "median": round(median_arm_coverage, 3)}, "weight": 10, "critical": True},
        {"id": "reference-palette", "label": "원본 캐릭터 색상 유지", "pass": reference_distance <= 105, "value": round(reference_distance, 1), "threshold": "<= 105", "weight": 10, "critical": False},
        {"id": "pose-match", "label": "걷기 포즈 준수", "pass": min(pose_ious) >= 0.28 and statistics.mean(pose_ious) >= 0.42, "value": {"min": round(min(pose_ious), 3), "mean": round(statistics.mean(pose_ious), 3)}, "threshold": {"min": 0.28, "mean": 0.42}, "weight": 15, "critical": True},
        {"id": "motion-progress", "label": "프레임별 동작 진행", "pass": motion_pass, "value": {"min_delta": round(min(adjacent_deltas), 3), "mean_delta": round(statistics.mean(adjacent_deltas), 3), "half_cycle": round(half_cycle_delta, 3), "excursion": round(idle_excursion, 3), "unique": unique_masks}, "threshold": motion_threshold, "weight": 15, "critical": True},
        {"id": "upper-body-motion", "label": "UAL 팔·손 동작 유지", "pass": upper_body_pass, "value": {"min_delta": round(min(upper_body_deltas), 3), "mean_delta": round(statistics.mean(upper_body_deltas), 3), "half_cycle": round(upper_body_half_cycle, 3), "unique": upper_body_unique}, "threshold": upper_body_threshold, "weight": 15, "critical": True},
        {"id": "pixel-contract", "label": "투명 배경·팔레트 규격", "pass": binary_alpha and pixel_nonempty and len(visible_colors) <= palette_limit, "value": {"binary_alpha": binary_alpha, "nonempty": pixel_nonempty, "colors": len(visible_colors)}, "threshold": {"colors": palette_limit}, "weight": 10, "critical": True},
    ]
    total_weight = sum(check["weight"] for check in checks)
    earned_weight = sum(check["weight"] for check in checks if check["pass"])
    score = round(earned_weight / max(1, total_weight) * 100)
    critical_pass = all(check["pass"] for check in checks if check["critical"])
    passed = critical_pass and score >= minimum_score
    failures = [check["label"] for check in checks if not check["pass"]]
    return {
        "pass": passed,
        "score": score,
        "minimum_score": minimum_score,
        "checks": [{key: value for key, value in check.items() if key not in {"weight", "critical"}} for check in checks],
        "failures": failures,
        "metrics": {
            "source_frames": metrics,
            "pose_ious": [round(value, 4) for value in pose_ious],
            "adjacent_mask_deltas": [round(value, 4) for value in adjacent_deltas],
            "upper_body_mask_deltas": [round(value, 4) for value in upper_body_deltas],
            "upper_body_half_cycle": round(upper_body_half_cycle, 4),
            "guide_upper_body_mask_deltas": [round(value, 4) for value in guide_upper_body_deltas],
            "guide_upper_body_half_cycle": round(guide_upper_body_half_cycle, 4),
            "reference_color_distances": [round(value, 2) for value in reference_distances],
            "arm_clothing_coverages": [round(value, 4) for value in arm_coverages],
        },
    }


def pixelize_action_sheet(master, *, cell_width: int, palette_colors: int):
    """Extract eight actors, lock their shared scale/root, and quantize one palette."""
    from PIL import Image, ImageChops, ImageFilter

    master = master.convert("RGBA")
    if master.width % 4 or master.height % 2:
        raise ValueError("ComfyUI action sheet must be divisible into a 4x2 grid")
    source_width = master.width // 4
    source_height = master.height // 2
    figures = []
    for index in range(8):
        column, row = index % 4, index // 4
        cell = master.crop((column * source_width, row * source_height, (column + 1) * source_width, (row + 1) * source_height))
        figures.append(_largest_component(cell))

    cell_height = cell_width * 2
    padding_x = max(3, round(cell_width * 0.08))
    bottom_padding = max(4, round(cell_height * 0.04))
    top_padding = max(4, round(cell_height * 0.04))
    scale = min(
        (cell_width - padding_x * 2) / max(figure.width for figure in figures),
        (cell_height - bottom_padding - top_padding) / max(figure.height for figure in figures),
    )
    sheet = Image.new("RGBA", (cell_width * 4, cell_height * 2), (0, 0, 0, 0))
    for index, figure in enumerate(figures):
        size = (max(1, round(figure.width * scale)), max(1, round(figure.height * scale)))
        figure = figure.resize(size, Image.Resampling.LANCZOS)
        column, row = index % 4, index // 4
        x = column * cell_width + (cell_width - figure.width) // 2
        y = row * cell_height + cell_height - bottom_padding - figure.height
        sheet.alpha_composite(figure, (x, y))

    alpha = sheet.getchannel("A").point(lambda value: 255 if value >= 96 else 0)
    palette_source = Image.new("RGB", sheet.size, (255, 0, 255))
    palette_source.paste(sheet.convert("RGB"), mask=alpha)
    quantized = palette_source.quantize(
        colors=palette_colors,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    ).convert("RGB").convert("RGBA")
    quantized.putalpha(alpha)
    visible_rgb = [pixel[:3] for pixel in quantized.get_flattened_data() if pixel[3]]
    outline_color = min(visible_rgb, key=lambda color: color[0] * 299 + color[1] * 587 + color[2] * 114)
    outline_alpha = ImageChops.subtract(alpha.filter(ImageFilter.MaxFilter(3)), alpha)
    outlined = Image.new("RGBA", quantized.size, (*outline_color, 0))
    outlined.putalpha(outline_alpha)
    outlined.alpha_composite(quantized)
    quantized = outlined
    frames = []
    for index in range(8):
        column, row = index % 4, index // 4
        frames.append(quantized.crop((column * cell_width, row * cell_height, (column + 1) * cell_width, (row + 1) * cell_height)))
    pixels = quantized.get_flattened_data() if hasattr(quantized, "get_flattened_data") else quantized.getdata()
    visible_colors = len({pixel[:3] for pixel in pixels if pixel[3]})
    return quantized, frames, {
        "visible_colors": visible_colors,
        "palette_limit": palette_colors,
        "frame_size": [cell_width, cell_height],
        "outline": "1px",
        "alpha": "binary",
    }


def _png_bytes(image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _preview_gif_bytes(frames, action: str) -> bytes:
    from PIL import Image

    duration = {"idle": 180, "walk": 120, "run": 85}[action]
    rendered = []
    for frame in frames:
        canvas = Image.new("RGBA", frame.size, (226, 226, 226, 255))
        canvas.alpha_composite(frame)
        rendered.append(canvas.convert("RGB").resize((frame.width * 4, frame.height * 4), Image.Resampling.NEAREST))
    output = io.BytesIO()
    rendered[0].save(output, format="GIF", save_all=True, append_images=rendered[1:], duration=duration, loop=0, disposal=2, optimize=False)
    return output.getvalue()


def _save_input_image(image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGBA").save(path, format="PNG", optimize=True)


def _retry_identity_prompt(settings: dict, previous_qa: dict | None) -> str:
    prompt = _identity_prompt(
        settings["action"],
        settings["direction"],
        settings["style"],
        settings["shape_lock"],
        settings["pixel_simplify"],
    )
    if not previous_qa:
        return prompt
    failure_copy = ", ".join(previous_qa.get("failures") or [])
    return (
        prompt
        + "\n\nSTRICT RETRY: The previous whole-sheet candidate was rejected by automatic QA for: "
        + failure_copy
        + ". Correct those failures across the entire 4x2 sheet. Copy the exact same hair, face, navy jacket, beige collar, cuffs, pockets, patches, loose dark pants, and shoes from image 1 into every cell. Keep all eight bodies at one scale and root. Make every gait phase visibly distinct while following its matching pose/depth cell. Never repair only one frame by changing the character design."
    )


def _build_identity_start_sheet(identity, guide):
    """Tile the real character into the guide grid for an identity-first edit latent."""
    from PIL import Image

    source = identity.convert("RGBA")
    source_pixels = source.load()
    alpha = Image.new("L", source.size, 0)
    alpha_pixels = alpha.load()
    for y in range(source.height):
        for x in range(source.width):
            red, green, blue, _ = source_pixels[x, y]
            alpha_pixels[x, y] = 0 if min(red, green, blue) >= 245 else 255
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError("identity image does not contain a visible character")
    subject = source.crop(bbox)
    subject.putalpha(alpha.crop(bbox))

    sheet = Image.new("RGBA", guide.size, (0, 255, 0, 255))
    cell_width = guide.width // 4
    cell_height = guide.height // 2
    scale = min((cell_width * 0.82) / subject.width, (cell_height * 0.90) / subject.height)
    target_size = (
        max(1, round(subject.width * scale)),
        max(1, round(subject.height * scale)),
    )
    subject = subject.resize(target_size, Image.Resampling.LANCZOS)
    for index in range(8):
        column, row = index % 4, index // 4
        x = column * cell_width + (cell_width - subject.width) // 2
        y = row * cell_height + round(cell_height * 0.95) - subject.height
        sheet.alpha_composite(subject, (x, y))
    return sheet


def generate_local_action_sheet(data: object, *, client: ComfyClient | None = None) -> dict:
    """Run the complete local 3D guide -> 2D pixel action workflow."""
    from PIL import Image

    settings = normalize_local_action_payload(data)
    client = client or ComfyClient()
    health = local_3d_pipeline_health(client=client)
    if not health.get("available"):
        detail = ", ".join(health.get("missing_nodes") or []) or health.get("error") or health.get("reason")
        raise RuntimeError(f"로컬 ComfyUI 파이프라인이 준비되지 않았습니다: {detail}")

    run_id = uuid.uuid4().hex
    relative_job = Path("asset_studio") / run_id
    input_job = client.paths.input / relative_job
    input_job.mkdir(parents=True, exist_ok=False)
    guide_path = input_job / "guide.png"
    identity_path = input_job / "identity.png"
    identity_sheet_path = input_job / "identity-sheet.png"
    _save_input_image(settings["guide"], guide_path)
    _save_input_image(settings["identity"], identity_path)
    _save_input_image(_build_identity_start_sheet(settings["identity"], settings["guide"]), identity_sheet_path)
    guide_name = (relative_job / guide_path.name).as_posix()
    identity_name = (relative_job / identity_path.name).as_posix()
    identity_sheet_name = (relative_job / identity_sheet_path.name).as_posix()
    output_prefix = f"AssetStudio/{run_id}"

    try:
        controls = client.run(build_controls_prompt(guide_name, output_prefix))
        pose_output = client.output_path(controls, "3")
        depth_output = client.output_path(controls, "7")
        pose_input = input_job / "pose.png"
        depth_input = input_job / "depth.png"
        shutil.copy2(pose_output, pose_input)
        shutil.copy2(depth_output, depth_input)

        previous_qa = None
        attempt_reports = []
        best_candidate = None
        for attempt_index in range(settings["max_attempts"]):
            attempt_number = attempt_index + 1
            attempt_seed = (settings["seed"] + attempt_index * 104_729) & (2**63 - 1)
            attempt_prefix = f"{output_prefix}/attempt-{attempt_number:02d}"
            qwen = client.run(
                build_qwen_prompt(
                    identity_name,
                    identity_sheet_name,
                    (relative_job / pose_input.name).as_posix(),
                    (relative_job / depth_input.name).as_posix(),
                    guide_name,
                    attempt_prefix,
                    action=settings["action"],
                    direction=settings["direction"],
                    style=settings["style"],
                    shape_lock=settings["shape_lock"],
                    pixel_simplify=settings["pixel_simplify"],
                    seed=attempt_seed,
                    prompt_text=_retry_identity_prompt(settings, previous_qa),
                )
            )
            painted_output = client.output_path(qwen, "22")
            painted_input = input_job / f"painted-{attempt_number:02d}.png"
            shutil.copy2(painted_output, painted_input)

            background = client.run(
                build_background_prompt(
                    (relative_job / painted_input.name).as_posix(),
                    attempt_prefix,
                )
            )
            cutout_output = client.output_path(background, "3")
            try:
                with Image.open(cutout_output) as cutout:
                    cutout_rgba = cutout.convert("RGBA")
                    cutout_rgba.load()
                atlas, frames, pixel_qa = pixelize_action_sheet(
                    cutout_rgba,
                    cell_width=settings["resolution"],
                    palette_colors=settings["palette_colors"],
                )
                strict_qa = evaluate_action_sheet_quality(
                    cutout_rgba,
                    guide=settings["guide"],
                    identity=settings["identity"],
                    pixel_frames=frames,
                    palette_limit=settings["palette_colors"],
                    minimum_score=settings["min_qa_score"],
                    action=settings["action"],
                )
            except ValueError as exc:
                attempt_reports.append(
                    {
                        "attempt": attempt_number,
                        "seed": attempt_seed,
                        "pass": False,
                        "score": 0,
                        "failures": [str(exc)],
                    }
                )
                previous_qa = {"failures": [str(exc)]}
                continue

            attempt_reports.append(
                {
                    "attempt": attempt_number,
                    "seed": attempt_seed,
                    "pass": strict_qa["pass"],
                    "score": strict_qa["score"],
                    "failures": strict_qa["failures"],
                }
            )
            candidate = {
                "atlas": atlas,
                "frames": frames,
                "pixel_qa": pixel_qa,
                "strict_qa": strict_qa,
                "seed": attempt_seed,
            }
            if best_candidate is None or strict_qa["score"] > best_candidate["strict_qa"]["score"]:
                best_candidate = candidate
            if strict_qa["pass"] or not settings["strict_validation"]:
                best_candidate = candidate
                break
            previous_qa = strict_qa

        if best_candidate is None:
            failures = attempt_reports[-1]["failures"] if attempt_reports else ["no candidate was produced"]
            raise RuntimeError("ComfyUI strict validation could not produce a usable sheet: " + "; ".join(failures))

        atlas = best_candidate["atlas"]
        frames = best_candidate["frames"]
        strict_qa = dict(best_candidate["strict_qa"])
        strict_qa["enforced"] = settings["strict_validation"]
        strict_qa["attempts_used"] = len(attempt_reports)
        strict_qa["max_attempts"] = settings["max_attempts"]
        strict_qa["attempts"] = attempt_reports
        if not settings["strict_validation"]:
            strict_qa["would_pass"] = strict_qa["pass"]
            strict_qa["pass"] = True
        qa = {**best_candidate["pixel_qa"], "strict": strict_qa}
        accepted = bool(strict_qa["pass"])
        atlas_bytes = _png_bytes(atlas)
        frame_bytes = [_png_bytes(frame) for frame in frames]
        preview_bytes = _preview_gif_bytes(frames, settings["action"])
        return {
            "run_id": run_id,
            "accepted": accepted,
            "atlas": atlas_bytes,
            "frames": frame_bytes,
            "preview": preview_bytes,
            "metadata": {
                "artifact_digest": hashlib.sha256(atlas_bytes).hexdigest(),
                "provider": "local-comfyui",
                "model": "Qwen-Image-Edit-2511-Lightning-4steps",
                "method": "whole-sheet-qwen-image-edit+dwpose+depth+strict-retry-qa+shared-palette-pixelization",
                "action": settings["action"],
                "direction": settings["direction"],
                "frame_count": 8,
                "frame_width": settings["resolution"],
                "frame_height": settings["resolution"] * 2,
                "palette_colors": settings["palette_colors"],
                "seed": best_candidate["seed"],
                "base_seed": settings["seed"],
                "shape_lock": settings["shape_lock"],
                "pixel_simplify": settings["pixel_simplify"],
                "qa": qa,
                "accepted": accepted,
                "hermes_used": False,
                "codex_used": False,
            },
        }
    finally:
        shutil.rmtree(input_job, ignore_errors=True)
        try:
            input_job.parent.rmdir()
        except OSError:
            pass
