#!/usr/bin/env python3
import json
import time
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path('/Users/tajokim/asset-studio-local')
OUT_DIR = ROOT / 'assets' / 'generated' / 'action_presets'
OUT_DIR.mkdir(parents=True, exist_ok=True)
RESULT_PATH = ROOT / 'docs' / 'history' / 'artifacts' / 'ACTION_PRESET_GENERATION_RESULTS.json'
CONTACT_PATH = OUT_DIR / 'action_presets_contact_sheet.png'
API = 'http://127.0.0.1:4184/api/generate'

ACTIONS = [
    ('idle', 'idle4', 4, 'idle animation, 4-frame subtle breathing loop: 1 neutral stance; 2 subtle breath up; 3 neutral stance; 4 subtle breath down. PASS only if this reads as idle breathing: standing in place, planted feet, same facing/pivot/baseline, small body breathing motion only; otherwise FAIL.'),
    ('walk4', 'walk4', 4, 'simple RPG walk cycle, 4-frame neutral-left-neutral-right in-place walking animation: 1 neutral still/planted stance; 2 left/support foot step; 3 same neutral still/planted stance again; 4 right/opposite-support foot step. PASS only if frames 1 and 3 are visually near-identical neutral frames, frames 2 and 4 are opposite-foot/opposite-contact step poses, fixed pelvis/root anchor, stable head/torso center and foot baseline, held tool same hand/side; otherwise FAIL.'),
    ('walk6', 'walk6', 6, 'smooth walk cycle, 6-frame human biped in-place walking animation: 1 left-foot contact; 2 down-left; 3 passing-left; 4 right-foot contact; 5 down-right; 6 passing-right. PASS only if this reads as walking across all six frames with alternating contacts, connected passing beats, opposite arm/leg phases, fixed pelvis/root anchor, stable head/torso center and foot baseline, held tool same hand/side; otherwise FAIL.'),
    ('attack', 'attack4', 4, 'attack animation, 4 frames: 1 ready pose; 2 wind-up weapon/arm pulled back; 3 decisive strike pose; 4 recovery. PASS only if this reads as an attack with ordered ready/wind-up/strike/recovery body and weapon motion; otherwise FAIL.'),
    ('jump', 'jump4', 4, 'jump animation, 4 frames: 1 crouch anticipation; 2 takeoff extension; 3 airborne peak with clear vertical lift; 4 landing recovery. PASS only if this reads as a jump; otherwise FAIL.'),
    ('cast', 'cast4', 4, 'cast animation, 4 frames: 1 ready pose; 2 gather/anticipation with hands or stance; 3 clear release gesture; 4 recover. PASS only if this reads as spell/skill casting body language without relying on external VFX; otherwise FAIL.'),
    ('hurt', 'hurt4', 4, 'hurt animation, 4 frames: 1 normal pose; 2 impact flinch; 3 recoil away from hit; 4 recovery. PASS only if this reads as a hurt reaction with same facing, identity, palette, and equipment; otherwise FAIL.'),
    ('death', 'death4', 4, 'death animation, 4 frames: 1 alive/impact; 2 collapse in progress; 3 downed body; 4 final dead/still downed pose. PASS only if this reads as death/collapse using the same identity and palette; otherwise FAIL.'),
]

BASE_SUBJECT = 'small hooded dungeon cleanup worker with brass goggles and short tool, consistent dark fantasy pixel character, same identity every frame'
BASE_STYLE = 'refined 32-bit pixel art, dark muted palette, clean silhouette, game-ready sprite, hard pixel edges, no text, no numbers, no watermark'
CORE_LOCKS = 'Core animation locks before PASS: Identity Lock, Equipment Lock, Direction Lock, Root Lock, Motion Read, Loop Read, Production Clean. Every frame must be the same character moving from a stable root, not similar redraws; if any lock fails, mark FAIL even if the motion or alpha partially passes.'
BOUNDARY = CORE_LOCKS + ' single horizontal sprite sheet, one row only, evenly spaced cells, wide empty #00FF00 chroma green gutters, every body part, weapon, held object, shadow, and silhouette fully inside its own cell, 15 percent empty margin in each cell; visual QA uses whitelist acceptance: PASS only when the generated frames clearly match the requested action beats and preserve facing, identity, palette, equipment, pivot, baseline, and cell containment; if the dominant readable motion is not the requested action, mark FAIL; no VFX, slash arcs, hit sparks, magic glows, particles, smoke, shockwaves, detached debris, or motion trails because effects are separate game assets composited in-game'
CLEANUP = 'background must be flat exact #00FF00 chroma green edge-to-edge before postprocess; no visible rectangular cell boxes, no dark green residue, no chroma spill, no halo, no fringe'

def post_json(url, payload, timeout=240):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def image_qa(path: Path, frames: int):
    img = Image.open(path).convert('RGBA')
    w, h = img.size
    px = img.load()
    corner_alpha = [px[0,0][3], px[w-1,0][3], px[0,h-1][3], px[w-1,h-1][3]]
    green = 0
    opaque = 0
    for r,g,b,a in img.getdata():
        if a > 0:
            opaque += 1
            if g > 180 and r < 90 and b < 90:
                green += 1
    cell_w = max(1, w // frames)
    frame_opaque = []
    for i in range(frames):
        x0 = i * cell_w
        x1 = w if i == frames - 1 else (i + 1) * cell_w
        count = 0
        for y in range(h):
            for x in range(x0, x1):
                if px[x, y][3] > 0:
                    count += 1
        frame_opaque.append(count)
    return {
        'size': [w, h],
        'corner_alpha': corner_alpha,
        'green_pixels': green,
        'opaque_pixels': opaque,
        'frame_opaque_pixels': frame_opaque,
        'frame_count_expected': frames,
        'frame_count_observed_by_split': len(frame_opaque),
        'nonempty_frames': sum(1 for c in frame_opaque if c > 20),
        'alpha_pass': corner_alpha == [0, 0, 0, 0] and green == 0,
        'frame_pass': sum(1 for c in frame_opaque if c > 20) == frames,
    }

def make_contact_sheet(items):
    thumbs = []
    for item in items:
        if not item.get('local_path'):
            continue
        img = Image.open(item['local_path']).convert('RGBA')
        bg = Image.new('RGBA', img.size, (36,36,36,255))
        # checkerboard
        draw = ImageDraw.Draw(bg)
        s = 16
        for y in range(0, img.height, s):
            for x in range(0, img.width, s):
                col = (70,70,70,255) if ((x//s + y//s) % 2) else (40,40,40,255)
                draw.rectangle([x,y,x+s-1,y+s-1], fill=col)
        bg.alpha_composite(img)
        bg.thumbnail((512, 160), Image.Resampling.NEAREST)
        tile = Image.new('RGBA', (540, 210), (20,20,24,255))
        tile.alpha_composite(bg, ((540-bg.width)//2, 36))
        d = ImageDraw.Draw(tile)
        d.text((10, 8), f"{item['action']} / {item['animation_mode']} / {item['frames']}f", fill=(235,235,235,255))
        q = item.get('image_qa', {})
        d.text((10, 184), f"alpha:{q.get('alpha_pass')} frames:{q.get('nonempty_frames')}/{q.get('frame_count_expected')} cleanup:{item.get('cleanup_pass')}", fill=(210,210,210,255))
        thumbs.append(tile)
    if not thumbs:
        return None
    cols = 2
    rows = (len(thumbs)+cols-1)//cols
    sheet = Image.new('RGBA', (cols*540, rows*210), (12,12,14,255))
    for idx, tile in enumerate(thumbs):
        sheet.alpha_composite(tile, ((idx%cols)*540, (idx//cols)*210))
    sheet.save(CONTACT_PATH)
    return str(CONTACT_PATH)

def main():
    results = []
    for action, mode, frames, action_line in ACTIONS:
        prompt = f"{BASE_SUBJECT}\n{action_line}\n{BOUNDARY}\n{BASE_STYLE}\n{CLEANUP}"
        payload = {
            'prompt': prompt,
            'preset': 'pixel',
            'aspect_ratio': 'square',
            'background_mode': 'chroma_green',
            'target_direction': 'S',
            'reference_direction': 'S',
            'direction_mode': 'single',
            'animation_mode': mode,
            'frame_count': frames,
            'walk_frames': frames,
            'chroma_mode': 'global',
        }
        print(f'GENERATE {action} {mode} {frames}f', flush=True)
        started = time.time()
        item = {'action': action, 'animation_mode': mode, 'frames': frames, 'prompt': prompt, 'started_at': started}
        try:
            data = post_json(API, payload, timeout=300)
            item['response'] = data
            item['elapsed_sec'] = round(time.time() - started, 2)
            item['success'] = bool(data.get('success'))
            item['cleanup_pass'] = bool(data.get('qa', {}).get('cleanup_qa', {}).get('pass'))
            if data.get('path'):
                src = Path(data['path'])
                dst = OUT_DIR / f"{action}_{mode}_{int(time.time())}.png"
                dst.write_bytes(src.read_bytes())
                item['local_path'] = str(dst)
                item['image_qa'] = image_qa(dst, frames)
            print(f"DONE {action} success={item['success']} elapsed={item['elapsed_sec']} path={item.get('local_path')}", flush=True)
        except Exception as e:
            item['success'] = False
            item['error'] = repr(e)
            item['elapsed_sec'] = round(time.time() - started, 2)
            print(f"FAIL {action}: {e!r}", flush=True)
        results.append(item)
        RESULT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
    contact = make_contact_sheet(results)
    summary = {
        'generated_at': time.time(),
        'result_path': str(RESULT_PATH),
        'contact_sheet': contact,
        'total': len(results),
        'successes': sum(1 for r in results if r.get('success')),
        'alpha_passes': sum(1 for r in results if r.get('image_qa', {}).get('alpha_pass')),
        'frame_passes': sum(1 for r in results if r.get('image_qa', {}).get('frame_pass')),
        'cleanup_passes': sum(1 for r in results if r.get('cleanup_pass')),
        'items': results,
    }
    RESULT_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ['result_path','contact_sheet','total','successes','alpha_passes','frame_passes','cleanup_passes']}, indent=2), flush=True)

if __name__ == '__main__':
    main()
