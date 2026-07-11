#!/usr/bin/env python3
import json, time, urllib.request, math, zipfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageSequence

ROOT = Path('/Users/tajokim/asset-studio-local')
API = 'http://127.0.0.1:4184/api/generate'
OUT = Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/visualqa_regen')
SHEET_DIR = OUT / 'sheets'
GIF_DIR = OUT / 'gifs'
SHEET_DIR.mkdir(parents=True, exist_ok=True)
GIF_DIR.mkdir(parents=True, exist_ok=True)

BASE_SUBJECT = 'small hooded dungeon cleanup worker with brass goggles and short tool, consistent dark fantasy pixel character, same identity every frame'
STYLE = 'refined 32-bit pixel art, dark muted palette, clean silhouette, game-ready sprite, hard pixel edges, no text, no numbers, no watermark'
COMMON = '''Whitelist QA: PASS only when the generated frames clearly match the requested action beats below and preserve S/front-facing direction, identity, palette, equipment, pivot, baseline, and cell containment. If the dominant readable motion is not the requested action, mark FAIL.
No VFX: character body/weapon/hand pose animation only. Do not include slash arcs, hit sparks, magic glows, particles, smoke, shockwaves, detached debris, motion trails, aura, impact symbols, blood, or background effects.
Cell safety: one horizontal sprite sheet, one row only, exact requested frame count, evenly spaced cells, wide empty #00FF00 chroma green gutters, at least 20 percent empty side margin in each cell, no body/weapon pixels crossing cell boundaries.
Background must be flat exact #00FF00 chroma green edge-to-edge before postprocess; no visible rectangular cell boxes, no dark green residue, no chroma spill, no halo, no fringe.'''
ACTIONS = [
    ('idle', 'idle4', 4, 'Idle action: frames are neutral stance, subtle breath up, neutral stance, subtle breath down. PASS only if this reads as idle breathing with planted feet, same facing/pivot/baseline, and small body breathing motion only; otherwise FAIL.'),
    ('walk4', 'walk4', 4, 'Walk action: frames are contact-left, passing-left, contact-right, passing-right. PASS only if this reads as a human biped in-place walk with alternating left/right foot contacts, connected passing beats, opposite arm/leg phases, fixed pelvis/root anchor, stable head/torso center and foot baseline, and held tool on the same hand/side; otherwise FAIL.'),
    ('walk6', 'walk6', 6, 'Walk action: frames are contact-left, down-left, passing-left, contact-right, down-right, passing-right. PASS only if this reads as a six-phase human biped in-place walk with alternating contacts, connected passing/down beats, opposite arm/leg phases, fixed pelvis/root anchor, stable head/torso center and foot baseline, and held tool on the same hand/side; otherwise FAIL.'),
    ('attack', 'attack4', 4, 'Attack action: frames are ready, wind-up, decisive strike, recovery. PASS only if this reads as an attack with ordered ready/wind-up/strike/recovery body and weapon motion; otherwise FAIL.'),
    ('jump', 'jump4', 4, 'Jump action: frames are crouch anticipation, takeoff extension, airborne peak, landing recovery. PASS only if this reads as jumping with clear vertical lift and return; otherwise FAIL.'),
    ('cast', 'cast4', 4, 'Cast action: frames are ready, gather/anticipation, release gesture, recovery. PASS only if this reads as spell/skill casting body language from pose alone; otherwise FAIL.'),
    ('hurt', 'hurt4', 4, 'Hurt action: frames are normal pose, impact flinch, recoil away from hit, recovery. PASS only if this reads as a hurt reaction while preserving facing, identity, palette, and equipment; otherwise FAIL.'),
    ('death', 'death4', 4, 'Death action: frames are alive/impact, collapse in progress, downed body, final dead/still downed pose. PASS only if this reads as death/collapse using the same identity and palette; otherwise FAIL.'),
]

def post(payload):
    req = urllib.request.Request(API, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=320) as r:
        return json.loads(r.read().decode())

def qa(path, frames):
    img = Image.open(path).convert('RGBA')
    w, h = img.size
    px = img.load()
    cell = w // frames
    corners = [px[0, 0][3], px[w - 1, 0][3], px[0, h - 1][3], px[w - 1, h - 1][3]]
    frame_stats = []
    for i in range(frames):
        x0 = i * cell
        x1 = w if i == frames - 1 else (i + 1) * cell
        crop = img.crop((x0, 0, x1, h))
        bbox = crop.getbbox()
        opaque = []
        if bbox:
            for r, g, b, a in crop.crop(bbox).getdata():
                if a > 0:
                    opaque.append((r, g, b, a))
        if opaque:
            n = len(opaque)
            avg = [sum(p[j] for p in opaque) / n for j in range(3)]
            red_ratio = sum(1 for r, g, b, a in opaque if r > 130 and r > g * 1.35 and r > b * 1.35) / n
        else:
            avg = [0, 0, 0]
            red_ratio = 0
        frame_stats.append({'opaque': len(opaque), 'avg_rgb': [round(x, 1) for x in avg], 'red_ratio': round(red_ratio, 4), 'bbox': bbox})
    base = frame_stats[0]['avg_rgb']
    drift = [max(abs(st['avg_rgb'][i] - base[i]) for i in range(3)) for st in frame_stats]
    return {
        'size': [w, h],
        'corner_alpha': corners,
        'alpha_pass': corners == [0, 0, 0, 0],
        'frames': frames,
        'frame_stats': frame_stats,
        'max_avg_color_drift': round(max(drift), 1),
        'max_red_ratio': max(st['red_ratio'] for st in frame_stats),
        'nonempty_frames': sum(1 for st in frame_stats if st['opaque'] > 20),
    }

def make_gifs(src, name, frames):
    img = Image.open(src).convert('RGBA')
    w, h = img.size
    cell = w // frames
    # Preserve original cell-relative offsets; do not crop each frame and
    # bbox-center it. bbox-centering can hide root drift and create a false
    # horse-like bouncing preview.
    cells = []
    for i in range(frames):
        c = img.crop((i * cell, 0, w if i == frames - 1 else (i + 1) * cell, h))
        cells.append(c)
    maxdim = max(cell, h)
    scale = math.ceil(maxdim / 320) if maxdim > 360 else 1
    frs = [c.resize((c.width // scale, c.height // scale), Image.Resampling.NEAREST) if scale > 1 else c.copy() for c in cells]
    dur = 150 if frames <= 4 else 110
    def checker(size):
        bg = Image.new('RGBA', size, (36, 36, 36, 255))
        d = ImageDraw.Draw(bg)
        s = 8
        for y in range(0, size[1], s):
            for x in range(0, size[0], s):
                d.rectangle([x, y, x + s - 1, y + s - 1], fill=(72, 72, 76, 255) if ((x // s + y // s) % 2) else (42, 42, 46, 255))
        return bg
    chk = []
    for f in frs:
        bg = checker(f.size)
        bg.alpha_composite(f)
        chk.append(bg.convert('P', palette=Image.Palette.ADAPTIVE, colors=128))
    checker_path = GIF_DIR / f'{name}_checker.gif'
    chk[0].save(checker_path, save_all=True, append_images=chk[1:], duration=dur, loop=0, disposal=2)
    trans = []
    for f in frs:
        p = f.convert('P', palette=Image.Palette.ADAPTIVE, colors=255)
        mask = Image.eval(f.getchannel('A'), lambda a: 255 if a <= 10 else 0)
        p.paste(255, mask)
        p.info['transparency'] = 255
        trans.append(p)
    trans_path = GIF_DIR / f'{name}_transparent.gif'
    trans[0].save(trans_path, save_all=True, append_images=trans[1:], duration=dur, loop=0, transparency=255, disposal=2)
    return checker_path, trans_path

def main():
    results = []
    for action, mode, frames, line in ACTIONS:
        prompt = f'{BASE_SUBJECT}\n{line}\n{COMMON}\n{STYLE}'
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
        print('GENERATE', action, flush=True)
        started = time.time()
        data = post(payload)
        elapsed = round(time.time() - started, 2)
        src = Path(data['path'])
        dst = SHEET_DIR / f'{action}_{mode}_{int(time.time())}.png'
        dst.write_bytes(src.read_bytes())
        item = {'action': action, 'mode': mode, 'frames': frames, 'prompt': prompt, 'sheet': str(dst), 'elapsed_sec': elapsed, 'api_success': data.get('success'), 'api_qa': data.get('qa', {}), 'qa': qa(dst, frames)}
        checker, trans = make_gifs(dst, f'{action}_{mode}_{frames}f', frames)
        item['checker_gif'] = str(checker)
        item['transparent_gif'] = str(trans)
        for key in ['checker_gif', 'transparent_gif']:
            im = Image.open(item[key])
            item[key + '_frames'] = sum(1 for _ in ImageSequence.Iterator(im))
            item[key + '_bytes'] = Path(item[key]).stat().st_size
        results.append(item)
        print('DONE', action, json.dumps({'qa': item['qa'], 'gif_frames': item['checker_gif_frames']}, ensure_ascii=False), flush=True)
    thumbs = []
    for item in results:
        img = Image.open(item['sheet']).convert('RGBA')
        bg = Image.new('RGBA', img.size, (36, 36, 36, 255))
        d = ImageDraw.Draw(bg)
        s = 16
        for y in range(0, img.height, s):
            for x in range(0, img.width, s):
                d.rectangle([x, y, x + s - 1, y + s - 1], fill=(70, 70, 70, 255) if ((x // s + y // s) % 2) else (40, 40, 40, 255))
        bg.alpha_composite(img)
        bg.thumbnail((760, 190), Image.Resampling.NEAREST)
        tile = Image.new('RGBA', (800, 250), (18, 18, 22, 255))
        tile.alpha_composite(bg, ((800 - bg.width) // 2, 38))
        dd = ImageDraw.Draw(tile)
        q = item['qa']
        dd.text((10, 8), f"{item['action']} {item['mode']} {item['frames']}f alpha:{q['alpha_pass']} colorDrift:{q['max_avg_color_drift']} red:{q['max_red_ratio']}", fill=(235, 235, 235, 255))
        thumbs.append(tile)
    contact = OUT / 'visualqa_regen_contact_sheet.png'
    sheet = Image.new('RGBA', (800, 250 * len(thumbs)), (12, 12, 14, 255))
    for i, t in enumerate(thumbs):
        sheet.alpha_composite(t, (0, i * 250))
    sheet.save(contact)
    manifest = OUT / 'manifest.json'
    manifest.write_text(json.dumps({'items': results, 'contact_sheet': str(contact)}, indent=2, ensure_ascii=False), encoding='utf-8')
    zip_path = OUT / 'visualqa_regen_gifs_and_sheets.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(manifest, manifest.name)
        z.write(contact, contact.name)
        for item in results:
            for key in ['sheet', 'checker_gif', 'transparent_gif']:
                z.write(item[key], Path(item[key]).name)
    print(json.dumps({'manifest': str(manifest), 'contact': str(contact), 'zip': str(zip_path), 'count': len(results)}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
