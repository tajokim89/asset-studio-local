from __future__ import annotations

import argparse
import json
import time
import urllib.request
import uuid
from pathlib import Path


POSITIVE = """A single pixel art game character performs a clean in-place looping walk cycle.
Full body remains centered and fully visible. Fixed front-facing camera, fixed scale, no camera movement.
Natural alternating heel-to-toe steps, knees bend, hips shift slightly, and both arms swing opposite the legs.
Preserve exactly the same young Korean male face, short black hair, navy patched work jacket, beige collar and cuffs,
dark baggy patched trousers, and navy shoes from the input image. Preserve crisp pixel-art edges and proportions.
The perfectly flat solid chroma green background remains unchanged. Animation only; no scene change."""

NEGATIVE = """camera movement, zoom, pan, rotation, crop, close-up, character redesign, different clothes,
missing limb, extra limb, fused legs, sliding feet, floating, dancing, running, turning around, side view,
background detail, shadow, floor, scenery, text, watermark, blur, smooth painting, photorealistic"""


def request_json(url: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def workflow(image_name: str, seed: int) -> dict:
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_ti2v_5B_fp16.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": POSITIVE, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": ["2", 0]}},
        "6": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "7": {"class_type": "Wan22ImageToVideoLatent", "inputs": {"vae": ["3", 0], "width": 512, "height": 512, "length": 25, "batch_size": 1, "start_image": ["6", 0]}},
        "8": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 8.0}},
        "9": {"class_type": "KSampler", "inputs": {"model": ["8", 0], "seed": seed, "steps": 20, "cfg": 5.0, "sampler_name": "uni_pc", "scheduler": "simple", "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["7", 0], "denoise": 1.0}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "asset_studio/chairman_wan5b_walk/frame"}},
        "12": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["10", 0], "frame_rate": 8.0, "loop_count": 0, "filename_prefix": "asset_studio/chairman_wan5b_walk/preview", "format": "image/gif", "pingpong": False, "save_output": True}},
        "13": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["10", 0], "frame_rate": 8.0, "loop_count": 0, "filename_prefix": "asset_studio/chairman_wan5b_walk/preview", "format": "video/h264-mp4", "pix_fmt": "yuv420p", "crf": 19, "save_metadata": True, "trim_to_audio": False, "pingpong": False, "save_output": True}},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--image-name", default="chairman_wan_walk_input.png")
    parser.add_argument("--seed", type=int, default=2608020636)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--history-out", type=Path)
    args = parser.parse_args()

    client_id = str(uuid.uuid4())
    queued = request_json(
        f"{args.server}/prompt",
        {"prompt": workflow(args.image_name, args.seed), "client_id": client_id},
    )
    prompt_id = queued["prompt_id"]
    print(f"queued {prompt_id}", flush=True)

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        history = request_json(f"{args.server}/history/{prompt_id}")
        if prompt_id in history:
            entry = history[prompt_id]
            if args.history_out:
                args.history_out.parent.mkdir(parents=True, exist_ok=True)
                args.history_out.write_text(json.dumps(entry, indent=2), encoding="utf-8")
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(json.dumps(status, ensure_ascii=False))
            print(json.dumps(entry.get("outputs", {}), ensure_ascii=False), flush=True)
            return
        time.sleep(2)
    raise TimeoutError(f"ComfyUI did not finish within {args.timeout}s: {prompt_id}")


if __name__ == "__main__":
    main()
