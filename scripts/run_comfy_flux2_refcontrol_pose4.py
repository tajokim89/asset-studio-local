#!/usr/bin/env python3
"""Generate the two non-neutral frames of an N-L-N-R walk with FLUX.2 RefControl."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


REQUIRED_NODES = {
    "CFGGuider",
    "CLIPLoader",
    "CLIPTextEncode",
    "EmptyFlux2LatentImage",
    "Flux2Scheduler",
    "KSamplerSelect",
    "LoadImage",
    "LoraLoaderModelOnly",
    "RandomNoise",
    "ReferenceLatent",
    "SamplerCustomAdvanced",
    "SaveImage",
    "UNETLoader",
    "VAEDecode",
    "VAEEncode",
    "VAELoader",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--seed", type=int, default=2608033301)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--cfg", type=float, default=5.0)
    parser.add_argument("--lora-strength", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=1200)
    return parser.parse_args()


def request_json(url: str, payload: dict | None = None, timeout: int = 60) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="GET" if body is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ComfyUI HTTP {error.code}: {detail[:2400]}") from error
    if not isinstance(result, dict):
        raise RuntimeError("ComfyUI returned a non-object response")
    return result


def upload_image(base_url: str, path: Path, subfolder: str) -> str:
    boundary = "----asset-studio-refcontrol-" + uuid.uuid4().hex
    parts: list[bytes] = []

    def field(name: str, value: str) -> None:
        parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode(),
                b"\r\n",
            ]
        )

    field("type", "input")
    field("subfolder", subfolder)
    field("overwrite", "true")
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    parts.extend(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="image"; filename="{path.name}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    request = urllib.request.Request(
        base_url.rstrip("/") + "/upload/image",
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)
    name = str(result.get("name") or "")
    returned_subfolder = str(result.get("subfolder") or "")
    if not name:
        raise RuntimeError(f"ComfyUI upload failed: {result}")
    return "/".join(part for part in (returned_subfolder.replace("\\", "/"), name) if part)


def build_prompt(
    pose_name: str,
    master_name: str,
    prompt_text: str,
    seed: int,
    steps: int,
    cfg: float,
    lora_strength: float,
    prefix: str,
) -> dict:
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "flux-2-klein-base-4b-fp8.safetensors", "weight_dtype": "default"},
        },
        "2": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["1", 0],
                "lora_name": "refcontrol-pose-klein-4b.safetensors",
                "strength_model": lora_strength,
            },
        },
        "3": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "flux2", "device": "default"},
        },
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "5": {"class_type": "LoadImage", "inputs": {"image": pose_name}},
        "6": {"class_type": "LoadImage", "inputs": {"image": master_name}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt_text, "clip": ["3", 0]}},
        "8": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["3", 0]}},
        "9": {"class_type": "VAEEncode", "inputs": {"pixels": ["5", 0], "vae": ["4", 0]}},
        "10": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["7", 0], "latent": ["9", 0]}},
        "11": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["8", 0], "latent": ["9", 0]}},
        "12": {"class_type": "VAEEncode", "inputs": {"pixels": ["6", 0], "vae": ["4", 0]}},
        "13": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["10", 0], "latent": ["12", 0]}},
        "14": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["11", 0], "latent": ["12", 0]}},
        "15": {
            "class_type": "CFGGuider",
            "inputs": {"model": ["2", 0], "positive": ["13", 0], "negative": ["14", 0], "cfg": cfg},
        },
        "16": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "17": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "18": {"class_type": "Flux2Scheduler", "inputs": {"steps": steps, "width": 1024, "height": 1024}},
        "19": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
        },
        "20": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["16", 0],
                "guider": ["15", 0],
                "sampler": ["17", 0],
                "sigmas": ["18", 0],
                "latent_image": ["19", 0],
            },
        },
        "21": {"class_type": "VAEDecode", "inputs": {"samples": ["20", 0], "vae": ["4", 0]}},
        "22": {"class_type": "SaveImage", "inputs": {"images": ["21", 0], "filename_prefix": prefix}},
    }


def run_prompt(base_url: str, prompt: dict, timeout: int) -> dict:
    queued = request_json(
        base_url.rstrip("/") + "/prompt",
        {"prompt": prompt, "client_id": str(uuid.uuid4())},
        timeout=60,
    )
    prompt_id = queued.get("prompt_id")
    if not isinstance(prompt_id, str) or not prompt_id:
        raise RuntimeError(f"ComfyUI did not return a prompt id: {queued}")
    print(json.dumps({"queued": prompt_id}), flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        history = request_json(base_url.rstrip("/") + f"/history/{prompt_id}", timeout=30)
        record = history.get(prompt_id)
        if isinstance(record, dict):
            status = record.get("status") if isinstance(record.get("status"), dict) else {}
            if status.get("status_str") == "error":
                raise RuntimeError(json.dumps(status.get("messages") or [], ensure_ascii=False)[-3000:])
            if status.get("completed") or status.get("status_str") == "success":
                return record
        time.sleep(1)
    raise TimeoutError(f"ComfyUI prompt exceeded {timeout} seconds")


def download_output(base_url: str, record: dict, destination: Path) -> dict:
    output = record.get("outputs", {}).get("22", {})
    images = output.get("images") if isinstance(output, dict) else None
    if not isinstance(images, list) or not images:
        raise RuntimeError("ComfyUI SaveImage node produced no image")
    item = images[0]
    query = urllib.parse.urlencode(
        {
            "filename": item.get("filename", ""),
            "subfolder": item.get("subfolder", ""),
            "type": item.get("type", "output"),
        }
    )
    with urllib.request.urlopen(base_url.rstrip("/") + "/view?" + query, timeout=60) as response:
        destination.write_bytes(response.read())
    return item


def main() -> int:
    args = parse_args()
    if not 1 <= args.steps <= 100:
        raise SystemExit("--steps must be in 1..100")
    if not 0.0 <= args.cfg <= 20.0:
        raise SystemExit("--cfg must be in 0..20")
    if not 0.0 <= args.lora_strength <= 2.0:
        raise SystemExit("--lora-strength must be in 0..2")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "asset-studio.sprite-pose4-run/v1":
        raise SystemExit("Unsupported manifest schema")
    requests = manifest.get("requests")
    if not isinstance(requests, list) or len(requests) != 2:
        raise SystemExit("N-L-N-R manifest must contain exactly two generated-frame requests")

    info = request_json(args.server.rstrip("/") + "/object_info", timeout=30)
    missing = sorted(REQUIRED_NODES.difference(info))
    if missing:
        raise SystemExit("ComfyUI is missing required nodes: " + ", ".join(missing))

    run_id = uuid.uuid4().hex[:12]
    input_subfolder = f"asset_studio_pose4/{run_id}"
    master_path = Path(requests[0]["image_2"]).resolve()
    master_name = upload_image(args.server, master_path, input_subfolder)
    pose_names = {
        int(request["frame_index"]): upload_image(
            args.server, Path(request["image_1"]).resolve(), input_subfolder
        )
        for request in requests
    }

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    candidates = []
    for request in requests:
        frame_index = int(request["frame_index"])
        beat = str(request["beat"])
        prompt_text = request.get("backend_prompts", {}).get("refcontrol-flux2-klein4")
        if not isinstance(prompt_text, str) or not prompt_text:
            raise SystemExit(f"Frame {frame_index} lacks a RefControl backend prompt")
        prefix = f"asset_studio_pose4/{run_id}/frame_{frame_index:02d}_{beat}_seed_{args.seed}"
        graph = build_prompt(
            pose_names[frame_index],
            master_name,
            prompt_text,
            args.seed,
            args.steps,
            args.cfg,
            args.lora_strength,
            prefix,
        )
        record = run_prompt(args.server, graph, args.timeout)
        destination = output / f"frame_{frame_index:02d}_{beat}_seed_{args.seed}.png"
        remote = download_output(args.server, record, destination)
        candidates.append(
            {
                "frame_index": frame_index,
                "beat": beat,
                "seed": args.seed,
                "path": str(destination),
                "remote": remote,
            }
        )
        print(json.dumps({"completed": str(destination), "frame_index": frame_index}), flush=True)

    report = {
        "schema_version": "asset-studio.sprite-pose4-refcontrol-run/v1",
        "backend": "FLUX.2 Klein Base 4B + RefControl Pose LoRA",
        "run_id": run_id,
        "manifest": str(args.manifest.resolve()),
        "seed": args.seed,
        "steps": args.steps,
        "cfg": args.cfg,
        "lora_strength": args.lora_strength,
        "candidates": candidates,
        "semantic_review_required": True,
    }
    report_path = output / "refcontrol_run.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"success": True, "report": str(report_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
