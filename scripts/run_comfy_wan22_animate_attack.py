from __future__ import annotations

import argparse
import json
import time
import urllib.request
import uuid
from pathlib import Path


POSITIVE = """Front-facing full-body pixel-art male game character performs exactly one compact dagger attack in place.
Follow the supplied pose video exactly: ready guard, brief anticipation, fast horizontal slash across the body,
clear follow-through, then recover to the identical ready guard. The same short silver dagger stays rigidly attached
to his right hand in every frame. Lock the exact blade length, straight blade shape, brown hilt, grip, hand, character
identity, neutral face, black hair, navy patched work jacket, beige collar and cuffs, dark baggy patched trousers,
knee patch, navy shoes, pixel density, front direction, camera, scale, foot baseline, and flat chroma green background.
Feet stay planted. One readable game attack cycle, no movement effect and no weapon trail."""

NEGATIVE = """bent dagger, curved dagger, rubber blade, changing blade length, oversized sword, weapon swap,
missing dagger, disappearing dagger, detached weapon, floating weapon, extra weapon, wrong hand, broken hand,
extra fingers, fused arms, extra limbs, missing limbs, face change, clothing change, direction change, body rotation,
walking, running, jumping, foot travel, camera motion, zoom, crop, floor, shadow, scenery, fire, magic, slash trail,
motion effect, glow, text, watermark, blur, photorealistic"""


def request_json(url: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def pose_nodes(pose_video: str, output_subfolder: str) -> dict:
    return {
        "20": {
            "class_type": "VHS_LoadVideoPath",
            "inputs": {
                "video": pose_video,
                "force_rate": 16.0,
                "custom_width": 512,
                "custom_height": 512,
                "frame_load_cap": 17,
                "skip_first_frames": 0,
                "select_every_nth": 1,
                "format": "None",
            },
        },
        "21": {
            "class_type": "DWPreprocessor",
            "inputs": {
                "image": ["20", 0],
                "detect_hand": "enable",
                "detect_body": "enable",
                "detect_face": "disable",
                "resolution": 512,
                "bbox_detector": "yolox_l.onnx",
                "pose_estimator": "dw-ll_ucoco_384_bs5.torchscript.pt",
                "scale_stick_for_xinsr_cn": "disable",
            },
        },
        "22": {
            "class_type": "DWPreprocessor",
            "inputs": {
                "image": ["20", 0],
                "detect_hand": "disable",
                "detect_body": "disable",
                "detect_face": "enable",
                "resolution": 512,
                "bbox_detector": "yolox_l.onnx",
                "pose_estimator": "dw-ll_ucoco_384_bs5.torchscript.pt",
                "scale_stick_for_xinsr_cn": "disable",
            },
        },
        "23": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["21", 0],
                "filename_prefix": f"asset_studio/{output_subfolder}/pose/frame",
            },
        },
        "24": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["21", 0],
                "frame_rate": 16.0,
                "loop_count": 0,
                "filename_prefix": f"asset_studio/{output_subfolder}/pose/preview",
                "format": "image/gif",
                "pingpong": False,
                "save_output": True,
            },
        },
        "25": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["22", 0],
                "frame_rate": 16.0,
                "loop_count": 0,
                "filename_prefix": f"asset_studio/{output_subfolder}/face/preview",
                "format": "image/gif",
                "pingpong": False,
                "save_output": True,
            },
        },
    }


def workflow(
    reference_image: str,
    pose_video: str,
    guide_frames_dir: str | None,
    seed: int,
    output_subfolder: str,
    pose_only: bool,
    control_only: bool,
) -> dict:
    nodes = pose_nodes(pose_video, output_subfolder)
    if pose_only:
        return nodes

    if guide_frames_dir:
        nodes.update(
            {
                "26": {
                    "class_type": "VHS_LoadImagesPath",
                    "inputs": {
                        "directory": guide_frames_dir,
                        "image_load_cap": 17,
                        "skip_first_images": 0,
                        "select_every_nth": 1,
                    },
                },
                "27": {
                    "class_type": "ImageColorToMask",
                    "inputs": {"image": ["26", 0], "color": 65280},
                },
                "28": {"class_type": "InvertMask", "inputs": {"mask": ["27", 0]}},
                "29": {
                    "class_type": "GrowMask",
                    "inputs": {"mask": ["28", 0], "expand": -20, "tapered_corners": False},
                },
                "30": {
                    "class_type": "GrowMask",
                    "inputs": {"mask": ["29", 0], "expand": 24, "tapered_corners": False},
                },
                "31": {"class_type": "MaskToImage", "inputs": {"mask": ["30", 0]}},
                "32": {
                    "class_type": "SaveImage",
                    "inputs": {
                        "images": ["31", 0],
                        "filename_prefix": f"asset_studio/{output_subfolder}/mix-mask/frame",
                    },
                },
                "33": {
                    "class_type": "VHS_VideoCombine",
                    "inputs": {
                        "images": ["31", 0],
                        "frame_rate": 16.0,
                        "loop_count": 0,
                        "filename_prefix": f"asset_studio/{output_subfolder}/mix-mask/preview",
                        "format": "image/gif",
                        "pingpong": False,
                        "save_output": True,
                    },
                },
            }
        )
        if control_only:
            return nodes

    nodes.update(
        {
            "1": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": "Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors",
                    "weight_dtype": "default",
                },
            },
            "2": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 5.0}},
            "3": {
                "class_type": "CLIPLoader",
                "inputs": {
                    "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                    "type": "wan",
                    "device": "default",
                },
            },
            "4": {"class_type": "CLIPTextEncode", "inputs": {"text": POSITIVE, "clip": ["3", 0]}},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": ["3", 0]}},
            "6": {"class_type": "VAELoader", "inputs": {"vae_name": "Wan2.1_VAE.safetensors"}},
            "7": {
                "class_type": "VHS_LoadImagePath",
                "inputs": {"image": reference_image, "custom_width": 512, "custom_height": 512},
            },
            "8": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "clip_vision_h.safetensors"}},
            "9": {
                "class_type": "CLIPVisionEncode",
                "inputs": {"clip_vision": ["8", 0], "image": ["7", 0], "crop": "none"},
            },
            "10": {
                "class_type": "WanAnimateToVideo",
                "inputs": {
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "vae": ["6", 0],
                    "width": 512,
                    "height": 512,
                    "length": 17,
                    "batch_size": 1,
                    "continue_motion_max_frames": 5,
                    "video_frame_offset": 0,
                    "clip_vision_output": ["9", 0],
                    "reference_image": ["7", 0],
                    "face_video": ["22", 0],
                    "pose_video": ["21", 0],
                    **(
                        {"background_video": ["26", 0], "character_mask": ["30", 0]}
                        if guide_frames_dir
                        else {}
                    ),
                },
            },
            "11": {
                "class_type": "KSamplerAdvanced",
                "inputs": {
                    "model": ["2", 0],
                    "add_noise": "enable",
                    "noise_seed": seed,
                    "steps": 20,
                    "cfg": 1.1,
                    "sampler_name": "ddim",
                    "scheduler": "simple",
                    "positive": ["10", 0],
                    "negative": ["10", 1],
                    "latent_image": ["10", 2],
                    "start_at_step": 0,
                    "end_at_step": 10000,
                    "return_with_leftover_noise": "disable",
                },
            },
            "12": {
                "class_type": "TrimVideoLatent",
                "inputs": {"samples": ["11", 0], "trim_amount": ["10", 3]},
            },
            "13": {
                "class_type": "VAEDecodeTiled",
                "inputs": {
                    "samples": ["12", 0],
                    "vae": ["6", 0],
                    "tile_size": 256,
                    "overlap": 32,
                    "temporal_size": 8,
                    "temporal_overlap": 4,
                },
            },
            "14": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["13", 0],
                    "filename_prefix": f"asset_studio/{output_subfolder}/frame",
                },
            },
            "15": {
                "class_type": "VHS_VideoCombine",
                "inputs": {
                    "images": ["13", 0],
                    "frame_rate": 16.0,
                    "loop_count": 0,
                    "filename_prefix": f"asset_studio/{output_subfolder}/preview",
                    "format": "image/gif",
                    "pingpong": False,
                    "save_output": True,
                },
            },
            "16": {
                "class_type": "VHS_VideoCombine",
                "inputs": {
                    "images": ["13", 0],
                    "frame_rate": 16.0,
                    "loop_count": 0,
                    "filename_prefix": f"asset_studio/{output_subfolder}/preview",
                    "format": "video/h264-mp4",
                    "pix_fmt": "yuv420p",
                    "crf": 19,
                    "save_metadata": True,
                    "trim_to_audio": False,
                    "pingpong": False,
                    "save_output": True,
                },
            },
        }
    )
    return nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--reference-image", type=Path, required=True)
    parser.add_argument("--pose-video", type=Path, required=True)
    parser.add_argument("--guide-frames-dir", type=Path)
    parser.add_argument("--seed", type=int, default=2608022201)
    parser.add_argument("--output-subfolder", default="chairman_wan22_animate_attack_v2")
    parser.add_argument("--pose-only", action="store_true")
    parser.add_argument("--control-only", action="store_true")
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--history-out", type=Path)
    args = parser.parse_args()

    queued = request_json(
        f"{args.server}/prompt",
        {
            "prompt": workflow(
                str(args.reference_image.resolve()),
                str(args.pose_video.resolve()),
                str(args.guide_frames_dir.resolve()) if args.guide_frames_dir else None,
                args.seed,
                args.output_subfolder,
                args.pose_only,
                args.control_only,
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
