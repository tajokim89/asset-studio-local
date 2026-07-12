#!/usr/bin/env python3
"""Generate one SE black-orc idle/walk sample through Asset Studio's HTTP API.

The successful path performs exactly two provider-backed requests:
1. text-to-image idle strip
2. reference-image walk strip using the idle result as the identity anchor

The checkpoint is resumable so a failed walk request does not spend another
credit regenerating the already accepted idle reference.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = os.environ.get("ASSET_STUDIO_URL", "http://127.0.0.1:4184").rstrip("/")
OUT = ROOT / "assets" / "generated" / "black_orc_se_sample"
STATE = OUT / "latest.json"

IDENTITY_PROMPT = """Create a production-ready pixel-art actor sprite strip for one original character.

Character identity lock:
- adult black-skinned orc; skin is charcoal/obsidian black, never green or olive
- cool slate-gray highlights keep facial planes, arms, hands, and legs readable against the dark outline
- broad muscular build, heavy brow, square jaw, two short ivory lower tusks, bald head, pointed ears
- worn dark-brown sleeveless leather tunic, simple belt, dark trousers, sturdy brown boots
- empty hands; no weapon, shield, backpack, jewelry, helmet, cape, or loose accessory
- preserve the exact same face, tusks, proportions, clothing, palette, outline, scale, and ground contact in every frame

Camera and layout lock:
- target direction is SE: front-right three-quarter view, body and feet turned toward screen-right while part of the face and chest remain visible
- exactly one direction only; never add other directional views
- crisp game-ready pixel art designed around a 32x32-pixel frame grid, hard pixel edges, no anti-aliasing
- full body and both feet visible in every cell; fixed root/pivot and identical ground baseline
- wide empty chroma-green gutters; no overlapping or touching adjacent cells"""

IDLE_PROMPT = IDENTITY_PROMPT + """

Action request:
- one horizontal 1x4 SE idle strip
- subtle breathing only: settle, breathe-up, settle-return, breathe-down
- feet stay planted; no stepping, turning, attack, or root drift
- first and last poses connect as a clean loop"""

WALK_PROMPT = IDENTITY_PROMPT + """

Use the supplied SE idle strip as the strict identity and style reference, then draw new complete poses.

Action request:
- one horizontal 1x6 SE walk strip
- continuous in-place walk with alternating left and right support phases
- opposite arm swing, visible foot contacts, readable passing poses, fixed root, and one ground baseline
- frames 1-3 and 4-6 must clearly show opposite support sides
- no skating, hopping, repeated same-side step, copied idle poses, or whole-body translation
- first and last poses connect as a clean loop"""

NEGATIVE_PROMPT = """green skin, olive skin, pale skin, human, elf, extra character, extra direction,
front-only view, side-only view, back view, weapon, shield, helmet, cape, text, numbers, watermark,
UI mockup, scene, floor, shadow panel, gradient background, painterly rendering, 3D render, blur,
anti-aliasing, cropped feet, overlapping cells, visible cell boxes, duplicated limbs, inconsistent costume,
identity drift, root drift, same leg phase in every walk frame, baked VFX, motion trails"""

STYLE_PROFILE = {
    "schema_version": "asset-studio.style-profile/v1",
    "id": "black-orc-sample",
    "name": "Black Orc Sample",
    "version": 1,
    "created_at": "2026-07-12T00:00:00.000Z",
    "updated_at": "2026-07-12T00:00:00.000Z",
    "palette": {
        "mode": "limited",
        "colors": [
            "#11151B", "#1C2229", "#2B333C", "#4A5662",
            "#352117", "#684328", "#A87843", "#D8C8A6",
        ],
    },
    "outline": {"mode": "dark", "width": 1, "color": "#11151B"},
    "shading": {"mode": "cel", "steps": 3, "light_direction": "top-left"},
    "material_treatment": {"mode": "matte", "detail": "medium"},
    "pixel_density": {"mode": "pixel-art", "scale": 1},
    "silhouette": {"mode": "readable", "complexity": "medium"},
    "contrast": {"mode": "high", "value": 0.78},
    "anti_aliasing": {"mode": "off"},
    "reference_assets": [],
    "forbidden_elements": ["text", "logo", "watermark", "green skin"],
    "family_overrides": {"sprite": {}, "tile": {}, "ui": {}, "object": {}},
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_state(value: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(STATE)


def read_state() -> dict:
    if not STATE.is_file():
        return {}
    try:
        value = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def post(endpoint: str, payload: dict) -> dict:
    request = urllib.request.Request(
        API_ROOT + endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        try:
            detail = json.loads(body)
        except json.JSONDecodeError:
            detail = {"error": body or str(error)}
        raise RuntimeError(f"{endpoint} returned HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach {API_ROOT}: {error.reason}") from error
    if not isinstance(result, dict) or not result.get("success") or not result.get("path"):
        raise RuntimeError(f"{endpoint} failed: {result}")
    return result


def payload_for(action: str, prompt: str) -> dict:
    return {
        "asset_family": "sprite",
        "asset_type": "character",
        "prompt": prompt,
        "negative": NEGATIVE_PROMPT,
        "preset": "pixel",
        "aspect_ratio": "square",
        "background_mode": "chroma_green",
        "no_baked_vfx": True,
        "style_profile": STYLE_PROFILE,
        "output": {"width": 512, "height": 512, "background": "chroma_green"},
        "sprite": {
            "output_profile_id": "generic-pixel-actor-v1",
            "animation_mode": action,
            "direction_mode": "single",
            "target_direction": "SE",
            "reference_direction": "SE",
            "chroma_mode": "global",
            # Deliberately non-authoritative values: the server profile must replace them.
            "frame_count": 999,
            "walk_frames": 999,
        },
    }


def stable_copy(result: dict, filename: str) -> Path:
    source = Path(result["path"])
    if not source.is_file():
        raise RuntimeError(f"Backend reported a missing artifact: {source}")
    destination = OUT / filename
    shutil.copy2(source, destination)
    return destination


def data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return "data:image/png;base64," + encoded


def start_managed_server(port: int) -> tuple[subprocess.Popen, object]:
    """Start the current checkout on a separate port and wait until it is ready."""
    global API_ROOT

    API_ROOT = f"http://127.0.0.1:{port}"
    hermes_python = Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python"
    python = os.environ.get("ASSET_STUDIO_PYTHON") or (
        str(hermes_python) if hermes_python.is_file() else sys.executable
    )
    OUT.mkdir(parents=True, exist_ok=True)
    log = (OUT / "managed_server.log").open("w", encoding="utf-8")
    environment = dict(os.environ)
    environment.update({"PORT": str(port), "PYTHONDONTWRITEBYTECODE": "1"})
    process = subprocess.Popen(
        [python, str(ROOT / "server.py")],
        cwd=ROOT,
        env=environment,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    deadline = time.monotonic() + 30
    last_error = "server did not respond"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log.flush()
            detail = (OUT / "managed_server.log").read_text(encoding="utf-8", errors="replace")
            log.close()
            raise RuntimeError(f"Managed server exited during startup:\n{detail[-2000:]}")
        try:
            with urllib.request.urlopen(API_ROOT + "/api/provider-health", timeout=2) as response:
                health = json.loads(response.read().decode("utf-8"))
            if health.get("available") or health.get("status") == "ready":
                return process, log
            last_error = str(health)
        except Exception as error:
            last_error = str(error)
        time.sleep(0.25)
    process.terminate()
    process.wait(timeout=5)
    log.close()
    raise RuntimeError(f"Managed server was not ready after 30 seconds: {last_error}")


def stop_managed_server(process: subprocess.Popen | None, log: object | None) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    if log is not None:
        log.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="discard a completed checkpoint and spend two new requests")
    parser.add_argument("--start-server", action="store_true", help="run this checkout on a temporary local port")
    parser.add_argument("--server-port", type=int, default=4185)
    args = parser.parse_args()

    state = {} if args.force else read_state()
    if state.get("status") == "complete":
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0

    managed_process = None
    managed_log = None
    if args.start_server:
        try:
            managed_process, managed_log = start_managed_server(args.server_port)
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1

    idle_path = Path(state.get("idle_path", "")) if state.get("idle_path") else None
    idle_result = state.get("idle_response") if isinstance(state.get("idle_response"), dict) else None

    try:
        if idle_path is None or not idle_path.is_file() or idle_result is None:
            idle_result = post("/api/generate", payload_for("idle", IDLE_PROMPT))
            idle_path = stable_copy(idle_result, "black_orc_se_idle_4f.png")
            state = {
                "status": "idle_ready",
                "updated_at": now(),
                "api_root": API_ROOT,
                "idle_path": str(idle_path),
                "idle_response": idle_result,
            }
            write_state(state)

        walk_payload = payload_for("walk", WALK_PROMPT)
        walk_payload["reference_image"] = data_url(idle_path)
        walk_result = post("/api/generate-reference", walk_payload)
        walk_path = stable_copy(walk_result, "black_orc_se_walk_6f.png")
        state.update({
            "status": "complete",
            "updated_at": now(),
            "walk_path": str(walk_path),
            "walk_response": walk_result,
        })
        write_state(state)
    except Exception as error:
        state.update({"status": "failed", "updated_at": now(), "error": str(error)})
        write_state(state)
        print(json.dumps(state, ensure_ascii=False, indent=2), file=sys.stderr)
        stop_managed_server(managed_process, managed_log)
        return 1

    stop_managed_server(managed_process, managed_log)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
