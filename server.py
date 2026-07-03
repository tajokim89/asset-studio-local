#!/usr/bin/env python3
from __future__ import annotations

import base64
import importlib.util
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
