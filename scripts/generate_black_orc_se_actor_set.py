#!/usr/bin/env python3
"""Generate a resumable SE black-orc actor set through Asset Studio's page backend.

The pilot stage spends only four provider calls: one Direction Master plus one
high-risk pose from idle, walk, and attack.  The all stage resumes from that
checkpoint and fills every profile-defined frame.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
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
sys.path.insert(0, str(ROOT))

from asset_studio.actor_blueprint import (  # noqa: E402
    render_pose_blueprint_png,
    se_attack_blueprints,
    se_idle_blueprints,
    se_walk_blueprints,
)


API_ROOT = os.environ.get("ASSET_STUDIO_URL", "http://127.0.0.1:4184").rstrip("/")
OUT = ROOT / "assets" / "generated" / "black_orc_se_v2"
MASTER_DIR = OUT / "master"
GUIDE_DIR = OUT / "pose_guides"
FRAME_DIR = OUT / "source_frames"
STATE_PATH = OUT / "manifest.json"

CHARACTER_PROMPT = """One original adult black-skinned muscular orc game character.
His skin is charcoal/obsidian black, never green or olive, with cool slate-gray highlights that keep the face, arms, hands, and legs readable against a near-black outline. He has an extremely broad athletic torso, thick but anatomically coherent arms and legs, a heavy brow, square jaw, bald head, pointed ears, and two short ivory lower tusks. He wears the same worn dark-brown sleeveless leather tunic, simple belt, dark trousers, and sturdy brown boots in every image. He is unarmed with empty hands and has no shield, helmet, cape, backpack, jewelry, or loose accessory."""

NEGATIVE_PROMPT = """green skin, olive skin, pale skin, human, elf, extra character, extra head,
extra arm, extra hand, extra leg, extra foot, missing hand, missing foot, fused limb, detached limb,
finger fan, claw blob, melted fist, twisted ankle, merged boots, broken knee, deformed anatomy,
weapon, shield, helmet, cape, backpack, jewelry, identity drift, costume change, direction drift,
front-only view, side-only view, back view, cropped body, cropped feet, floor, cast shadow, scene,
sprite sheet, contact sheet, grid, labels, text, numbers, watermark, VFX, motion trail, blur,
anti-aliasing, painterly rendering, 3D render, gradient background"""

MOTION_DIRECTIVES = {
    "idle": "Unarmed subtle breathing only. Both feet stay planted and both empty hands remain relaxed and anatomically connected.",
    "walk": "Unarmed in-place walk. Alternate support feet and opposite arm swing while both empty hands remain compact readable fists.",
    "attack": "Unarmed heavy right-handed punch; no weapon. The right fist, wrist, elbow, shoulder, torso rotation, hips, and planted feet drive one coherent strike.",
}

BLUEPRINT_FACTORIES = {
    "idle": se_idle_blueprints,
    "walk": se_walk_blueprints,
    "attack": se_attack_blueprints,
}

PILOT_FRAMES = (("idle", 1), ("walk", 0), ("attack", 3))
PIPELINE_CONTRACT_VERSION = "black-orc-se-frame-blueprint/v2"
FRAME_PROMPT_CONTRACT_VERSION = "black-orc-se-frame-prompt/v3-screen-space-contact"
REQUIRED_FRAME_VISUAL_CHECKS = {
    "identity",
    "direction",
    "hand_integrity",
    "foot_integrity",
    "joint_coherence",
    "pose_match",
}
REQUIRED_MASTER_VISUAL_CHECKS = {
    "single_character",
    "identity",
    "direction",
    "hand_integrity",
    "foot_integrity",
    "joint_coherence",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_state() -> dict:
    if not STATE_PATH.is_file():
        return {
            "schema_version": "asset-studio.actor-generation-run/v1",
            "status": "new",
            "character_id": "black-muscular-orc",
            "direction": "SE",
            "frames": {},
        }
    try:
        value = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read generation manifest: {error}") from error
    if not isinstance(value, dict) or value.get("schema_version") != "asset-studio.actor-generation-run/v1":
        raise RuntimeError("Generation manifest has an incompatible schema")
    value.setdefault("frames", {})
    return value


def write_state(state: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now()
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(STATE_PATH)


def canonical_digest(value: dict) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record_visual_qa(
    state: dict,
    target: str,
    *,
    passed: bool,
    checks: dict[str, str],
    notes: list[str],
) -> None:
    if target == "master":
        record = state.get("master")
        required = REQUIRED_MASTER_VISUAL_CHECKS
    else:
        try:
            action, raw_index = target.split(":", 1)
            index = int(raw_index)
        except (ValueError, TypeError) as error:
            raise RuntimeError("QA target must be master or ACTION:INDEX") from error
        record = state.get("frames", {}).get(action, {}).get(str(index))
        required = REQUIRED_FRAME_VISUAL_CHECKS
    if not isinstance(record, dict):
        raise RuntimeError(f"No generated artifact exists for QA target {target}")
    artifact = Path(str(record.get("path", "")))
    if not artifact.is_file():
        raise RuntimeError(f"QA target artifact is missing: {artifact}")
    if record.get("artifact_sha256") != file_digest(artifact):
        raise RuntimeError("QA target artifact digest does not match the generation checkpoint")
    if passed:
        missing = sorted(required - set(checks))
        failed = sorted(name for name, status in checks.items() if status != "PASS")
        if missing or failed:
            raise RuntimeError(
                f"PASS requires all visual checks; missing={missing}, failed={failed}"
            )
    record["visual_qa"] = {
        "status": "PASS" if passed else "FAIL",
        "checks": dict(sorted(checks.items())),
        "notes": list(notes),
        "reviewer": "codex-visual-inspection",
        "reviewed_at": now(),
        "artifact_sha256": file_digest(artifact),
    }
    record["export_ready"] = False
    state["status"] = "visual-qa-recorded"
    write_state(state)


def data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return "data:image/png;base64," + encoded


def post(endpoint: str, payload: dict) -> dict:
    request = urllib.request.Request(
        API_ROOT + endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
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


def copy_backend_artifact(result: dict, destination: Path) -> Path:
    source = Path(str(result["path"]))
    if not source.is_file():
        raise RuntimeError(f"Backend reported a missing artifact: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def direction_master_request_digest(state: dict) -> str:
    return canonical_digest({
        "contract": PIPELINE_CONTRACT_VERSION,
        "stage": "direction-master",
        "prompt": CHARACTER_PROMPT,
        "negative": NEGATIVE_PROMPT,
        "direction": "SE",
        "image_model": state.get("image_model"),
    })


def ensure_pose_guide(action: str, blueprint: dict) -> Path:
    destination = GUIDE_DIR / f"se_{action}_{blueprint['frame_index']:02d}_{blueprint['beat_id']}.png"
    expected = render_pose_blueprint_png(blueprint, scale=16)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.is_file() or destination.read_bytes() != expected:
        destination.write_bytes(expected)
    return destination


def generate_master(state: dict, *, force: bool = False) -> Path:
    existing = state.get("master") if isinstance(state.get("master"), dict) else None
    existing_path = Path(existing.get("path", "")) if existing else None
    request_digest = direction_master_request_digest(state)
    if not force and existing_path is not None and existing_path.is_file():
        if existing.get("request_digest") != request_digest:
            raise RuntimeError("Direction Master checkpoint is stale; use --force-master deliberately")
        return existing_path
    result = post("/api/generate-actor-master", {
        "prompt": CHARACTER_PROMPT,
        "negative": NEGATIVE_PROMPT,
        "direction": "SE",
        "background_mode": "chroma_green",
    })
    path = copy_backend_artifact(result, MASTER_DIR / "black_orc_se_direction_master.png")
    state["master"] = {
        "path": str(path),
        "artifact_sha256": file_digest(path),
        "request_digest": request_digest,
        "response": result,
        "deterministic_qa": result.get("deterministic_qa"),
        "visual_qa": {"status": "PENDING", "checks": {}, "notes": []},
        "export_ready": False,
        "generated_at": now(),
    }
    state["status"] = "master-ready"
    write_state(state)
    return path


def adopt_existing_master(state: dict, source: Path) -> Path:
    """Checkpoint a provider artifact that already passed through the page endpoint."""
    import server

    source = source.expanduser().resolve()
    if not source.is_file():
        raise RuntimeError(f"Adopted Direction Master does not exist: {source}")
    out, qa = server.postprocess_actor_single_frame_bytes(
        source.read_bytes(),
        background_mode="none",
    )
    deterministic_pass = bool(
        qa["single_frame_qa"]["pass"] and qa["cleanup_qa"]["pass"]
    )
    if not deterministic_pass:
        raise RuntimeError(f"Adopted Direction Master failed deterministic QA: {qa}")
    path = MASTER_DIR / "black_orc_se_direction_master.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)
    state["master"] = {
        "path": str(path),
        "artifact_sha256": file_digest(path),
        "request_digest": direction_master_request_digest(state),
        "response": {
            "provider_success": True,
            "provider": "hermes",
            "model": state.get("image_model"),
            "method": "adopt-existing-page-backend-artifact",
            "source_path": str(source),
        },
        "deterministic_qa": {"status": "PASS", "details": qa},
        "visual_qa": {"status": "PENDING", "checks": {}, "notes": []},
        "export_ready": False,
        "generated_at": now(),
    }
    state["status"] = "master-ready"
    write_state(state)
    return path


def generated_frame(state: dict, action: str, frame_index: int) -> Path | None:
    record = state.get("frames", {}).get(action, {}).get(str(frame_index))
    if not isinstance(record, dict):
        return None
    path = Path(str(record.get("path", "")))
    return path if path.is_file() else None


def require_visual_qa_before_new_call(
    state: dict,
    *,
    excluding: tuple[str, int] | None = None,
) -> None:
    master = state.get("master")
    master_status = master.get("visual_qa", {}).get("status") if isinstance(master, dict) else None
    if master_status != "PASS":
        raise RuntimeError("Direction Master visual QA must be PASS before generating a frame")
    for action, frames in state.get("frames", {}).items():
        if not isinstance(frames, dict):
            continue
        for raw_index, record in frames.items():
            try:
                key = (action, int(raw_index))
            except (TypeError, ValueError):
                continue
            if key == excluding or not isinstance(record, dict):
                continue
            if record.get("visual_qa", {}).get("status") != "PASS":
                raise RuntimeError(
                    f"Visual QA for {action}:{raw_index} must be PASS before another provider call"
                )


def generate_frame(state: dict, master_path: Path, action: str, blueprint: dict, *, force: bool = False) -> Path:
    frame_index = blueprint["frame_index"]
    existing = generated_frame(state, action, frame_index)
    guide_path = ensure_pose_guide(action, blueprint)
    request_digest = canonical_digest({
        "contract": FRAME_PROMPT_CONTRACT_VERSION,
        "stage": "actor-frame",
        "character_prompt": CHARACTER_PROMPT,
        "negative": NEGATIVE_PROMPT,
        "motion_directive": MOTION_DIRECTIVES[action],
        "direction": "SE",
        "action": action,
        "frame_index": frame_index,
        "pose_blueprint": blueprint,
        "master_sha256": file_digest(master_path),
        "image_model": state.get("image_model"),
    })
    current_record = state.get("frames", {}).get(action, {}).get(str(frame_index), {})
    if not force and existing is not None:
        if current_record.get("request_digest") != request_digest:
            raise RuntimeError(
                f"Frame checkpoint {action}:{frame_index} is stale; use --force-frame {action}:{frame_index} deliberately"
            )
        return existing
    require_visual_qa_before_new_call(state, excluding=(action, frame_index))
    result = post("/api/generate-actor-frame", {
        "prompt": CHARACTER_PROMPT,
        "negative": NEGATIVE_PROMPT,
        "direction": "SE",
        "action": action,
        "frame_index": frame_index,
        "direction_master": data_url(master_path),
        "pose_blueprint": blueprint,
        "motion_directive": MOTION_DIRECTIVES[action],
        "background_mode": "chroma_green",
        "output_profile_id": "generic-pixel-actor-v1",
    })
    filename = f"black_orc_se_{action}_{frame_index:02d}_{blueprint['beat_id']}.png"
    path = copy_backend_artifact(result, FRAME_DIR / action / filename)
    state.setdefault("frames", {}).setdefault(action, {})[str(frame_index)] = {
        "beat": blueprint["beat_id"],
        "path": str(path),
        "pose_guide": str(guide_path),
        "artifact_sha256": file_digest(path),
        "request_digest": request_digest,
        "response": result,
        "deterministic_qa": result.get("deterministic_qa"),
        "visual_qa": {"status": "PENDING", "checks": {}, "notes": []},
        "export_ready": False,
        "generated_at": now(),
    }
    state["status"] = "frames-in-progress"
    write_state(state)
    return path


def start_managed_server(port: int, image_model: str) -> tuple[subprocess.Popen, object]:
    global API_ROOT

    API_ROOT = f"http://127.0.0.1:{port}"
    hermes_python = Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python"
    python = os.environ.get("ASSET_STUDIO_PYTHON") or (
        str(hermes_python) if hermes_python.is_file() else sys.executable
    )
    OUT.mkdir(parents=True, exist_ok=True)
    log = (OUT / "managed_server.log").open("w", encoding="utf-8")
    environment = dict(os.environ)
    environment.update({
        "PORT": str(port),
        "PYTHONDONTWRITEBYTECODE": "1",
        "OPENAI_IMAGE_MODEL": image_model,
    })
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
            raise RuntimeError(f"Managed server exited during startup:\n{detail[-3000:]}")
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


def selected_frames(
    stage: str,
    explicit_frames: tuple[tuple[str, int], ...] = (),
) -> tuple[tuple[str, int], ...]:
    if explicit_frames:
        return explicit_frames
    if stage == "master":
        return ()
    if stage == "pilot":
        return PILOT_FRAMES
    return tuple(
        (action, blueprint["frame_index"])
        for action, factory in BLUEPRINT_FACTORIES.items()
        for blueprint in factory()
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("master", "pilot", "all"), default="master")
    parser.add_argument("--start-server", action="store_true")
    parser.add_argument("--server-port", type=int, default=4186)
    parser.add_argument(
        "--image-model",
        choices=("gpt-image-2-low", "gpt-image-2-medium", "gpt-image-2-high"),
        default="gpt-image-2-high",
    )
    parser.add_argument("--force-master", action="store_true")
    parser.add_argument(
        "--adopt-master",
        type=Path,
        help="checkpoint an already generated page-backend master without a provider call",
    )
    parser.add_argument(
        "--frame",
        action="append",
        default=[],
        metavar="ACTION:INDEX",
        help="generate only this frame; repeat deliberately for more than one",
    )
    parser.add_argument(
        "--force-frame",
        action="append",
        default=[],
        metavar="ACTION:INDEX",
        help="regenerate one checkpointed frame",
    )
    parser.add_argument(
        "--record-qa",
        metavar="TARGET",
        help="record visual QA for master or ACTION:INDEX without calling the provider",
    )
    qa_verdict = parser.add_mutually_exclusive_group()
    qa_verdict.add_argument("--qa-pass", action="store_true")
    qa_verdict.add_argument("--qa-fail", action="store_true")
    parser.add_argument(
        "--qa-check",
        action="append",
        default=[],
        metavar="NAME=PASS|FAIL",
    )
    parser.add_argument("--qa-note", action="append", default=[])
    args = parser.parse_args()

    if args.record_qa:
        if not args.qa_pass and not args.qa_fail:
            parser.error("--record-qa requires --qa-pass or --qa-fail")
        checks = {}
        for value in args.qa_check:
            try:
                name, status = value.split("=", 1)
            except ValueError:
                parser.error(f"invalid --qa-check {value!r}; expected NAME=PASS|FAIL")
            name = name.strip().lower()
            status = status.strip().upper()
            if not name or status not in {"PASS", "FAIL"}:
                parser.error(f"invalid --qa-check {value!r}; expected NAME=PASS|FAIL")
            checks[name] = status
        try:
            state = read_state()
            record_visual_qa(
                state,
                args.record_qa,
                passed=args.qa_pass,
                checks=checks,
                notes=[str(note).strip() for note in args.qa_note if str(note).strip()],
            )
        except RuntimeError as error:
            parser.error(str(error))
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    if args.qa_pass or args.qa_fail or args.qa_check or args.qa_note:
        parser.error("QA verdict/check/note options require --record-qa")

    def parse_frame_selectors(values: list[str], option: str) -> tuple[tuple[str, int], ...]:
        parsed = []
        for value in values:
            try:
                action, raw_index = value.split(":", 1)
                index = int(raw_index)
            except (ValueError, TypeError):
                parser.error(f"invalid {option} {value!r}; expected ACTION:INDEX")
            if action not in BLUEPRINT_FACTORIES:
                parser.error(f"unknown action in {option}: {action}")
            if not 0 <= index < len(BLUEPRINT_FACTORIES[action]()):
                parser.error(f"frame index outside {action} blueprint sequence in {option}: {index}")
            parsed.append((action, index))
        return tuple(parsed)

    explicit_frames = parse_frame_selectors(args.frame, "--frame")
    forced_frames = set(parse_frame_selectors(args.force_frame, "--force-frame"))

    process = None
    log = None
    try:
        if args.start_server:
            process, log = start_managed_server(args.server_port, args.image_model)
        state = read_state()
        state["api_root"] = API_ROOT
        state["image_model"] = args.image_model
        write_state(state)
        master_path = (
            adopt_existing_master(state, args.adopt_master)
            if args.adopt_master is not None
            else generate_master(state, force=args.force_master)
        )

        by_action = {action: factory() for action, factory in BLUEPRINT_FACTORIES.items()}
        requested = selected_frames(args.stage, explicit_frames)
        for action, frame_index in requested:
            blueprints = by_action[action]
            if not 0 <= frame_index < len(blueprints):
                raise RuntimeError(f"Frame {action}:{frame_index} is outside the blueprint sequence")
            generate_frame(
                state,
                master_path,
                action,
                blueprints[frame_index],
                force=(action, frame_index) in forced_frames,
            )

        if explicit_frames:
            state["status"] = "selected-frames-ready"
        else:
            state["status"] = "pilot-ready" if args.stage == "pilot" else (
                "master-ready" if args.stage == "master" else "frames-ready"
            )
        state["requested_frames"] = [f"{action}:{index}" for action, index in requested]
        write_state(state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        state = locals().get("state")
        if isinstance(state, dict):
            state["status"] = "failed"
            state["error"] = str(error)
            write_state(state)
        print(str(error), file=sys.stderr)
        return 1
    finally:
        stop_managed_server(process, log)


if __name__ == "__main__":
    raise SystemExit(main())
