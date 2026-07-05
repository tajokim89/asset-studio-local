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


def collect_codex_edit_b64(image_data_url: str, mask_data_url: str, prompt: str, negative: str = "") -> tuple[str, str, str]:
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
    edit_prompt = build_inpaint_prompt(prompt, negative)
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


def classify_chat_command(message: str, context: dict | None = None) -> dict:
    """Small local command router for the editor chat panel.

    This intentionally returns confirmable editor actions instead of executing anything
    server-side. It is deterministic so the editor remains useful without LLM access.
    """
    context = context or {}
    text = (message or "").strip()
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
    if any(k in low for k in ["재생성", "inpaint", "수정", "바꿔", "고쳐"]):
        prompt = text
        if not has_image:
            return response("select_image_needed", "이미지 레이어 선택 필요", "선택영역 AI 재생성은 이미지 레이어 선택 후 가능합니다.", {"tool": "select"}, False)
        if has_region:
            return response("prepare_region_inpaint", "선택영역 AI 수정 준비", "현재 선택영역을 AI 수정 패널로 연결합니다. 프롬프트를 확인한 뒤 실행하세요.", {"prompt": prompt})
        if not has_mask:
            return response("activate_region", "선택영역 필요", "먼저 영역 도구로 수정할 부분을 선택하세요. 영역 도구로 전환합니다.", {}, False)
        return response("prepare_inpaint", "선택영역 AI 재생성 준비", "프롬프트를 직접 재생성 입력칸에 넣고 실행 준비를 합니다. 실제 생성은 확인 후 버튼으로 진행하세요.", {"prompt": prompt})
    if any(k in low for k in ["마스크", "mask"]):
        return response("activate_mask", "마스크 도구 전환", "마스크 도구로 전환합니다. 빨간 영역은 AI 수정 대상, 파란 영역은 앞가림 보존입니다.", {}, False)
    if any(k in low for k in ["선택영역", "선택 영역"]):
        return response("activate_region", "영역 도구 전환", "영역 도구로 전환합니다. 사각형/원형/올가미로 이미지 일부를 선택하세요.", {}, False)
    if any(k in low for k in ["생성", "generate", "만들어"]):
        return response("prepare_generate", "AI 에셋 생성 준비", "AI 생성 도구로 전환하고 프롬프트를 입력합니다. 실제 생성은 확인 후 실행하세요.", {"prompt": text})
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
                    "model": model,
                    "quality": quality,
                    "method": "codex-crop-edit+transparent-mask-patch",
                })
            if path == "/api/chat":
                message = str(data.get("message", ""))
                context = data.get("context") if isinstance(data.get("context"), dict) else {}
                result = classify_chat_command(message, context)
                return self.send_json(200 if result.get("success") else 400, result)
            if path == "/api/generate":
                prompt = build_prompt(
                    data.get("prompt", ""),
                    data.get("preset", "general"),
                    data.get("background_mode", "none"),
                )
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
