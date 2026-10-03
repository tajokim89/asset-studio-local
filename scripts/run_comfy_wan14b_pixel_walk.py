from __future__ import annotations

import argparse
import json
import time
import urllib.request
import uuid
from pathlib import Path


WALK_POSITIVE = """{direction} full-body pixel character walking in place in one continuous exact 17-frame video.
Begin walking immediately with no frozen hold. Complete one natural alternating two-step walk cycle across all 17 frames.
Both feet alternately leave the ground with clear contact and passing poses; do not move only one foot. Both relaxed arms
swing clearly in the opposite direction from the legs without lifting above the waist. End in a loop-ready pose close to
the starting gait phase. Locked camera, fixed character scale, fixed facing direction, and no character translation.
Keep the exact same face, black hair, navy patched work jacket, beige collar and cuffs, dark baggy patched trousers,
knee patch, navy shoes, crisp pixel-art edges, proportions, colors, and flat chroma green background."""

PIXEL_WALK_POSITIVE = """pix3lwalk, {direction} full-body character walk animation, pixel style looping walk animation.
The character walks in place with a natural alternating gait and opposite arm swing. Locked camera, fixed direction,
fixed scale, fixed foot baseline, and no translation. Preserve the exact face, black hair, navy patched work jacket,
beige collar and cuffs, dark baggy patched trousers, knee patch, navy shoes, proportions, palette, crisp pixel edges,
and flat chroma green background from the input image."""

IDLE_POSITIVE = """{direction} full-body pixel character standing in one exact 5-frame idle video.
Frame 1 is the neutral start pose. Frame 2 is a tiny inhale. Frame 3 is the breathing peak with only the chest and
jacket collar rising by about 2 pixels. Frame 4 settles back down. Frame 5 exactly repeats frame 1 as a loop-closure
frame. Both arms stay straight and pinned beside the torso; elbows do not bend, hands do not lift, and shoulder width
does not expand. Feet remain firmly planted throughout. Keep the face completely frozen in the approved neutral
expression for every frame: mouth closed, eyes open, eyebrows unchanged, hair unchanged, and head angle unchanged.
No blinking, lip movement, talking, singing, emotion change, or head tilt. Hands remain relaxed at the sides and never
swing. The only readable motion is the chest and jacket collar rising and falling slightly. The breathing
must be visible at sprite scale without walking, stepping, bouncing, or changing direction. Frame 5 returns to the same
neutral pose and expression as frame 1. Locked camera, fixed character scale, and fixed facing direction.
Keep the exact same face, black hair, navy patched work jacket, beige collar and cuffs, dark baggy patched trousers,
knee patch, navy shoes, crisp pixel-art edges, proportions, colors, and flat chroma green background."""

RUN_POSITIVE = """{direction} full-body pixel character running in place, strong readable run cycle.
Large alternating strides with clear airborne flight phases and energetic opposite arm drive.
The torso leans slightly in the fixed facing direction. Locked camera and fixed character scale.
Keep the exact same face, black hair, navy patched work jacket, beige collar and cuffs, dark baggy patched trousers,
knee patch, navy shoes, crisp pixel-art edges, proportions, colors, and flat chroma green background."""

COMMON_NEGATIVE = """dancing, turning, camera movement, zoom, crop, close-up, character redesign, clothing change,
missing limb, extra limb, fused legs, floating, background detail, floor, shadow, scenery, text, watermark, blur,
photorealistic"""

ACTION_NEGATIVE = {
    "idle": "facial animation, expression change, talking, singing, crying, worried face, mouth open, lip movement, blinking, eyes closed, eyebrow movement, head tilt, walking, running, stepping, foot travel, arm swing, arm lift, raised arms, elbow bend, shrug, hands away from thighs, waving, full-body translation, exaggerated bouncing, " + COMMON_NEGATIVE,
    "walk": "static pose, idle, frozen feet, pose hold, waiting, slow start, slow motion, tiny foot movement, shuffling, sliding feet, high kick, running, " + COMMON_NEGATIVE,
    "run": "static pose, idle, walking, slow motion, shuffling, sliding feet, no airborne phase, " + COMMON_NEGATIVE,
}

ACTION_POSITIVE = {
    "idle": IDLE_POSITIVE,
    "walk": WALK_POSITIVE,
    "run": RUN_POSITIVE,
}

ACTION_LENGTH = {"idle": 5, "walk": 17, "run": 17}

DIRECTION_TEXT = {
    "S": "front view facing straight toward the viewer/south",
    "SE": "front-right three-quarter view facing screen-right and toward the viewer/southeast at a fixed 45-degree angle",
    "E": "strict right profile facing screen-right/east",
    "NE": "back-right three-quarter view facing screen-right and away from the viewer/northeast at a fixed 45-degree angle",
    "N": "strict back view facing directly away from the viewer/north",
    "NW": "back-left three-quarter view facing screen-left and away from the viewer/northwest at a fixed 45-degree angle",
    "W": "strict left profile facing screen-left/west",
    "SW": "front-left three-quarter view facing screen-left and toward the viewer/southwest at a fixed 45-degree angle",
}


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


def workflow(
    image_name: str,
    seed: int,
    strength: float,
    output_subfolder: str,
    high_lora: str,
    low_lora: str,
    shift: float,
    cfg: float,
    sampler: str,
    direction: str,
    action: str,
    length: int,
    profile: str,
) -> dict:
    positive_template = PIXEL_WALK_POSITIVE if action == "walk" and profile == "pixel_walk" else ACTION_POSITIVE[action]
    positive_text = positive_template.format(direction=DIRECTION_TEXT[direction])
    negative_text = ACTION_NEGATIVE[action]
    video_inputs = {
        "positive": ["8", 0],
        "negative": ["9", 0],
        "vae": ["10", 0],
        "width": 512,
        "height": 512,
        "length": length,
        "batch_size": 1,
        "start_image": ["11", 0],
    }
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "Wan2.2-I2V-A14B-HighNoise-Q4_K_S.gguf"}},
        "2": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "Wan2.2-I2V-A14B-LowNoise-Q4_K_S.gguf"}},
        "3": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": high_lora, "strength_model": strength}},
        "4": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["2", 0], "lora_name": low_lora, "strength_model": strength}},
        "5": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["3", 0], "shift": shift}},
        "6": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["4", 0], "shift": shift}},
        "7": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"}},
        "8": {"class_type": "CLIPTextEncode", "inputs": {"text": positive_text, "clip": ["7", 0]}},
        "9": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_text, "clip": ["7", 0]}},
        "10": {"class_type": "VAELoader", "inputs": {"vae_name": "Wan2.1_VAE.safetensors"}},
        "11": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "12": {"class_type": "WanImageToVideo", "inputs": video_inputs},
        "13": {"class_type": "KSamplerAdvanced", "inputs": {"model": ["5", 0], "add_noise": "enable", "noise_seed": seed, "steps": 20, "cfg": cfg, "sampler_name": sampler, "scheduler": "simple", "positive": ["12", 0], "negative": ["12", 1], "latent_image": ["12", 2], "start_at_step": 0, "end_at_step": 10, "return_with_leftover_noise": "enable"}},
        "14": {"class_type": "KSamplerAdvanced", "inputs": {"model": ["6", 0], "add_noise": "disable", "noise_seed": 0, "steps": 20, "cfg": cfg, "sampler_name": sampler, "scheduler": "simple", "positive": ["12", 0], "negative": ["12", 1], "latent_image": ["13", 0], "start_at_step": 10, "end_at_step": 10000, "return_with_leftover_noise": "disable"}},
        "15": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["10", 0]}},
        "16": {"class_type": "SaveImage", "inputs": {"images": ["15", 0], "filename_prefix": f"asset_studio/{output_subfolder}/frame"}},
        "17": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["15", 0], "frame_rate": 16.0, "loop_count": 0, "filename_prefix": f"asset_studio/{output_subfolder}/preview", "format": "image/gif", "pingpong": False, "save_output": True}},
        "18": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["15", 0], "frame_rate": 16.0, "loop_count": 0, "filename_prefix": f"asset_studio/{output_subfolder}/preview", "format": "video/h264-mp4", "pix_fmt": "yuv420p", "crf": 19, "save_metadata": True, "trim_to_audio": False, "pingpong": False, "save_output": True}},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--image-name", default="chairman_wan_walk_input.png")
    parser.add_argument("--seed", type=int, default=2608021436)
    parser.add_argument("--strength", type=float, default=1.0)
    parser.add_argument("--output-subfolder", default="chairman_wan14b_pixel_walk")
    parser.add_argument("--high-lora", default="wan2.2_animate_adapter_model.safetensors")
    parser.add_argument("--low-lora", default="wan2.2_animate_adapter_model.safetensors")
    parser.add_argument("--shift", type=float, default=5.0)
    parser.add_argument("--cfg", type=float, default=1.1)
    parser.add_argument("--sampler", default="ddim")
    parser.add_argument("--direction", choices=tuple(DIRECTION_TEXT), default="S")
    parser.add_argument("--action", choices=tuple(ACTION_POSITIVE), default="walk")
    parser.add_argument("--length", type=int)
    parser.add_argument("--profile", choices=("pixel_animate", "pixel_walk"), default="pixel_animate")
    parser.add_argument("--timeout", type=int, default=2400)
    parser.add_argument("--history-out", type=Path)
    args = parser.parse_args()
    length = args.length if args.length is not None else ACTION_LENGTH[args.action]

    queued = request_json(
        f"{args.server}/prompt",
        {
            "prompt": workflow(
                args.image_name,
                args.seed,
                args.strength,
                args.output_subfolder,
                args.high_lora,
                args.low_lora,
                args.shift,
                args.cfg,
                args.sampler,
                args.direction,
                args.action,
                length,
                args.profile,
            ),
            "client_id": str(uuid.uuid4()),
        },
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
        time.sleep(3)
    raise TimeoutError(f"ComfyUI did not finish within {args.timeout}s: {prompt_id}")


if __name__ == "__main__":
    main()
