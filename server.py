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


def build_prompt(user_prompt: str, preset: str) -> str:
    user_prompt = (user_prompt or "").strip()
    preset = (preset or "general").strip()
    suffix = PRESET_SUFFIX.get(preset, PRESET_SUFFIX["general"])
    return f"""{user_prompt or 'Useful image asset'}

Asset Studio preset: {preset}
Guidance: {suffix}
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

def remove_background_bytes(raw: bytes, tolerance: int = 36, mode: str = "ai") -> tuple[bytes, str]:
    # AI segmentation is good for one subject, but it often drops most sprites in an asset sheet.
    # Sheet mode uses edge-aware border flood so all separated objects are preserved.
    if mode in {"sheet", "flood", "border"}:
        return edge_aware_sheet_remove(raw, tolerance=tolerance or 24), "preserve-mask-sheet"
    try:
        from rembg import remove
        return remove(raw), "rembg"
    except Exception as e:
        return fallback_corner_remove(raw, tolerance=tolerance), f"fallback:{type(e).__name__}"


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
                out, method = remove_background_bytes(raw, tolerance=tolerance, mode=mode)
                name = f"cutout_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
                dst = PROCESSED / name
                dst.write_bytes(out)
                return self.send_json(200, {
                    "success": True,
                    "url": f"/assets/processed/{name}",
                    "path": str(dst),
                    "method": method,
                })
            if path == "/api/inpaint":
                prompt = str(data.get("prompt", "")).strip()
                if not prompt:
                    return self.send_json(400, {"success": False, "error": "Prompt is required"})
                if not data.get("image") or not data.get("mask"):
                    return self.send_json(400, {"success": False, "error": "Image and mask are required"})
                # UI/API contract is in place. Real selected-area image editing will be wired in the next backend slice.
                return self.send_json(501, {
                    "success": False,
                    "error": "Selected-area AI backend is not connected yet. UI prompt/mask payload is ready for Phase 4 wiring.",
                })
            if path == "/api/generate":
                prompt = build_prompt(data.get("prompt", ""), data.get("preset", "general"))
                aspect = data.get("aspect_ratio") or "square"
                provider = load_provider()
                result = provider.generate(prompt, aspect_ratio=aspect)
                if not result.get("success"):
                    return self.send_json(500, {"success": False, "error": result.get("error") or str(result)})
                src = Path(result["image"])
                name = f"generated_{int(time.time())}_{src.name}"
                dst = GENERATED / name
                shutil.copy2(src, dst)
                return self.send_json(200, {"success": True, "url": f"/assets/generated/{name}", "path": str(dst), "model": result.get("model"), "provider": result.get("provider")})
            return self.send_json(404, {"success": False, "error": "Unknown API endpoint"})
        except Exception as e:
            return self.send_json(500, {"success": False, "error": str(e)})


if __name__ == "__main__":
    os.chdir(ROOT)
    port = int(os.environ.get("PORT", "4184"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Serving Asset Studio on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()
