import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw

from asset_studio.local_3d_pipeline import (
    ComfyPaths,
    REQUIRED_COMFY_NODES,
    build_background_prompt,
    build_controls_prompt,
    build_qwen_prompt,
    build_reference_idle_sheet,
    evaluate_action_sheet_quality,
    generate_local_action_sheet,
    local_3d_pipeline_health,
    normalize_local_action_payload,
    pixelize_action_sheet,
)


def data_url(image: Image.Image) -> str:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def action_sheet(*, alpha: bool) -> Image.Image:
    background = (0, 0, 0, 0) if alpha else (243, 245, 247, 255)
    sheet = Image.new("RGBA", (1024, 1024), background)
    draw = ImageDraw.Draw(sheet)
    for index in range(8):
        column, row = index % 4, index // 4
        center_x = column * 256 + 128
        top = row * 512 + 64
        color = (60 + index * 12, 80 + index * 8, 120 + index * 6, 255)
        draw.ellipse((center_x - 34, top, center_x + 34, top + 68), fill=color)
        draw.rectangle((center_x - 52, top + 60, center_x + 52, top + 260), fill=color)
        draw.rectangle((center_x - 44, top + 250, center_x - 4, top + 420), fill=color)
        draw.rectangle((center_x + 4, top + 250, center_x + 44, top + 420), fill=color)
    return sheet


def consistent_walk_sheet(
    *,
    clothing_drift: bool = False,
    duplicate_motion: bool = False,
    static_upper_body: bool = False,
) -> Image.Image:
    sheet = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    phases = [(-26, 22), (-18, 14), (-9, 5), (3, -8), (24, -25), (15, -16), (7, -3), (-8, 10)]
    if duplicate_motion:
        phases = [phases[0]] * 8
    for index, (left_shift, right_shift) in enumerate(phases):
        column, row = index % 4, index // 4
        offset_x, offset_y = column * 256, row * 512
        draw = ImageDraw.Draw(sheet)
        skin = (190, 116, 70, 255)
        jacket = (180, 40, 45, 255) if clothing_drift and index == 3 else (36, 48, 88, 255)
        pants = (42, 38, 40, 255)
        draw.ellipse((offset_x + 98, offset_y + 52, offset_x + 158, offset_y + 118), fill=skin)
        draw.rectangle((offset_x + 86, offset_y + 110, offset_x + 170, offset_y + 284), fill=jacket)
        arm_left = 0 if static_upper_body else left_shift
        arm_right = 0 if static_upper_body else right_shift
        draw.line((offset_x + 88, offset_y + 132, offset_x + 68 - arm_left // 4, offset_y + 270 + arm_right * 2), fill=jacket, width=24)
        draw.line((offset_x + 168, offset_y + 132, offset_x + 188 - arm_right // 4, offset_y + 270 + arm_left * 2), fill=jacket, width=24)
        draw.line((offset_x + 112, offset_y + 276, offset_x + 104 + left_shift, offset_y + 438), fill=pants, width=32)
        draw.line((offset_x + 144, offset_y + 276, offset_x + 152 + right_shift, offset_y + 438), fill=pants, width=32)
    return sheet


def consistent_idle_sheet() -> Image.Image:
    sheet = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    breath_offsets = [0, -3, -6, -3, 0, 3, 6, 3]
    hand_offsets = [0, -2, -4, -2, 0, 2, 4, 2]
    for index, (breath, hands) in enumerate(zip(breath_offsets, hand_offsets)):
        column, row = index % 4, index // 4
        offset_x, offset_y = column * 256, row * 512
        draw = ImageDraw.Draw(sheet)
        skin = (190, 116, 70, 255)
        jacket = (36, 48, 88, 255)
        pants = (42, 38, 40, 255)
        draw.ellipse((offset_x + 98, offset_y + 52 + breath, offset_x + 158, offset_y + 118 + breath), fill=skin)
        draw.rectangle((offset_x + 86, offset_y + 110 + breath, offset_x + 170, offset_y + 284), fill=jacket)
        draw.line((offset_x + 88, offset_y + 132 + breath, offset_x + 68, offset_y + 270 + hands), fill=jacket, width=24)
        draw.line((offset_x + 168, offset_y + 132 + breath, offset_x + 188, offset_y + 270 + hands), fill=jacket, width=24)
        draw.line((offset_x + 112, offset_y + 276, offset_x + 106, offset_y + 438), fill=pants, width=32)
        draw.line((offset_x + 144, offset_y + 276, offset_x + 150, offset_y + 438), fill=pants, width=32)
    return sheet


def test_local_payload_and_workflows_lock_eight_frame_contract():
    guide = action_sheet(alpha=False)
    identity = guide.crop((0, 0, 256, 512))
    normalized = normalize_local_action_payload({
        "guide_sheet": data_url(guide),
        "identity_image": data_url(identity),
        "action": "walk",
        "direction": "S",
        "resolution": 64,
        "palette_colors": 24,
        "style": "32-bit refined RPG",
        "shape_lock": 88,
        "pixel_simplify": 72,
        "seed": 123,
    })
    assert normalized["guide"].size == (1024, 1024)
    assert normalized["identity"].size == (256, 512)
    assert normalized["action"] == "walk"
    assert normalized["shape_lock"] == 88

    controls = build_controls_prompt("job/guide.png", "AssetStudio/run")
    assert controls["2"]["class_type"] == "DWPreprocessor"
    assert controls["6"]["class_type"] == "DepthAnything_V3"
    qwen = build_qwen_prompt(
        "job/identity.png",
        "job/identity-sheet.png",
        "job/pose.png",
        "job/depth.png",
        "job/guide.png",
        "AssetStudio/run",
        action="walk",
        direction="S",
        style="32-bit refined RPG",
        shape_lock=88,
        pixel_simplify=72,
        seed=123,
    )
    assert qwen["8"]["class_type"] == "TextEncodeQwenImageEditPlus"
    assert "exact 4 columns by 2 rows" in qwen["8"]["inputs"]["prompt"]
    assert "Preserve the supplied UAL walk exactly" in qwen["8"]["inputs"]["prompt"]
    assert "appearance transfer only" in qwen["8"]["inputs"]["prompt"]
    assert "starting 4x2 sheet already contains eight copies" in qwen["8"]["inputs"]["prompt"]
    assert "no green holes" in qwen["8"]["inputs"]["prompt"]
    assert "pose drift" in qwen["6"]["inputs"]["text"]
    assert "split face" in qwen["6"]["inputs"]["text"]
    assert qwen["20"]["inputs"]["latent_image"] == ["26", 0]
    assert qwen["20"]["inputs"]["positive"] == ["23", 0]
    assert qwen["23"]["inputs"] == {"conditioning": ["16", 0], "latent": ["19", 0]}
    assert qwen["24"]["inputs"]["image"] == "job/identity-sheet.png"
    assert qwen["26"]["inputs"]["pixels"] == ["25", 0]
    assert qwen["20"]["inputs"]["steps"] == 4
    assert qwen["20"]["inputs"]["denoise"] == 0.90
    refinement = build_qwen_prompt(
        "job/identity.png",
        "job/pose-base.png",
        "job/pose.png",
        "job/depth.png",
        "job/guide.png",
        "AssetStudio/refine",
        action="idle",
        direction="8dir",
        style="32-bit refined RPG",
        shape_lock=96,
        pixel_simplify=60,
        seed=456,
        prompt_text="restore clothing only",
        denoise=0.58,
        megapixels=1.0,
    )
    assert refinement["20"]["inputs"]["latent_image"] == ["26", 0]
    assert refinement["20"]["inputs"]["denoise"] == 0.58
    assert refinement["8"]["inputs"]["prompt"] == "restore clothing only"
    assert refinement["10"]["inputs"]["megapixels"] == 1.0
    assert refinement["25"]["inputs"]["megapixels"] == 1.0
    background = build_background_prompt("job/painted.png", "AssetStudio/run")
    assert background["2"]["class_type"] == "BiRefNetRMBG"


def test_shared_palette_pixelizer_outputs_eight_root_locked_portrait_frames():
    atlas, frames, qa = pixelize_action_sheet(action_sheet(alpha=True), cell_width=64, palette_colors=24)
    assert atlas.size == (256, 256)
    assert len(frames) == 8
    assert all(frame.size == (64, 128) for frame in frames)
    assert all(frame.getchannel("A").getbbox() is not None for frame in frames)
    assert qa["frame_size"] == [64, 128]
    assert qa["visible_colors"] <= 24
    assert qa["outline"] == "1px"
    assert qa["alpha"] == "binary"
    baselines = [frame.getchannel("A").getbbox()[3] for frame in frames]
    assert len(set(baselines)) == 1


class FakeComfyClient:
    def __init__(self, root: Path):
        self.url = "http://127.0.0.1:8188"
        self.paths = ComfyPaths(root=root, input=root / "input", output=root / "output")
        self.paths.input.mkdir(parents=True)
        self.paths.output.mkdir(parents=True)
        self.records = []
        for name, image in {
            "pose.png": action_sheet(alpha=False),
            "depth.png": action_sheet(alpha=False),
            "painted.png": action_sheet(alpha=False),
            "cutout.png": action_sheet(alpha=True),
        }.items():
            image.save(self.paths.output / name)

    def object_info(self):
        return {name: {} for name in REQUIRED_COMFY_NODES}

    def run(self, prompt):
        classes = {node["class_type"] for node in prompt.values()}
        if "DWPreprocessor" in classes:
            kind = "controls"
        elif "TextEncodeQwenImageEditPlus" in classes:
            kind = "qwen"
        else:
            kind = "background"
        record = {"kind": kind}
        self.records.append(record)
        return record

    def output_path(self, record, node_id):
        if record["kind"] == "controls":
            return self.paths.output / ("pose.png" if node_id == "3" else "depth.png")
        if record["kind"] == "qwen":
            return self.paths.output / "painted.png"
        return self.paths.output / "cutout.png"


def test_complete_local_pipeline_uses_no_hermes_or_codex(tmp_path):
    client = FakeComfyClient(tmp_path)
    health = local_3d_pipeline_health(client=client)
    assert health["available"] is True
    assert health["hermes_required"] is False

    guide = action_sheet(alpha=False)
    result = generate_local_action_sheet({
        "guide_sheet": data_url(guide),
        "identity_image": data_url(guide.crop((0, 0, 256, 512))),
        "action": "run",
        "resolution": 64,
        "palette_colors": 24,
        "seed": 123,
        "strict_validation": False,
    }, client=client)
    atlas = Image.open(io.BytesIO(result["atlas"])).convert("RGBA")
    assert atlas.size == (256, 256)
    assert len(result["frames"]) == 8
    assert result["metadata"]["provider"] == "local-comfyui"
    assert result["metadata"]["hermes_used"] is False
    assert result["metadata"]["codex_used"] is False
    assert result["accepted"] is True
    assert result["metadata"]["qa"]["strict"]["enforced"] is False
    assert [record["kind"] for record in client.records] == ["controls", "qwen", "background"]
    assert not any(client.paths.input.iterdir())


def test_strict_validator_accepts_consistent_motion_and_rejects_drift_and_duplicates():
    clean = consistent_walk_sheet()
    atlas, frames, _qa = pixelize_action_sheet(clean, cell_width=64, palette_colors=24)
    report = evaluate_action_sheet_quality(
        clean,
        guide=clean,
        identity=clean.crop((0, 0, 256, 512)),
        pixel_frames=frames,
        palette_limit=24,
        minimum_score=90,
    )
    assert atlas.size == (256, 256)
    assert report["pass"] is True, report
    assert report["score"] >= 90

    drift = consistent_walk_sheet(clothing_drift=True)
    _atlas, drift_frames, _qa = pixelize_action_sheet(drift, cell_width=64, palette_colors=24)
    drift_report = evaluate_action_sheet_quality(
        drift,
        guide=clean,
        identity=clean.crop((0, 0, 256, 512)),
        pixel_frames=drift_frames,
        palette_limit=24,
        minimum_score=90,
    )
    assert drift_report["pass"] is False
    assert "옷 색과 머리색 고정" in drift_report["failures"]

    duplicate = consistent_walk_sheet(duplicate_motion=True)
    _atlas, duplicate_frames, _qa = pixelize_action_sheet(duplicate, cell_width=64, palette_colors=24)
    duplicate_report = evaluate_action_sheet_quality(
        duplicate,
        guide=clean,
        identity=clean.crop((0, 0, 256, 512)),
        pixel_frames=duplicate_frames,
        palette_limit=24,
        minimum_score=90,
    )
    assert duplicate_report["pass"] is False
    duplicate_upper_check = next(check for check in duplicate_report["checks"] if check["id"] == "upper-body-motion")
    assert duplicate_upper_check["pass"] is False
    duplicate_motion_check = next(check for check in duplicate_report["checks"] if check["id"] == "motion-progress")
    assert duplicate_motion_check["pass"] is False

    static_upper = consistent_walk_sheet(static_upper_body=True)
    _atlas, static_upper_frames, _qa = pixelize_action_sheet(static_upper, cell_width=64, palette_colors=24)
    static_upper_report = evaluate_action_sheet_quality(
        static_upper,
        guide=clean,
        identity=clean.crop((0, 0, 256, 512)),
        pixel_frames=static_upper_frames,
        palette_limit=24,
        minimum_score=90,
    )
    assert static_upper_report["pass"] is False
    upper_check = next(check for check in static_upper_report["checks"] if check["id"] == "upper-body-motion")
    assert upper_check["pass"] is False


def test_strict_validator_accepts_subtle_idle_without_requiring_walk_motion():
    idle = consistent_idle_sheet()
    _atlas, frames, _qa = pixelize_action_sheet(idle, cell_width=64, palette_colors=24)
    report = evaluate_action_sheet_quality(
        idle,
        guide=idle,
        identity=idle.crop((0, 0, 256, 512)),
        pixel_frames=frames,
        palette_limit=24,
        minimum_score=90,
        action="idle",
    )
    assert report["pass"] is True, report
    motion_check = next(check for check in report["checks"] if check["id"] == "motion-progress")
    assert motion_check["pass"] is True
    assert motion_check["threshold"]["unique"] == 3


def test_reference_idle_keeps_identity_and_feet_locked_while_breathing():
    identity = consistent_idle_sheet().crop((0, 0, 256, 512))
    sheet = build_reference_idle_sheet(identity)
    atlas, frames, _qa = pixelize_action_sheet(sheet, cell_width=96, palette_colors=32)
    assert atlas.size == (384, 384)
    baselines = [frame.getchannel("A").getbbox()[3] for frame in frames]
    assert len(set(baselines)) == 1
    assert len({frame.tobytes() for frame in frames}) >= 5
