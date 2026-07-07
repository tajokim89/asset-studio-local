#!/usr/bin/env python3
from __future__ import annotations

import base64
import importlib.util
import io
import json
import os
import shutil
import sys
import time
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
UPLOADS = ASSETS / "uploads"
GENERATED = ASSETS / "generated"
PROCESSED = ASSETS / "processed"
PROJECTS = ROOT / "projects"
for p in (UPLOADS, GENERATED, PROCESSED, PROJECTS):
    p.mkdir(parents=True, exist_ok=True)

HERMES_REPO = Path(os.environ.get("HERMES_REPO", "/Users/tajokim/.hermes/hermes-agent"))
PROVIDER_PATH = HERMES_REPO / "plugins/image_gen/openai-codex/__init__.py"
sys.path.insert(0, str(HERMES_REPO))

RUNTIME_DEPENDENCIES = {
    "httpx": "httpx>=0.28.0",
    "PIL": "pillow>=12.1.0",
    "numpy": "numpy>=2.3.0",
}


def check_runtime_dependencies() -> None:
    """Fail at startup with an actionable message instead of during AI generation."""
    missing = []
    for module_name, package_name in RUNTIME_DEPENDENCIES.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append(package_name)
    if not missing:
        return
    python = sys.executable
    raise SystemExit(
        "Missing Python runtime dependencies: "
        + ", ".join(missing)
        + "\nFix: "
        + f"{python} -m pip install -r requirements.txt"
        + "\nOr run: ./scripts/run_server.sh"
        + f"\nCurrent Python: {python}"
    )


PRESET_SUFFIX = {
    "general": "Clean, useful image asset. No watermark.",
    "product": "Product photography style, isolated subject, clean lighting, usable commercial asset. No watermark.",
    "character": "Character asset, clear silhouette, usable as a cutout. No text, no watermark.",
    "icon": "Icon asset, centered, clean silhouette, simple background. No text, no watermark.",
    "logo": "Logo concept exploration, simple mark, avoid tiny unreadable text, no watermark.",
    "game": "Game-ready asset, clean silhouette, transparent-friendly composition. No text, no watermark.",
    "ui": "UI component asset, clean shape, usable in app/game interface. No baked text unless requested.",
    "background": "Background illustration, composition suitable as a canvas backdrop. No watermark.",
    "pixel": "Refined pixel-art style, clean edges, not chunky 8-bit unless requested. No watermark.",
    "sticker": "Sticker-style cutout, bold readable silhouette, isolated subject. No watermark.",
    "thumbnail": "Thumbnail element, high contrast, clean cutout-friendly subject. No watermark.",
}


def load_provider():
    spec = importlib.util.spec_from_file_location("asset_studio_openai_codex", PROVIDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load openai-codex image provider")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.OpenAICodexImageGenProvider()


def build_prompt(user_prompt: str, preset: str, background_mode: str = "none") -> str:
    user_prompt = (user_prompt or "").strip()
    preset = (preset or "general").strip()
    background_mode = (background_mode or "none").strip()
    suffix = PRESET_SUFFIX.get(preset, PRESET_SUFFIX["general"])
    chroma = ""
    if background_mode == "chroma_green":
        chroma = """
Chroma key background requirement: render the generated object on a perfectly flat solid green background, exactly RGB(0,255,0) / #00FF00. The green background must be uniform edge-to-edge with no gradient, texture, shadow, vignette, checkerboard, transparency, scenery, floor, or backdrop objects. Keep the subject fully inside the frame and separated from the green so the background can be removed by color key."""
    return f"""{user_prompt or 'Useful image asset'}

Asset Studio preset: {preset}
Guidance: {suffix}{chroma}
Production constraints: make it easy to use in a design canvas; avoid watermarks; avoid accidental logos; avoid unreadable text unless explicitly requested.""".strip()


def data_url_to_bytes(data_url: str) -> tuple[bytes, str]:
    if "," not in data_url:
        raise ValueError("Expected data URL")
    header, b64 = data_url.split(",", 1)
    ext = "png"
    if "jpeg" in header or "jpg" in header:
        ext = "jpg"
    elif "webp" in header:
        ext = "webp"
    return base64.b64decode(b64), ext


def fallback_corner_remove(raw: bytes, tolerance: int = 36) -> bytes:
    """Conservative fallback: flood-fill transparent pixels connected to image borders."""
    from PIL import Image

    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    px = img.load()
    w, h = img.size
    step = max(1, min(w, h) // 128)
    border = []
    for x in range(0, w, step):
        border.append((x, 0)); border.append((x, h - 1))
    for y in range(0, h, step):
        border.append((0, y)); border.append((w - 1, y))
    corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    seeds = list(dict.fromkeys(border + corners))
    targets = [px[x, y][:3] for x, y in seeds]
    mins = tuple(min(c[i] for c in targets) for i in range(3))
    maxs = tuple(max(c[i] for c in targets) for i in range(3))
    seen = set()
    stack = seeds[:]

    def close(rgb):
        return all(mins[i] - tolerance <= rgb[i] <= maxs[i] + tolerance for i in range(3))

    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= w or y >= h or (x, y) in seen:
            continue
        seen.add((x, y))
        r, g, b, a = px[x, y]
        if a == 0 or not close((r, g, b)):
            continue
        px[x, y] = (r, g, b, 0)
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def force_chroma_green_background(raw: bytes, tolerance: int = 44) -> bytes:
    """Replace border-connected generated backdrop with exact #00FF00.

    Image models often ignore prompt-only green background requests and return white.
    This makes the file itself chroma-keyable by flood-filling only the backdrop
    connected to the image edges, preserving internal subject pixels.
    """
    from collections import deque
    from PIL import Image

    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    px = img.load()
    w, h = img.size
    step = max(1, min(w, h) // 160)
    seeds = []
    samples = []
    for x in range(0, w, step):
        seeds.append((x, 0)); seeds.append((x, h - 1))
    for y in range(0, h, step):
        seeds.append((0, y)); seeds.append((w - 1, y))
    seeds.extend([(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)])
    seeds = list(dict.fromkeys(seeds))
    for x, y in seeds:
        r, g, b, a = px[x, y]
        if a > 0:
            samples.append((r, g, b))
    if not samples:
        samples = [(255, 255, 255)]
    bg = tuple(sum(c[i] for c in samples) / len(samples) for i in range(3))

    def bg_like(x, y):
        r, g, b, a = px[x, y]
        if a == 0:
            return True
        dist = sum((v - bg[i]) ** 2 for i, v in enumerate((r, g, b))) ** 0.5
        # White/gray model backdrops often have slight compression/lighting variation.
        return dist <= tolerance or (r >= 235 and g >= 235 and b >= 235 and bg[0] >= 210 and bg[1] >= 210 and bg[2] >= 210)

    seen = set()
    q = deque(seeds)
    while q:
        x, y = q.popleft()
        if x < 0 or y < 0 or x >= w or y >= h or (x, y) in seen or not bg_like(x, y):
            continue
        seen.add((x, y))
        px[x, y] = (0, 255, 0, 255)
        q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _is_chroma_green_pixel(r: int, g: int, b: int, a: int, tolerance: int = 18) -> bool:
    if a == 0:
        return True
    green_dom = g - max(r, b)
    green_ratio = g / max(1, (r + b) / 2)
    return (
        (r <= tolerance and g >= 255 - tolerance and b <= tolerance)
        or (g > 80 and green_dom > max(22, tolerance) and green_ratio > 1.25 and b < 150)
        or (g > 55 and green_dom > max(18, tolerance - 4) and green_ratio > 1.18 and b < 130)
    )


def chroma_green_report(raw: bytes, tolerance: int = 18) -> dict:
    from PIL import Image

    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    w, h = img.size
    px = img.load()
    green_pixels = 0
    alpha_min = 255
    alpha_max = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            alpha_min = min(alpha_min, a)
            alpha_max = max(alpha_max, a)
            if a > 0 and _is_chroma_green_pixel(r, g, b, a, tolerance):
                green_pixels += 1
    corners = [list(px[0, 0]), list(px[w - 1, 0]), list(px[0, h - 1]), list(px[w - 1, h - 1])]
    return {"width": w, "height": h, "alpha_min": alpha_min, "alpha_max": alpha_max, "corner_alpha": [c[3] for c in corners], "green_pixels": green_pixels}


def remove_chroma_green_bytes(raw: bytes, tolerance: int = 18, mode: str = "global") -> bytes:
    """Remove #00FF00 chroma backdrop plus internal green holes and subtle green spill/halo.

    mode='outer' keeps legacy border-connected behavior. mode='global' removes
    all chroma-green pixels anywhere in the sheet, including negative-space holes
    between legs/arms/equipment, which is required for generated sprite sheets.
    """
    from collections import deque
    from PIL import Image

    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    px = img.load()
    w, h = img.size

    def green_like(x, y):
        r, g, b, a = px[x, y]
        return _is_chroma_green_pixel(r, g, b, a, tolerance)

    if mode in {"outer", "border", "flood"}:
        q = deque()
        for x in range(w):
            q.append((x, 0)); q.append((x, h - 1))
        for y in range(h):
            q.append((0, y)); q.append((w - 1, y))
        seen = set()
        while q:
            x, y = q.popleft()
            if x < 0 or y < 0 or x >= w or y >= h or (x, y) in seen or not green_like(x, y):
                continue
            seen.add((x, y))
            r, g, b, a = px[x, y]
            px[x, y] = (r, g, b, 0)
            q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    else:
        # Global chroma key: delete green anywhere, not just border-connected areas.
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a > 0 and green_like(x, y):
                    px[x, y] = (r, g, b, 0)

    # Remove green spill/matte remnants around newly transparent pixels.
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a <= 0:
                continue
            green_dom = g - max(r, b)
            green_ratio = g / max(1, (r + b) / 2)
            if g > 45 and green_dom > 8 and green_ratio > 1.10 and b < 120:
                base = int((r + b) / 2)
                nr = max(r, base + 8)
                ng = min(base, g)
                nb = min(b, base)
                px[x, y] = (nr, ng, nb, int(a * 0.55))

    for y in range(1, h - 1):
        for x in range(1, w - 1):
            r, g, b, a = px[x, y]
            if a <= 0:
                continue
            transparent_neighbors = sum(1 for yy in (y - 1, y, y + 1) for xx in (x - 1, x, x + 1) if not (xx == x and yy == y) and px[xx, yy][3] == 0)
            if transparent_neighbors >= 5 and g > max(r, b) + 6 and g > 35:
                px[x, y] = (r, g, b, 0)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _png_bytes_from_image(img) -> bytes:
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _alpha_bbox(img, threshold: int = 0):
    alpha = img.getchannel("A")
    mask = alpha.point(lambda a: 255 if a > threshold else 0)
    return mask.getbbox()


def _component_bboxes(img, min_area: int = 8):
    """Return connected opaque component bboxes sorted in reading order."""
    from collections import deque
    px = img.load()
    w, h = img.size
    seen = set()
    boxes = []
    for y in range(h):
        for x in range(w):
            if (x, y) in seen or px[x, y][3] == 0:
                continue
            q = deque([(x, y)])
            seen.add((x, y))
            minx = maxx = x
            miny = maxy = y
            count = 0
            while q:
                cx, cy = q.popleft()
                count += 1
                minx = min(minx, cx); maxx = max(maxx, cx)
                miny = min(miny, cy); maxy = max(maxy, cy)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if nx < 0 or ny < 0 or nx >= w or ny >= h or (nx, ny) in seen:
                        continue
                    if px[nx, ny][3] == 0:
                        continue
                    seen.add((nx, ny))
                    q.append((nx, ny))
            if count >= min_area:
                boxes.append({"bbox": (minx, miny, maxx + 1, maxy + 1), "area": count})
    return sorted(boxes, key=lambda b: (b["bbox"][1], b["bbox"][0]))


def _direction_slot_index(direction: str, slot_count: int) -> int:
    direction = (direction or "S").upper()
    canonical8 = ["S", "SW", "W", "NW", "N", "NE", "E", "SE"]
    if direction in canonical8:
        return min(slot_count - 1, canonical8.index(direction))
    return 0


def _crop_with_transparent_padding(img, bbox, pad: int = 1):
    from PIL import Image
    x0, y0, x1, y1 = bbox
    crop = img.crop((x0, y0, x1, y1))
    if pad <= 0:
        return crop
    out = Image.new("RGBA", (crop.width + pad * 2, crop.height + pad * 2), (0, 0, 0, 0))
    out.alpha_composite(crop, (pad, pad))
    return out


def _crop_single_direction_candidate(img, target_direction: str = "S"):
    bbox = _alpha_bbox(img)
    if not bbox:
        return img, {"status": "fail", "reason": "no_opaque_pixels", "target_direction": target_direction}
    cropped = img.crop(bbox)
    components = _component_bboxes(cropped)
    if len(components) >= 6:
        idx = _direction_slot_index(target_direction, 8)
        cell_w = max(1, cropped.width // 8)
        x0 = max(0, idx * cell_w)
        x1 = cropped.width if idx == 7 else min(cropped.width, (idx + 1) * cell_w)
        cell = cropped.crop((x0, 0, x1, cropped.height))
        tight = _alpha_bbox(cell)
        if tight:
            result = _crop_with_transparent_padding(cell, tight)
        else:
            result = cell
        return result, {"status": "pass", "reason": "selected_equal_grid_slot", "target_direction": target_direction, "component_count": len(components), "selected_slot": idx, "bbox": [bbox[0] + x0 + (tight[0] if tight else 0), bbox[1] + (tight[1] if tight else 0), bbox[0] + x0 + (tight[2] if tight else (x1 - x0)), bbox[1] + (tight[3] if tight else cropped.height)]}
    if len(components) <= 1:
        tight = _alpha_bbox(cropped)
        if tight:
            cropped = _crop_with_transparent_padding(cropped, tight)
        return cropped, {"status": "pass", "reason": "single_component", "target_direction": target_direction, "component_count": len(components), "selected_slot": 0, "bbox": list(bbox)}
    idx = _direction_slot_index(target_direction, len(components))
    chosen = components[idx]
    x0, y0, x1, y1 = chosen["bbox"]
    result = _crop_with_transparent_padding(cropped, (x0, y0, x1, y1))
    tight = _alpha_bbox(result)
    return result, {"status": "pass", "reason": "selected_direction_slot", "target_direction": target_direction, "component_count": len(components), "selected_slot": idx, "bbox": [bbox[0] + x0, bbox[1] + y0, bbox[0] + x1, bbox[1] + y1]}


def _trim_and_center_sprite(raw: bytes, cell_size: int):
    from PIL import Image
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    bbox = _alpha_bbox(img)
    if bbox:
        img = img.crop(bbox)
    scale = min(1.0, (cell_size - 16) / max(1, img.width), (cell_size - 16) / max(1, img.height))
    if scale < 1.0:
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (cell_size, cell_size), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((cell_size - img.width) // 2, cell_size - img.height - 8))
    return canvas


def sprite_alpha_bbox_stats(raw: bytes) -> dict:
    """Measure the actual transparent sprite silhouette before accepting it as game-ready."""
    from PIL import Image
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    bbox = _alpha_bbox(img)
    if not bbox:
        return {"bbox": None, "width": 0, "height": 0, "area": 0, "image_size": [img.width, img.height], "touches_edge": False}
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    height = y1 - y0
    touches_edge = x0 <= 0 or y0 <= 0 or x1 >= img.width or y1 >= img.height
    return {
        "bbox": [x0, y0, x1, y1],
        "width": width,
        "height": height,
        "area": width * height,
        "image_size": [img.width, img.height],
        "touches_edge": touches_edge,
    }


def evaluate_sprite_source_geometry_quality(
    sources: dict,
    *,
    required_directions=("S", "N", "W", "SW", "NW"),
    min_height_ratio: float = 0.82,
    min_width_ratio: float = 0.55,
    min_area_ratio: float = 0.55,
    reject_edge_touch: bool = True,
) -> dict:
    """Fail closed when generated directions are not the same character scale.

    Direction classifiers can say "SW" while the model actually returned a tiny or
    cropped character. This gate catches the Phase 20 failure mode before any
    sheet/atlas is presented as usable.
    """
    present = {str(k).upper(): v for k, v in sources.items()}
    missing = [d for d in required_directions if d not in present]
    if missing:
        return {"pass": False, "reason": "missing_sources", "missing": missing, "failed_directions": missing, "stats": {}}

    stats = {d: sprite_alpha_bbox_stats(present[d]) for d in required_directions}
    non_empty = [s for s in stats.values() if s["height"] > 0 and s["width"] > 0]
    if len(non_empty) != len(required_directions):
        failed = [d for d, s in stats.items() if s["height"] <= 0 or s["width"] <= 0]
        return {"pass": False, "reason": "empty_sprite", "failed_directions": failed, "stats": stats}

    max_height = max(s["height"] for s in stats.values())
    max_width = max(s["width"] for s in stats.values())
    max_area = max(s["area"] for s in stats.values())
    failed = []
    for d, s in stats.items():
        s["height_ratio"] = round(s["height"] / max(1, max_height), 4)
        s["width_ratio"] = round(s["width"] / max(1, max_width), 4)
        s["area_ratio"] = round(s["area"] / max(1, max_area), 4)
        reasons = []
        if s["height_ratio"] < min_height_ratio:
            reasons.append("height_outlier")
        if s["width_ratio"] < min_width_ratio:
            reasons.append("width_outlier")
        if s["area_ratio"] < min_area_ratio:
            reasons.append("area_outlier")
        if reject_edge_touch and s["touches_edge"]:
            reasons.append("touches_canvas_edge")
        s["quality_failures"] = reasons
        if reasons:
            failed.append(d)

    return {
        "pass": not failed,
        "reason": "pass" if not failed else "inconsistent_source_geometry",
        "failed_directions": failed,
        "thresholds": {
            "min_height_ratio": min_height_ratio,
            "min_width_ratio": min_width_ratio,
            "min_area_ratio": min_area_ratio,
            "reject_edge_touch": reject_edge_touch,
        },
        "stats": stats,
    }


def build_8dir_mirror_sheet_from_source_pngs(sources: dict, cell_size: int = 420, layout: str = "row") -> tuple[bytes, dict]:
    """Build canonical 8-direction sheet from 5 generated sources plus exact flips.

    Only S/N/W/SW/NW are accepted as source directions. E/SE/NE must be derived
    by horizontal mirror so right-facing consistency is deterministic.
    """
    from PIL import Image, ImageOps
    required = ["S", "N", "W", "SW", "NW"]
    forbidden = ["E", "SE", "NE"]
    present = {str(k).upper() for k in sources.keys()}
    bad = [d for d in forbidden if d in present]
    if bad:
        raise ValueError(f"right-facing source directions are forbidden; derive by flip only: {', '.join(bad)}")
    missing = [d for d in required if d not in present]
    if missing:
        raise ValueError(f"missing source directions: {', '.join(missing)}")

    geometry_qa = evaluate_sprite_source_geometry_quality({d: sources[d] for d in required})
    if geometry_qa.get("pass") is not True:
        raise ValueError(f"sprite source geometry QA failed: {geometry_qa}")

    sprites = {d: _trim_and_center_sprite(sources[d], cell_size) for d in required}
    sprites["NE"] = ImageOps.mirror(sprites["NW"])
    sprites["E"] = ImageOps.mirror(sprites["W"])
    sprites["SE"] = ImageOps.mirror(sprites["SW"])
    order = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

    if layout == "atlas_2x4":
        sheet = Image.new("RGBA", (cell_size * 2, cell_size * 4), (0, 0, 0, 0))
        for i, d in enumerate(order):
            sheet.alpha_composite(sprites[d], ((i % 2) * cell_size, (i // 2) * cell_size))
    else:
        sheet = Image.new("RGBA", (cell_size * len(order), cell_size), (0, 0, 0, 0))
        for i, d in enumerate(order):
            sheet.alpha_composite(sprites[d], (i * cell_size, 0))
    out = _png_bytes_from_image(sheet)
    qa = chroma_green_report(out)
    qa.update({
        "method": "5-source+mirror",
        "order": order,
        "source_directions": required,
        "mirrored_pairs": {"NW": "NE", "W": "E", "SW": "SE"},
        "layout": layout,
        "cell_size": cell_size,
        "geometry_qa": geometry_qa,
    })
    return out, qa


def postprocess_pixel_generation_bytes(raw: bytes, background_mode: str = "none", direction_mode: str = "single", target_direction: str = "S", animation_mode: str = "idle", chroma_mode: str = "global") -> tuple[bytes, dict]:
    from PIL import Image
    """Normalize generated pixel assets before the browser sees them.

    For single-target idle assets, never return the model's full turnaround sheet:
    remove chroma, split opaque candidates, select the requested direction slot,
    and return one transparent sprite crop.
    """
    processed = raw
    method_steps = []
    if str(background_mode or "none").strip() == "chroma_green":
        processed = force_chroma_green_background(processed)
        processed = remove_chroma_green_bytes(processed, mode=chroma_mode)
        method_steps.append(f"chroma-{chroma_mode}")
    img = Image.open(io.BytesIO(processed)).convert("RGBA")
    direction_qa = {"status": "skipped", "target_direction": target_direction}
    if str(direction_mode or "single") == "single" and str(animation_mode or "idle") == "idle":
        img, direction_qa = _crop_single_direction_candidate(img, target_direction)
        method_steps.append("single-target-crop")
    out = _png_bytes_from_image(img)
    qa = chroma_green_report(out)
    qa["direction_qa"] = direction_qa
    qa["method"] = "+".join(method_steps) if method_steps else "none"
    return out, qa


def edge_aware_sheet_remove(raw: bytes, tolerance: int = 24, edge_threshold: int = 40) -> bytes:
    """Preserve-mask sheet cleanup: remove border backdrop, protect obvious item pixels.

    Designed for multi-object asset sheets where rembg keeps only a few main subjects.
    It first protects pixels that clearly differ from the sampled border background,
    expands that protection slightly to keep outlines, then flood-removes only the
    border-connected backdrop outside the protected mask.
    """
    from collections import deque
    from PIL import Image, ImageFilter
    import math

    def lum(rgb):
        return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]

    def sat(rgb):
        mx = max(rgb); mn = min(rgb)
        return 0 if mx == 0 else (mx - mn) / mx * 255

    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    px = img.load()
    w, h = img.size

    # Border statistics define the generated backdrop.
    step = max(1, min(w, h) // 160)
    samples = []
    for x in range(0, w, step):
        samples.append(px[x, 0][:3]); samples.append(px[x, h - 1][:3])
    for y in range(0, h, step):
        samples.append(px[0, y][:3]); samples.append(px[w - 1, y][:3])
    bg = tuple(sum(c[i] for c in samples) / len(samples) for i in range(3))
    bg_l = sum(lum(c) for c in samples) / len(samples)
    bg_s = sum(sat(c) for c in samples) / len(samples)

    # Tuned so tolerance 24 is conservative enough to preserve visible items,
    # while still clearing the dark generated backdrop around the whole sheet.
    bg_tol = tolerance + 20
    preserve_dist = max(30, tolerance + 14)
    light_diff = max(18, tolerance)
    sat_diff = max(12, tolerance - 6)

    mins = tuple(min(c[i] for c in samples) - bg_tol for i in range(3))
    maxs = tuple(max(c[i] for c in samples) + bg_tol for i in range(3))

    protect = Image.new("L", (w, h), 0)
    pdata = []
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                pdata.append(0)
                continue
            rgb = (r, g, b)
            dist = math.sqrt(sum((rgb[i] - bg[i]) ** 2 for i in range(3)))
            # Keep clear item material: color/brightness/saturation that differs from the border backdrop.
            keep = (
                dist >= preserve_dist
                or lum(rgb) >= bg_l + light_diff
                or sat(rgb) >= bg_s + sat_diff
            )
            pdata.append(255 if keep else 0)
    protect.putdata(pdata)
    protect = protect.filter(ImageFilter.MaxFilter(5))  # 2px outline protection.
    ppx = protect.load()

    def bg_like(x, y):
        r, g, b, a = px[x, y]
        if a == 0:
            return True
        if ppx[x, y] > 0:
            return False
        rgb = (r, g, b)
        dist = math.sqrt(sum((rgb[i] - bg[i]) ** 2 for i in range(3)))
        in_border_box = mins[0] <= r <= maxs[0] and mins[1] <= g <= maxs[1] and mins[2] <= b <= maxs[2]
        return dist <= bg_tol or in_border_box

    seen = set()
    q = deque()
    for x in range(w):
        q.append((x, 0)); q.append((x, h - 1))
    for y in range(h):
        q.append((0, y)); q.append((w - 1, y))

    while q:
        x, y = q.popleft()
        if x < 0 or y < 0 or x >= w or y >= h or (x, y) in seen or not bg_like(x, y):
            continue
        seen.add((x, y))
        r, g, b, a = px[x, y]
        px[x, y] = (r, g, b, 0)
        q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    # Remove tiny disconnected specks that are not part of the protected item mask.
    visited = set()
    cleanup_min = 18
    for yy in range(h):
        for xx in range(w):
            if (xx, yy) in visited or px[xx, yy][3] == 0:
                continue
            comp = []
            has_protect = False
            q = deque([(xx, yy)])
            while q:
                x, y = q.popleft()
                if x < 0 or y < 0 or x >= w or y >= h or (x, y) in visited or px[x, y][3] == 0:
                    continue
                visited.add((x, y)); comp.append((x, y))
                if ppx[x, y] > 0:
                    has_protect = True
                q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
            if len(comp) < cleanup_min and not has_protect:
                for x, y in comp:
                    r, g, b, a = px[x, y]
                    px[x, y] = (r, g, b, 0)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

def remove_background_bytes(raw: bytes, tolerance: int = 36, mode: str = "ai", chroma_mode: str = "global") -> tuple[bytes, str, dict | None]:
    # AI segmentation is good for one subject, but it often drops most sprites in an asset sheet.
    # Sheet mode uses edge-aware border flood so all separated objects are preserved.
    if mode in {"chroma_green", "green", "key"}:
        out = remove_chroma_green_bytes(raw, tolerance=tolerance or 18, mode=chroma_mode or "global")
        return out, f"chroma-green-key-{chroma_mode or 'global'}", chroma_green_report(out, tolerance=tolerance or 18)
    if mode in {"sheet", "flood", "border"}:
        return edge_aware_sheet_remove(raw, tolerance=tolerance or 24), "preserve-mask-sheet", None
    try:
        from rembg import remove
        return remove(raw), "rembg", None
    except Exception as e:
        return fallback_corner_remove(raw, tolerance=tolerance), f"fallback:{type(e).__name__}", None


def data_url_to_png_data_url(data_url: str) -> str:
    raw, _ext = data_url_to_bytes(data_url)
    from PIL import Image

    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    out = io.BytesIO()
    img.save(out, format="PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")


def aspect_from_image_data_url(data_url: str) -> tuple[str, tuple[int, int]]:
    from PIL import Image

    raw, _ext = data_url_to_bytes(data_url)
    img = Image.open(io.BytesIO(raw))
    w, h = img.size
    if w > h * 1.15:
        return "landscape", (w, h)
    if h > w * 1.15:
        return "portrait", (w, h)
    return "square", (w, h)


def build_inpaint_prompt(prompt: str, negative: str = "") -> str:
    neg = f"\nAvoid: {negative.strip()}" if negative and negative.strip() else ""
    return f"""You are editing a small cropped patch from a pixel/game asset canvas.

Mask contract:
- White pixels = the ONLY area that may change.
- Black pixels = context only; preserve it.
- Do not redesign the whole crop, scene, tile, character, skeleton, or background.

User edit request for the white masked area only: {prompt.strip()}
{neg}

Return the same crop composition. Match the original pixel-art style, palette, lighting, scale, outline thickness, and perspective. No new background panel, no rectangle fill, no watermark, no text.""".strip()


def build_replace_object_prompt(prompt: str, negative: str = "") -> str:
    neg = f"\nAvoid: {negative.strip()}" if negative and negative.strip() else ""
    return f"""You are editing a cropped region from an existing game/pixel-art image.

Object replacement contract:
- The first input image is the real reference/context crop. Study its style, angle, scale, palette, lighting, outline thickness, and hand/contact geometry.
- The second input image is a black/white mask. White pixels are where the old object was selected. Black pixels are protected context.
- Generate the requested replacement object so it fits the masked area and matches the surrounding image.
- Do not draw a new character/body/hand/background/scene. Do not redesign protected context.
- The result will be locally clipped to the white mask and placed back at the original bbox, so draw the replacement at the same crop scale, not as a centered sticker.

Replacement request: {prompt.strip()}
{neg}

Return the same crop composition. No text, no watermark, no full-image redraw.""".strip()


def collect_codex_edit_b64(image_data_url: str, mask_data_url: str, prompt: str, negative: str = "", prompt_is_final: bool = False) -> tuple[str, str, str]:
    """Use the Codex image-generation tool as an image-edit backend.

    The tool returns a full image; we still composite it locally through the mask so
    pixels outside the selected area stay protected even if the model drifts.
    """
    import httpx
    from agent.auxiliary_client import _codex_cloudflare_headers

    # Re-load the provider module by file path so we can use its private helpers without
    # depending on package import names.
    spec = importlib.util.spec_from_file_location("asset_studio_openai_codex_edit", PROVIDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load openai-codex image provider")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    token = mod._read_codex_access_token()
    if not token:
        raise RuntimeError("No Codex/ChatGPT OAuth credentials available. Run hermes auth codex.")

    aspect, _size_px = aspect_from_image_data_url(image_data_url)
    tier_id, meta = mod._resolve_model()
    size = mod._SIZES.get(aspect, mod._SIZES["square"])
    edit_prompt = prompt if prompt_is_final else build_inpaint_prompt(prompt, negative)
    headers = _codex_cloudflare_headers(token)
    headers.update({
        "Accept": "text/event-stream",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    payload = {
        "model": mod._CODEX_CHAT_MODEL,
        "store": False,
        "instructions": "You are an image editor. Use the image_generation tool to edit the supplied image according to the mask and prompt.",
        "input": [{
            "type": "message",
            "role": "user",
            "content": [
                {"type": "input_text", "text": edit_prompt},
                {"type": "input_text", "text": "Original image:"},
                {"type": "input_image", "image_url": data_url_to_png_data_url(image_data_url)},
                {"type": "input_text", "text": "Mask image. White = edit area, black = protected area:"},
                {"type": "input_image", "image_url": data_url_to_png_data_url(mask_data_url)},
            ],
        }],
        "tools": [{
            "type": "image_generation",
            "model": mod.API_MODEL,
            "size": size,
            "quality": meta["quality"],
            "output_format": "png",
            "background": "opaque",
            "partial_images": 1,
        }],
        "tool_choice": {
            "type": "allowed_tools",
            "mode": "required",
            "tools": [{"type": "image_generation"}],
        },
        "stream": True,
    }

    image_b64 = None
    timeout = httpx.Timeout(300.0, connect=30.0, read=300.0, write=30.0, pool=30.0)
    with httpx.Client(timeout=timeout, headers=headers) as http:
        with http.stream("POST", f"{mod._CODEX_BASE_URL}/responses", json=payload) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                exc.response.read()
                raise RuntimeError(f"Codex edit API returned HTTP {exc.response.status_code}: {exc.response.text[:500]}") from exc
            for event in mod._iter_sse_json(response):
                found = mod._extract_image_b64(event)
                if found:
                    image_b64 = found

    if not image_b64:
        raise RuntimeError("Codex edit response contained no image result")
    return image_b64, tier_id, meta["quality"]


def collect_codex_replacement_b64(image_data_url: str, mask_data_url: str, prompt: str, negative: str = "") -> tuple[str, str, str]:
    """Reference-guided object replacement using the same image+mask edit path."""
    return collect_codex_edit_b64(image_data_url, mask_data_url, build_replace_object_prompt(prompt, negative), "", prompt_is_final=True)


def build_reference_sprite_prompt(prompt: str, negative: str = "", direction_mode: str = "single", reference_direction: str = "S", target_direction: str = "S", animation_mode: str = "idle", walk_frames: int = 4) -> str:
    neg = f"\nAvoid: {negative.strip()}" if negative and negative.strip() else ""
    direction_contract = ""
    if direction_mode == "8dir":
        direction_contract = """
Directional sprite-sheet contract:
- 8-direction output. Direction row order must be exactly: N, NE, E, SE, S, SW, W, NW.
- The supplied reference image direction is reference_direction={reference_direction}. Preserve that view most closely, then rotate the same character design into the other seven directions.
- Side rows must read as true side profiles. Back rows must remove front-only face/chest details.
- Keep identical scale, pivot, costume, outline thickness, palette, and lighting across all rows.""".format(reference_direction=reference_direction)
    elif direction_mode == "4dir":
        direction_contract = """
Directional sprite-sheet contract:
- 4-direction output. Direction row order must be exactly: S, W, E, N.
- The supplied reference image direction is reference_direction={reference_direction}. Preserve that view most closely, then rotate the same character design into the other directions.
- Side rows must read as true side profiles. Back row must remove front-only face/chest details.""".format(reference_direction=reference_direction)
    else:
        direction_contract = """
Single-target internal extraction sheet contract:
- Generate an internal extraction sheet as one horizontal row with separated candidates in exactly this left-to-right order: S, SW, W, NW, N, NE, E, SE.
- Direction meaning is screen-space: SW means the body turns toward screen-left while still showing front details; W means a true side profile facing screen-left; SE/E face screen-right.
- The app will crop and return only the requested target direction: target_direction={target_direction}.
- The supplied reference image direction is reference_direction={reference_direction}; use it for identity/style, then rotate the same character into the canonical candidate order.
- If target_direction is W or E, the corresponding candidate must be a true side profile, not a 3/4 front view.
- If target_direction is S, the corresponding candidate must face camera/front.
- Keep the candidates separated by green background gaps so postprocessing can isolate the selected slot.""".format(reference_direction=reference_direction, target_direction=target_direction)
    frame_contract = ""
    if animation_mode == "walk":
        frame_contract = f"""
Walk-cycle contract:
- Column order must be exactly: idle -> stepA -> idle -> stepB for 4-frame walk cycles.
- The column order must be preserved in every direction row.
- column order must be checked before accepting the sheet.
- Use {walk_frames} walk frames per direction.
- stepA and stepB must show opposite arm/leg phases, not just body bobbing.
- Feet positions must visibly alternate in every direction."""
    elif animation_mode == "idle":
        frame_contract = """
Idle contract:
- One readable idle frame per direction unless the user explicitly asks for breathing frames.
- Do not invent extra unrelated poses."""
    return f"""Create a new pixel-art game asset sprite sheet from the supplied reference image.

Reference contract:
- The input image is the source/reference character or asset. Keep the same identity, costume, silhouette language, palette, outline thickness, pixel scale, lighting, and camera angle.
- Generate the requested animation/asset sheet as a NEW output; do not merely upscale, crop, or copy the reference.
- Use evenly spaced sprite-sheet cells when animation frames are requested.
- Use a flat exact RGB(0,255,0) / #00FF00 chroma-key background edge-to-edge so the app can remove it after generation.
- No text, no numbers, no watermark, no mockup frame.
{direction_contract}
{frame_contract}

User request: {prompt.strip()}
{neg}""".strip()


def collect_codex_reference_sprite_b64(reference_data_url: str, prompt: str, negative: str = "", direction_mode: str = "single", reference_direction: str = "S", target_direction: str = "S", animation_mode: str = "idle", walk_frames: int = 4) -> tuple[str, str, str]:
    """Generate a new sprite/asset sheet while using the selected image as style/identity reference."""
    import httpx
    from agent.auxiliary_client import _codex_cloudflare_headers

    spec = importlib.util.spec_from_file_location("asset_studio_openai_codex_reference", PROVIDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load openai-codex image provider")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    token = mod._read_codex_access_token()
    if not token:
        raise RuntimeError("No Codex/ChatGPT OAuth credentials available. Run hermes auth codex.")

    tier_id, meta = mod._resolve_model()
    headers = _codex_cloudflare_headers(token)
    headers.update({
        "Accept": "text/event-stream",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    payload = {
        "model": mod._CODEX_CHAT_MODEL,
        "store": False,
        "instructions": "You generate pixel-art game assets from a supplied reference image. Preserve identity/style and output a clean chroma-green sprite sheet.",
        "input": [{
            "type": "message",
            "role": "user",
            "content": [
                {"type": "input_text", "text": build_reference_sprite_prompt(prompt, negative, direction_mode=direction_mode, reference_direction=reference_direction, target_direction=target_direction, animation_mode=animation_mode, walk_frames=walk_frames)},
                {"type": "input_text", "text": "Reference image to preserve identity/style:"},
                {"type": "input_image", "image_url": data_url_to_png_data_url(reference_data_url)},
            ],
        }],
        "tools": [{
            "type": "image_generation",
            "model": mod.API_MODEL,
            "size": mod._SIZES.get("square", "1024x1024"),
            "quality": meta["quality"],
            "output_format": "png",
            "background": "opaque",
            "partial_images": 1,
        }],
        "tool_choice": {
            "type": "allowed_tools",
            "mode": "required",
            "tools": [{"type": "image_generation"}],
        },
        "stream": True,
    }

    image_b64 = None
    timeout = httpx.Timeout(300.0, connect=30.0, read=300.0, write=30.0, pool=30.0)
    with httpx.Client(timeout=timeout, headers=headers) as http:
        with http.stream("POST", f"{mod._CODEX_BASE_URL}/responses", json=payload) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                exc.response.read()
                raise RuntimeError(f"Codex reference generation API returned HTTP {exc.response.status_code}: {exc.response.text[:500]}") from exc
            for event in mod._iter_sse_json(response):
                found = mod._extract_image_b64(event)
                if found:
                    image_b64 = found
    if not image_b64:
        raise RuntimeError("Codex reference generation response contained no image result")
    return image_b64, tier_id, meta["quality"]


def _extract_response_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        chunks = []
        for key in ("text", "output_text", "content"):
            if key in value:
                chunks.append(_extract_response_text(value[key]))
        if chunks:
            return "\n".join(c for c in chunks if c)
        return "\n".join(_extract_response_text(v) for v in value.values() if isinstance(v, (dict, list)))
    if isinstance(value, list):
        return "\n".join(_extract_response_text(v) for v in value)
    return ""


def _json_from_text(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        pass
    decoder = json.JSONDecoder()
    objects = []
    idx = 0
    while idx < len(text):
        start = text.find("{", idx)
        if start < 0:
            break
        try:
            obj, end = decoder.raw_decode(text[start:])
            if isinstance(obj, dict):
                objects.append(obj)
            idx = start + max(end, 1)
        except json.JSONDecodeError:
            idx = start + 1
    if objects:
        for obj in reversed(objects):
            if "pass" in obj and "observed" in obj:
                return obj
        return objects[-1]
    raise ValueError(f"No JSON object in response: {text[:300]}")


def classify_direction_candidate_with_codex_vision(raw_png: bytes, expected_direction: str) -> dict:
    """Direction QA contract: fail closed unless vision says the candidate matches."""
    import httpx
    from agent.auxiliary_client import _codex_cloudflare_headers

    expected_direction = (expected_direction or "S").upper()
    if expected_direction in {"E", "SE", "NE"}:
        return {"pass": False, "observed": expected_direction, "reason": "right-facing source is forbidden; derive by flip only"}

    spec = importlib.util.spec_from_file_location("asset_studio_openai_codex_direction_qa", PROVIDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load openai-codex provider for direction QA")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    token = mod._read_codex_access_token()
    if not token:
        raise RuntimeError("No Codex/ChatGPT OAuth credentials available for direction QA")

    headers = _codex_cloudflare_headers(token)
    headers.update({"Accept": "text/event-stream", "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    prompt = f"""Direction QA contract for a transparent pixel-art sprite.
Expected direction: {expected_direction}
Screen-space rules:
- W means true side profile facing screen-left.
- SW means front-left 3/4, face/body turned screen-left while front details remain visible.
- NW means back-left 3/4, mostly back/side turned screen-left, not screen-right.
- S means front-facing camera.
- N means back-facing away from camera.
Reject if ambiguous, if facing screen-right, if it is an E/SE/NE source, or if the view does not match.
Return only compact JSON: {{"pass": true/false, "observed": "S|N|W|SW|NW|E|SE|NE|ambiguous", "reason": "..."}}"""
    image_url = "data:image/png;base64," + base64.b64encode(raw_png).decode("ascii")
    payload = {
        "model": mod._CODEX_CHAT_MODEL,
        "store": False,
        "input": [{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": image_url},
        ]}],
        "stream": True,
    }
    timeout = httpx.Timeout(120.0, connect=30.0, read=120.0, write=30.0, pool=30.0)
    texts = []
    with httpx.Client(timeout=timeout, headers=headers) as http:
        with http.stream("POST", f"{mod._CODEX_BASE_URL}/responses", json=payload) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                exc.response.read()
                raise RuntimeError(f"Direction QA API returned HTTP {exc.response.status_code}: {exc.response.text[:500]}") from exc
            for event in mod._iter_sse_json(response):
                text = _extract_response_text(event)
                if text:
                    texts.append(text)
    parsed = _json_from_text("\n".join(texts))
    passed = bool(parsed.get("pass")) and str(parsed.get("observed", "")).upper() == expected_direction
    return {"pass": passed, "observed": str(parsed.get("observed", "ambiguous")).upper(), "reason": str(parsed.get("reason", "")), "raw": parsed}


def classify_sprite_sheet_consistency_with_codex_vision(sheet_png: bytes) -> dict:
    """Holistic sprite-set QA: fail closed on identity/equipment/proportion/crop mismatches."""
    import httpx
    from agent.auxiliary_client import _codex_cloudflare_headers

    spec = importlib.util.spec_from_file_location("asset_studio_openai_codex_sprite_set_qa", PROVIDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load openai-codex provider for sprite-set QA")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    token = mod._read_codex_access_token()
    if not token:
        raise RuntimeError("No Codex/ChatGPT OAuth credentials available for sprite-set QA")

    headers = _codex_cloudflare_headers(token)
    headers.update({"Accept": "text/event-stream", "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    prompt = """Sprite-set production QA contract for a top-down pixel-art game asset.
The sheet order is N, NE, E, SE, S, SW, W, NW.
Reject unless this looks like the SAME character rotated, not eight unrelated cuts.
Fail if any of these are visible:
- diagonal/front/back directions have noticeably different scale or body proportions
- backpack, weapon, hat, armor, colors, or silhouette change between directions
- equipment/backpack is clipped/cropped by the cell edge
- a direction looks like a different character, different camera angle, or painterly illustration
- feet/pivot alignment is unusable for a game sprite
- right-facing sprites are not clean mirrors of left-facing sprites
Return only compact JSON: {"pass": true/false, "reason": "...", "failures": ["..."]}"""
    image_url = "data:image/png;base64," + base64.b64encode(sheet_png).decode("ascii")
    payload = {
        "model": mod._CODEX_CHAT_MODEL,
        "store": False,
        "input": [{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": image_url},
        ]}],
        "stream": True,
    }
    timeout = httpx.Timeout(120.0, connect=30.0, read=120.0, write=30.0, pool=30.0)
    texts = []
    with httpx.Client(timeout=timeout, headers=headers) as http:
        with http.stream("POST", f"{mod._CODEX_BASE_URL}/responses", json=payload) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                exc.response.read()
                raise RuntimeError(f"Sprite-set QA API returned HTTP {exc.response.status_code}: {exc.response.text[:500]}") from exc
            for event in mod._iter_sse_json(response):
                text = _extract_response_text(event)
                if text:
                    texts.append(text)
    parsed = _json_from_text("\n".join(texts))
    return {"pass": bool(parsed.get("pass")), "reason": str(parsed.get("reason", "")), "failures": parsed.get("failures", []), "raw": parsed}



def select_valid_direction_candidate(direction: str, max_source_attempts: int, generate_fn, validate_fn) -> tuple[bytes, dict]:
    """Generate/validate candidates; fail closed if no direction-valid candidate passes."""
    attempts = []
    for attempt in range(1, max(1, int(max_source_attempts)) + 1):
        raw, generation_qa = generate_fn(direction, attempt)
        visual_qa = validate_fn(raw, direction)
        item = {"attempt": attempt, "generation_qa": generation_qa, "visual_direction_qa": visual_qa}
        attempts.append(item)
        if visual_qa.get("pass") is True:
            item["accepted"] = True
            return raw, {"accepted_attempt": attempt, "attempts": attempts, "visual_direction_qa": visual_qa}
    raise RuntimeError(f"No direction-valid candidate for {direction} after {max_source_attempts} attempts; fail closed")


def generate_reference_8dir_mirror_sheet(reference_data_url: str, prompt: str, negative: str = "", background_mode: str = "chroma_green", reference_direction: str = "S", chroma_mode: str = "global") -> tuple[bytes, str, str, dict]:
    """Web/API pipeline for 8-dir sprites: generate only 5 source views, mirror the right side.

    This intentionally never requests E/SE/NE from the model. Those views are exact
    flips of W/SW/NW, avoiding mixed right-facing source mistakes.
    """
    source_dirs = ["S", "N", "W", "SW", "NW"]
    source_prompt = {
        "S": "front-facing, looking straight toward camera/front; do not turn left or right",
        "N": "back-facing, looking away from camera; show back of head/body only, no face",
        "W": "true side profile facing screen-left only; absolutely not screen-right",
        "SW": "front-left three-quarter view facing screen-left while retaining front details; absolutely not screen-right",
        "NW": "back-left three-quarter view facing screen-left/back-left; mostly back/side, no front face; absolutely not screen-right",
    }
    source_pngs = {}
    source_qa = {}
    model = ""
    quality = ""
    max_source_attempts = int(os.environ.get("ASSET_STUDIO_DIRECTION_QA_ATTEMPTS", "3"))

    def make_candidate(direction: str, attempt: int):
        nonlocal model, quality
        attempt_hint = f"Attempt {attempt}/{max_source_attempts}: be stricter than prior attempts. " if attempt > 1 else ""
        image_b64, model, quality = collect_codex_reference_sprite_b64(
            reference_data_url,
            f"{prompt}\n\n{attempt_hint}Generate SOURCE DIRECTION {direction} only: {source_prompt[direction]}. Do not generate E, SE, or NE source sprites; right-facing views are created by app-side horizontal flip.",
            negative,
            direction_mode="single",
            reference_direction=reference_direction,
            target_direction=direction,
            animation_mode="idle",
            walk_frames=4,
        )
        processed, qa = postprocess_pixel_generation_bytes(
            base64.b64decode(image_b64),
            background_mode=background_mode,
            direction_mode="single",
            target_direction=direction,
            animation_mode="idle",
            chroma_mode=chroma_mode,
        )
        return processed, qa

    for direction in source_dirs:
        processed, qa = select_valid_direction_candidate(
            direction,
            max_source_attempts,
            make_candidate,
            classify_direction_candidate_with_codex_vision,
        )
        source_pngs[direction] = processed
        source_qa[direction] = qa
    sheet, qa = build_8dir_mirror_sheet_from_source_pngs(source_pngs, cell_size=420, layout="row")
    sprite_set_qa = {"status": "skipped", "reason": "ASSET_STUDIO_SPRITE_SET_VISION_QA=0"}
    if os.environ.get("ASSET_STUDIO_SPRITE_SET_VISION_QA", "1") != "0":
        sprite_set_qa = classify_sprite_sheet_consistency_with_codex_vision(sheet)
        if sprite_set_qa.get("pass") is not True:
            raise RuntimeError(f"sprite-set visual QA failed; fail closed: {sprite_set_qa}")
    qa["source_qa"] = source_qa
    qa["sprite_set_visual_qa"] = sprite_set_qa
    qa["direction_qa"] = {"status": "pass", "target_direction": "8dir", "method": "S/N/W/SW/NW sources + E/SE/NE flips"}
    return sheet, model, quality, qa


def image_to_data_url(img) -> str:
    out = io.BytesIO()
    img.save(out, format="PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")


def mask_bbox(mask, padding: int = 24) -> tuple[int, int, int, int]:
    mask = mask.convert("L")
    w, h = mask.size
    bbox = mask.point(lambda p: 255 if p > 8 else 0).getbbox()
    if not bbox:
        raise ValueError("Mask has no white/editable pixels")
    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(w, right + padding)
    bottom = min(h, bottom + padding)
    return left, top, right, bottom


def prepare_inpaint_crop(original_data_url: str, mask_data_url: str) -> tuple[str, str, dict]:
    from PIL import Image

    orig_raw, _ = data_url_to_bytes(original_data_url)
    mask_raw, _ = data_url_to_bytes(mask_data_url)
    original = Image.open(io.BytesIO(orig_raw)).convert("RGBA")
    mask = Image.open(io.BytesIO(mask_raw)).convert("L")
    if mask.size != original.size:
        mask = mask.resize(original.size, Image.Resampling.BILINEAR)
    left, top, right, bottom = mask_bbox(mask)
    crop = original.crop((left, top, right, bottom))
    mask_crop = mask.crop((left, top, right, bottom))
    bbox = {"x": left, "y": top, "width": right - left, "height": bottom - top}
    return image_to_data_url(crop), image_to_data_url(mask_crop.convert("RGB")), bbox


def composite_patch_with_mask(original_crop_data_url: str, mask_crop_data_url: str, generated_b64: str) -> bytes:
    from PIL import Image, ImageFilter

    orig_raw, _ = data_url_to_bytes(original_crop_data_url)
    mask_raw, _ = data_url_to_bytes(mask_crop_data_url)
    gen_raw = base64.b64decode(generated_b64)

    original = Image.open(io.BytesIO(orig_raw)).convert("RGBA")
    generated = Image.open(io.BytesIO(gen_raw)).convert("RGBA")
    if generated.size != original.size:
        generated = generated.resize(original.size, Image.Resampling.LANCZOS)
    mask = Image.open(io.BytesIO(mask_raw)).convert("L")
    if mask.size != original.size:
        mask = mask.resize(original.size, Image.Resampling.BILINEAR)
    alpha = mask.filter(ImageFilter.GaussianBlur(radius=0.8))
    patch = Image.composite(generated, original, alpha)
    # Patch layer must only contain editable pixels; original layer stays underneath.
    patch.putalpha(alpha)
    out = io.BytesIO()
    patch.save(out, format="PNG")
    return out.getvalue()


def replacement_patch_with_mask(original_crop_data_url: str, mask_crop_data_url: str, generated_b64: str) -> bytes:
    """Return generated pixels clipped to the edit mask, sized 1:1 to the crop bbox."""
    from PIL import Image, ImageFilter

    orig_raw, _ = data_url_to_bytes(original_crop_data_url)
    mask_raw, _ = data_url_to_bytes(mask_crop_data_url)
    gen_raw = base64.b64decode(generated_b64)

    original = Image.open(io.BytesIO(orig_raw)).convert("RGBA")
    generated = Image.open(io.BytesIO(gen_raw)).convert("RGBA")
    if generated.size != original.size:
        generated = generated.resize(original.size, Image.Resampling.LANCZOS)
    mask = Image.open(io.BytesIO(mask_raw)).convert("L")
    if mask.size != original.size:
        mask = mask.resize(original.size, Image.Resampling.BILINEAR)
    alpha = mask.filter(ImageFilter.GaussianBlur(radius=0.35))
    generated.putalpha(alpha)
    out = io.BytesIO()
    generated.save(out, format="PNG")
    return out.getvalue()


def classify_chat_command(message: str, context: dict | None = None, negative: str = "") -> dict:
    """Small local command router for the editor chat panel.

    This intentionally returns confirmable editor actions instead of executing anything
    server-side. It is deterministic so the editor remains useful without LLM access.
    """
    context = context or {}
    text = (message or "").strip()
    negative = (negative or "").strip()
    low = text.lower()
    selected_layer = context.get("selectedLayer") if isinstance(context.get("selectedLayer"), dict) else {}
    has_image = bool(selected_layer.get("type") == "image")
    has_mask = bool(context.get("mask", {}).get("count", 0))
    has_region = bool(context.get("regionSelection", {}).get("count", 0))

    def response(action, title, reply, params=None, requires_confirm=True):
        return {
            "success": True,
            "reply": reply,
            "action": {
                "type": action,
                "title": title,
                "params": params or {},
                "requires_confirm": requires_confirm,
            },
            "context_used": {
                "selectedLayer": context.get("selectedLayer"),
                "mask": context.get("mask"),
                "regionSelection": context.get("regionSelection"),
                "layerCount": context.get("layerCount"),
            },
        }

    if not text:
        return {"success": False, "error": "Message is required"}
    wants_export = any(k in low for k in ["내보내", "export", "png", "저장"])
    wants_bg_remove = any(k in low for k in ["배경 제거", "누끼", "remove bg", "remove background", "cutout"])
    if any(k in low for k in ["상태", "요약", "뭐 있어", "canvas state", "summary"]):
        selected = context.get("selectedLayer") or {"name": "선택 없음", "type": "none"}
        mask = context.get("mask") or {}
        return response(
            "state_summary",
            "현재 상태 요약",
            f"캔버스 {context.get('canvas', {}).get('width', '?')}×{context.get('canvas', {}).get('height', '?')}, 레이어 {context.get('layerCount', 0)}개, 선택 {selected.get('name')} / {selected.get('type')}, 마스크 {mask.get('count', 0)}개입니다.",
            {},
            False,
        )
    if wants_bg_remove and wants_export and has_image:
        mode = "sheet" if any(k in low for k in ["시트", "여러", "아이템", "스프라이트", "sheet", "sprite"]) else "ai"
        return response("plan", "배경 제거 후 PNG 내보내기", "2단계 실행 계획입니다. 확인하면 배경 제거를 시작하고, 완료 후 PNG 내보내기를 실행합니다.", {"actions": [{"type": "remove_bg", "params": {"mode": mode}}, {"type": "export_png", "params": {}}]})
    if any(k in low for k in ["투명", "transparent"]) and any(k in low for k in ["캔버스", "배경", "background"]):
        return response("transparent_canvas", "캔버스 배경 투명화", "캔버스 배경을 투명으로 바꿀 수 있습니다.")
    if any(k in low for k in ["체커", "checker"]):
        return response("toggle_checker", "체커보드 토글", "투명도 확인용 체커보드를 켜거나 끌 수 있습니다.")
    if any(k in low for k in ["배경 제거", "누끼", "remove bg", "remove background", "cutout"]):
        mode = "sheet" if any(k in low for k in ["시트", "여러", "아이템", "스프라이트", "sheet", "sprite"]) else "ai"
        if not has_image:
            return response("select_image_needed", "이미지 레이어 선택 필요", "배경 제거는 이미지 레이어 선택 후 실행할 수 있습니다. 먼저 이미지 레이어를 선택하세요.", {"tool": "select"}, False)
        return response("remove_bg", "이미지 배경 제거", f"선택 이미지에 {'에셋 시트' if mode == 'sheet' else 'AI Cutout'} 배경 제거를 실행합니다.", {"mode": mode})
    if any(k in low for k in ["오브젝트", "물체", "무기", "검", "곤봉", "칼", "도끼", "replace object", "object replacement"]):
        if any(k in low for k in ["치환", "교체", "바꿔", "replace", "swap", "만들", "생성"]):
            return response("execute_replace_object", "오브젝트 자동 치환/생성", "실행하면 AI Chat이 내부 오브젝트 치환 파이프라인을 호출합니다. 마스크가 있으면 참고 치환, 없으면 새 오브젝트 레이어 생성으로 처리합니다.", {"prompt": text, "negative": negative})
    if any(k in low for k in ["재생성", "inpaint", "수정", "바꿔", "고쳐"]):
        prompt = text
        if not has_image:
            return response("select_image_needed", "이미지 레이어 선택 필요", "선택영역 AI 재생성은 이미지 레이어 선택 후 가능합니다.", {"tool": "select"}, False)
        if has_region:
            return response("execute_inpaint", "선택영역 AI 수정 실행", "실행하면 현재 선택영역/마스크로 직접 재생성을 요청하고 결과 미리보기를 만듭니다.", {"prompt": prompt, "negative": negative})
        if not has_mask:
            return response("activate_region", "선택영역 필요", "먼저 영역 도구로 수정할 부분을 선택하세요. 영역 도구로 전환합니다.", {}, False)
        return response("execute_inpaint", "선택영역 AI 재생성 실행", "실행하면 현재 마스크 영역으로 직접 재생성을 요청하고 결과 미리보기를 만듭니다.", {"prompt": prompt, "negative": negative})
    if any(k in low for k in ["마스크", "mask"]):
        return response("activate_mask", "마스크 도구 전환", "마스크 도구로 전환합니다. 빨간 영역은 AI 수정 대상, 파란 영역은 앞가림 보존입니다.", {}, False)
    if any(k in low for k in ["선택영역", "선택 영역"]):
        return response("activate_region", "영역 도구 전환", "영역 도구로 전환합니다. 사각형/원형/올가미로 이미지 일부를 선택하세요.", {}, False)
    if any(k in low for k in ["생성", "generate", "만들어"]):
        return response("execute_generate", "AI 에셋 생성 실행", "실행하면 AI 생성 도구로 프롬프트를 보내 새 에셋 생성을 시작합니다.", {"prompt": text, "negative": negative})
    if any(k in low for k in ["내보내", "export", "png", "저장"]):
        return response("export_png", "PNG 내보내기", "현재 캔버스를 PNG로 내보냅니다.")
    if any(k in low for k in ["텍스트", "text", "글자"]):
        return response("activate_text", "텍스트 도구 전환", "텍스트 도구로 전환합니다.", {}, False)

    return response("explain", "명령 해석", "아직 자동 실행 가능한 명령으로 확정하지 못했습니다. 배경 제거, 투명 배경, 마스크, 선택영역 재생성, PNG 내보내기처럼 말해 주세요.", {}, False)


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def send_json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
            if path == "/api/upload-data-url":
                raw, ext = data_url_to_bytes(data.get("image", ""))
                name = f"upload_{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
                dst = UPLOADS / name
                dst.write_bytes(raw)
                return self.send_json(200, {"success": True, "url": f"/assets/uploads/{name}", "path": str(dst)})
            if path == "/api/remove-bg":
                raw, _ext = data_url_to_bytes(data.get("image", ""))
                tolerance = int(data.get("tolerance", 36))
                mode = str(data.get("mode", "ai"))
                chroma_mode = str(data.get("chroma_mode", "global"))
                out, method, qa = remove_background_bytes(raw, tolerance=tolerance, mode=mode, chroma_mode=chroma_mode)
                name = f"cutout_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
                dst = PROCESSED / name
                dst.write_bytes(out)
                return self.send_json(200, {
                    "success": True,
                    "url": f"/assets/processed/{name}",
                    "path": str(dst),
                    "method": method,
                    "qa": qa,
                    "chroma_mode": chroma_mode,
                })
            if path == "/api/inpaint":
                prompt = str(data.get("prompt", "")).strip()
                negative = str(data.get("negative", "")).strip()
                image = data.get("image", "")
                mask = data.get("mask", "")
                if not prompt:
                    return self.send_json(400, {"success": False, "error": "Prompt is required"})
                if not image or not mask:
                    return self.send_json(400, {"success": False, "error": "Image and mask are required"})
                crop_image, crop_mask, bbox = prepare_inpaint_crop(image, mask)
                generated_b64, model, quality = collect_codex_edit_b64(crop_image, crop_mask, prompt, negative)
                out = composite_patch_with_mask(crop_image, crop_mask, generated_b64)
                name = f"inpaint_patch_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
                dst = PROCESSED / name
                dst.write_bytes(out)
                return self.send_json(200, {
                    "success": True,
                    "url": f"/assets/processed/{name}",
                    "path": str(dst),
                    "bbox": bbox,
                    "patch_width": bbox["width"],
                    "patch_height": bbox["height"],
                    "model": model,
                    "quality": quality,
                    "method": "codex-crop-edit+transparent-mask-patch+1to1-bbox",
                })
            if path == "/api/replace-object":
                prompt = str(data.get("prompt", "")).strip()
                negative = str(data.get("negative", "")).strip()
                image = data.get("image", "")
                mask = data.get("mask", "")
                if not prompt:
                    return self.send_json(400, {"success": False, "error": "Prompt is required"})
                if not image or not mask:
                    return self.send_json(400, {"success": False, "error": "Image and mask are required"})
                crop_image, crop_mask, bbox = prepare_inpaint_crop(image, mask)
                generated_b64, model, quality = collect_codex_replacement_b64(crop_image, crop_mask, prompt, negative)
                out = replacement_patch_with_mask(crop_image, crop_mask, generated_b64)
                name = f"replacement_patch_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
                dst = PROCESSED / name
                dst.write_bytes(out)
                return self.send_json(200, {
                    "success": True,
                    "url": f"/assets/processed/{name}",
                    "path": str(dst),
                    "bbox": bbox,
                    "patch_width": bbox["width"],
                    "patch_height": bbox["height"],
                    "model": model,
                    "quality": quality,
                    "method": "codex-reference-object-replace+transparent-mask-patch+1to1-bbox",
                })
            if path == "/api/chat":
                message = str(data.get("message", ""))
                negative = str(data.get("negative", ""))
                context = data.get("context") if isinstance(data.get("context"), dict) else {}
                result = classify_chat_command(message, context, negative)
                return self.send_json(200 if result.get("success") else 400, result)
            if path == "/api/generate-reference":
                reference_image = data.get("reference_image") or data.get("image")
                if not reference_image:
                    return self.send_json(400, {"success": False, "error": "reference_image is required"})
                background_mode = data.get("background_mode", "chroma_green")
                prompt = build_prompt(
                    data.get("prompt", ""),
                    data.get("preset", "pixel"),
                    background_mode,
                )
                direction_mode = str(data.get("direction_mode", "single"))
                reference_direction = str(data.get("reference_direction", "S"))
                target_direction = str(data.get("target_direction", "S"))
                animation_mode = str(data.get("animation_mode", "idle"))
                chroma_mode = str(data.get("chroma_mode", "global"))
                if direction_mode == "8dir" and animation_mode == "idle":
                    out, model, quality, qa = generate_reference_8dir_mirror_sheet(
                        reference_image,
                        prompt,
                        data.get("negative", ""),
                        background_mode=background_mode,
                        reference_direction=reference_direction,
                        chroma_mode=chroma_mode,
                    )
                    name = f"reference_8dir_mirror_{int(time.time())}.png"
                    dst = GENERATED / name
                    dst.write_bytes(out)
                    return self.send_json(200, {"success": True, "url": f"/assets/generated/{name}", "path": str(dst), "model": model, "quality": quality, "provider": "openai-codex-reference", "background_mode": background_mode, "qa": qa, "method": f"reference-image-8dir-mirror+{qa.get('method', 'postprocess')}"})
                image_b64, model, quality = collect_codex_reference_sprite_b64(
                    reference_image,
                    prompt,
                    data.get("negative", ""),
                    direction_mode=direction_mode,
                    reference_direction=reference_direction,
                    target_direction=target_direction,
                    animation_mode=animation_mode,
                    walk_frames=int(data.get("walk_frames", 4) or 4),
                )
                raw = base64.b64decode(image_b64)
                out, qa = postprocess_pixel_generation_bytes(
                    raw,
                    background_mode=background_mode,
                    direction_mode=direction_mode,
                    target_direction=target_direction,
                    animation_mode=animation_mode,
                    chroma_mode=chroma_mode,
                )
                name = f"reference_generated_{int(time.time())}.png"
                dst = GENERATED / name
                dst.write_bytes(out)
                return self.send_json(200, {"success": True, "url": f"/assets/generated/{name}", "path": str(dst), "model": model, "quality": quality, "provider": "openai-codex-reference", "background_mode": background_mode, "qa": qa, "method": f"reference-image-sprite-generation+{qa.get('method', 'postprocess')}"})
            if path == "/api/generate":
                background_mode = data.get("background_mode", "none")
                prompt = build_prompt(
                    data.get("prompt", ""),
                    data.get("preset", "general"),
                    background_mode,
                )
                aspect = data.get("aspect_ratio") or "square"
                provider = load_provider()
                result = provider.generate(prompt, aspect_ratio=aspect)
                if not result.get("success"):
                    return self.send_json(500, {"success": False, "error": result.get("error") or str(result)})
                src = Path(result["image"])
                out, qa = postprocess_pixel_generation_bytes(
                    src.read_bytes(),
                    background_mode=background_mode,
                    direction_mode=str(data.get("direction_mode", "single")),
                    target_direction=str(data.get("target_direction", "S")),
                    animation_mode=str(data.get("animation_mode", "idle")),
                    chroma_mode=str(data.get("chroma_mode", "global")),
                )
                name = f"generated_{int(time.time())}_{src.name}"
                dst = GENERATED / name
                dst.write_bytes(out)
                return self.send_json(200, {"success": True, "url": f"/assets/generated/{name}", "path": str(dst), "model": result.get("model"), "provider": result.get("provider"), "background_mode": background_mode, "qa": qa, "method": f"generate+{qa.get('method', 'postprocess')}"})
            return self.send_json(404, {"success": False, "error": "Unknown API endpoint"})
        except Exception as e:
            return self.send_json(500, {"success": False, "error": str(e)})


if __name__ == "__main__":
    check_runtime_dependencies()
    os.chdir(ROOT)
    port = int(os.environ.get("PORT", "4184"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Serving Asset Studio on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()
