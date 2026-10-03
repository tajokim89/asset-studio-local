"""Local image-to-3D and Blender motion production for Asset Studio.

Hunyuan3D in the user's local ComfyUI creates the base mesh.  Blender then
adds a compact humanoid rig and appends Idle, Walk, and Run actions one at a
time.  No hosted agent or Hermes process participates in this pipeline.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import subprocess
import uuid
from pathlib import Path
from urllib.parse import unquote

from .local_3d_pipeline import ComfyClient, _decode_image_data_url


HUNYUAN_NODES = frozenset({
    "LoadImage",
    "ImageResize+",
    "TransparentBGSession+",
    "ImageRemoveBackground+",
    "InvertMask",
    "JoinImageWithAlpha",
    "Hy3D21MeshGenerator",
    "Hy3D21VAELoader",
    "Hy3D21VAEDecode",
    "Hy3D21PostprocessMesh",
    "Hy3D21ExportMesh",
})
SUPPORTED_MOTIONS = frozenset({"idle", "walk", "run"})
DEFAULT_BLENDER = Path(r"C:\Users\tajok\dev\codex\tools\blender-4.5.12-windows-x64\blender.exe")


def resolve_blender() -> Path | None:
    configured = os.environ.get("ASSET_STUDIO_BLENDER")
    candidates = [Path(configured).expanduser() if configured else None, DEFAULT_BLENDER]
    command = shutil.which("blender")
    if command:
        candidates.append(Path(command))
    return next((path.resolve() for path in candidates if path and path.is_file()), None)


def local_model_pipeline_health(*, client: ComfyClient | None = None) -> dict:
    client = client or ComfyClient()
    blender = resolve_blender()
    try:
        info = client.object_info()
        missing = sorted(HUNYUAN_NODES.difference(info))
        comfy_paths_ready = client.paths.input.is_dir() and client.paths.output.is_dir()
        return {
            "model_generation_available": not missing and comfy_paths_ready,
            "animation_available": blender is not None,
            "blender": str(blender) if blender else None,
            "hunyuan_missing_nodes": missing,
            "hunyuan_model": "Hunyuan3D 2.1 local",
            "hermes_required": False,
        }
    except Exception as exc:
        return {
            "model_generation_available": False,
            "animation_available": blender is not None,
            "blender": str(blender) if blender else None,
            "hunyuan_missing_nodes": [],
            "hunyuan_model": "Hunyuan3D 2.1 local",
            "hermes_required": False,
            "model_generation_error": str(exc),
        }


def build_hunyuan_prompt(input_name: str, output_prefix: str, *, seed: int) -> dict:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": input_name}},
        "2": {"class_type": "ImageResize+", "inputs": {"image": ["1", 0], "width": 518, "height": 518, "interpolation": "lanczos", "method": "pad", "condition": "always", "multiple_of": 2}},
        "3": {"class_type": "ImageResize+", "inputs": {"image": ["1", 0], "width": 768, "height": 768, "interpolation": "lanczos", "method": "pad", "condition": "always", "multiple_of": 2}},
        "4": {"class_type": "TransparentBGSession+", "inputs": {"mode": "base", "use_jit": False}},
        "5": {"class_type": "ImageRemoveBackground+", "inputs": {"rembg_session": ["4", 0], "image": ["2", 0]}},
        "6": {"class_type": "InvertMask", "inputs": {"mask": ["5", 1]}},
        "7": {"class_type": "JoinImageWithAlpha", "inputs": {"image": ["3", 0], "alpha": ["6", 0]}},
        "8": {"class_type": "Hy3D21MeshGenerator", "inputs": {"model": "hunyuan3d-dit-v2-1.ckpt", "image": ["7", 0], "steps": 20, "guidance_scale": 7.5, "seed": seed, "attention_mode": "sdpa"}},
        "9": {"class_type": "Hy3D21VAELoader", "inputs": {"model_name": "hunyuan3d-vae-v2-1.ckpt"}},
        "10": {"class_type": "Hy3D21VAEDecode", "inputs": {"vae": ["9", 0], "latents": ["8", 0], "box_v": 1.01, "octree_resolution": 368, "num_chunks": 100000, "mc_level": 0.0, "mc_algo": "mc", "enable_flash_vdm": True, "force_offload": True}},
        "11": {"class_type": "Hy3D21PostprocessMesh", "inputs": {"trimesh": ["10", 0], "remove_floaters": True, "remove_degenerate_faces": True, "reduce_faces": True, "max_facenum": 100000, "smooth_normals": True}},
        "12": {"class_type": "Hy3D21ExportMesh", "inputs": {"trimesh": ["11", 0], "filename_prefix": output_prefix, "file_format": "glb", "save_file": True}},
    }


def _model_seed(image) -> int:
    digest = hashlib.sha256(image.tobytes()[:4_000_000]).digest()
    return int.from_bytes(digest[:8], "big") & (2**63 - 1)


def generate_local_base_model(data: object, *, generated_root: Path, client: ComfyClient | None = None) -> dict:
    if not isinstance(data, dict):
        raise ValueError("image-to-3D payload must be an object")
    image = _decode_image_data_url(data.get("image"), "image")
    client = client or ComfyClient(timeout_seconds=1800)
    health = local_model_pipeline_health(client=client)
    if not health["model_generation_available"]:
        missing = ", ".join(health.get("hunyuan_missing_nodes") or [])
        raise RuntimeError(f"로컬 Hunyuan3D를 사용할 수 없습니다.{(' 누락 노드: ' + missing) if missing else ''}")

    run_id = uuid.uuid4().hex
    relative_input = Path("asset_studio_3d") / run_id / "reference.png"
    comfy_input = client.paths.input / relative_input
    comfy_input.parent.mkdir(parents=True, exist_ok=True)
    image.save(comfy_input, format="PNG")
    output_prefix = f"AssetStudio3D/{run_id}/base_model"
    client.run(build_hunyuan_prompt(relative_input.as_posix(), output_prefix, seed=_model_seed(image)))
    matches = sorted((client.paths.output / "AssetStudio3D" / run_id).glob("base_model*.glb"))
    if not matches:
        raise RuntimeError("Hunyuan3D 작업은 끝났지만 GLB 결과를 찾지 못했습니다.")

    destination = generated_root / "3d-models" / run_id
    destination.mkdir(parents=True, exist_ok=True)
    model_path = destination / "base_model.glb"
    reference_path = destination / "reference.png"
    shutil.copy2(matches[-1], model_path)
    image.save(reference_path, format="PNG")
    summary = inspect_glb(model_path)
    return {
        "success": True,
        "run_id": run_id,
        "url": f"/assets/generated/3d-models/{run_id}/base_model.glb",
        "reference_url": f"/assets/generated/3d-models/{run_id}/reference.png",
        "name": "base_model.glb",
        "provider": "local-comfyui-hunyuan3d-2.1",
        "model": "hunyuan3d-dit-v2-1",
        "summary": summary,
    }


def _safe_asset_model(model_url: object, *, assets_root: Path) -> Path:
    if not isinstance(model_url, str) or not model_url.startswith("/assets/"):
        raise ValueError("a server asset GLB URL is required")
    relative = Path(unquote(model_url.removeprefix("/assets/")))
    if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != ".glb":
        raise ValueError("invalid model asset URL")
    resolved = (assets_root / relative).resolve()
    try:
        resolved.relative_to(assets_root.resolve())
    except ValueError as exc:
        raise ValueError("model URL points outside the asset directory") from exc
    if not resolved.is_file():
        raise ValueError("model asset does not exist")
    if resolved.stat().st_size > 500 * 1024 * 1024:
        raise ValueError("model asset exceeds 500MB")
    return resolved


def animate_local_model(
    data: object,
    *,
    assets_root: Path,
    generated_root: Path,
    script_path: Path,
    blender: Path | None = None,
) -> dict:
    if not isinstance(data, dict):
        raise ValueError("3D motion payload must be an object")
    action = str(data.get("action", "")).strip().lower()
    if action not in SUPPORTED_MOTIONS:
        raise ValueError("action must be idle, walk, or run")
    source = _safe_asset_model(data.get("model_url"), assets_root=assets_root)
    blender = blender or resolve_blender()
    if blender is None:
        raise RuntimeError("Blender 4.5 실행 파일을 찾지 못했습니다.")
    if not script_path.is_file():
        raise RuntimeError("Blender animation script is missing")

    run_id = uuid.uuid4().hex
    destination = generated_root / "3d-models" / run_id
    destination.mkdir(parents=True, exist_ok=True)
    glb_path = destination / f"model_{action}.glb"
    blend_path = destination / f"model_{action}.blend"
    report_path = destination / f"model_{action}.json"
    command = [
        str(blender), "--background", "--python", str(script_path), "--",
        "--input", str(source), "--output", str(glb_path),
        "--blend-output", str(blend_path), "--report", str(report_path),
        "--actions", action,
    ]
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=300,
        check=False,
    )
    if completed.returncode != 0 or not glb_path.is_file():
        detail = (completed.stderr + "\n" + completed.stdout)[-4000:]
        raise RuntimeError(f"Blender {action} 생성 실패: {detail}")
    summary = inspect_glb(glb_path)
    expected = action.capitalize()
    if expected not in summary["animations"]:
        raise RuntimeError(f"Blender 결과에 {expected} 클립이 없습니다.")
    return {
        "success": True,
        "run_id": run_id,
        "action": action,
        "url": f"/assets/generated/3d-models/{run_id}/{glb_path.name}",
        "blend_url": f"/assets/generated/3d-models/{run_id}/{blend_path.name}",
        "report_url": f"/assets/generated/3d-models/{run_id}/{report_path.name}",
        "provider": "local-blender",
        "summary": summary,
    }


def inspect_glb(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) < 20 or raw[:4] != b"glTF" or struct.unpack_from("<I", raw, 4)[0] != 2:
        raise ValueError("invalid GLB 2.0 file")
    json_length, chunk_type = struct.unpack_from("<II", raw, 12)
    if chunk_type != 0x4E4F534A or 20 + json_length > len(raw):
        raise ValueError("GLB JSON chunk is missing")
    document = json.loads(raw[20 : 20 + json_length].decode("utf-8"))
    accessors = document.get("accessors") if isinstance(document.get("accessors"), list) else []
    animations = []
    durations = {}
    channels = {}
    for index, animation in enumerate(document.get("animations") or []):
        name = str(animation.get("name") or f"Animation {index + 1}")
        animations.append(name)
        channels[name] = len(animation.get("channels") or [])
        maximum = 0.0
        for sampler in animation.get("samplers") or []:
            accessor_index = sampler.get("input")
            if isinstance(accessor_index, int) and 0 <= accessor_index < len(accessors):
                values = accessors[accessor_index].get("max") or []
                if values:
                    maximum = max(maximum, float(values[0]))
        durations[name] = maximum
    joints = {joint for skin in document.get("skins") or [] for joint in skin.get("joints") or [] if isinstance(joint, int)}
    return {
        "bytes": path.stat().st_size,
        "meshes": len(document.get("meshes") or []),
        "skins": len(document.get("skins") or []),
        "bones": len(joints),
        "animations": animations,
        "animation_channels": channels,
        "durations": durations,
    }
