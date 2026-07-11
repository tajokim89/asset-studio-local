#!/usr/bin/env python3
from __future__ import annotations
import base64, io, json, os, time, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw

API = 'http://127.0.0.1:4184/api/generate-reference'
RESULT = Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/goblin_ref_walk4/goblin_walk4_result.json')
OUT = Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/goblin_ref_walk4/per_frame')
OUT.mkdir(parents=True, exist_ok=True)

meta = json.loads(RESULT.read_text())
sheet = Image.open(meta['local_path']).convert('RGBA')
cell_w = sheet.width // 4
neutral = sheet.crop((0, 0, cell_w, sheet.height))
neutral_path = OUT / 'accepted_neutral.png'
neutral.save(neutral_path)

buf = io.BytesIO(); neutral.save(buf, format='PNG')
ref_data = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
mirrored_neutral = neutral.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
buf = io.BytesIO(); mirrored_neutral.save(buf, format='PNG')
mirrored_ref_data = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
annotated_neutral = Image.new('RGBA', neutral.size, (0, 255, 0, 255))
annotated_neutral.alpha_composite(neutral)
marker = ImageDraw.Draw(annotated_neutral)
# Instruction-only marker around the screen-right boot in the accepted neutral pose.
marker.ellipse((318, 455, 390, 540), outline=(0, 220, 255, 255), width=8)
marker.line((420, 420, 375, 465), fill=(0, 220, 255, 255), width=8)
marker.polygon([(375, 465), (382, 440), (398, 456)], fill=(0, 220, 255, 255))
buf = io.BytesIO(); annotated_neutral.save(buf, format='PNG')
annotated_ref_data = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')

BASE = '''Use the supplied sprite as the exact accepted identity, equipment, palette, pixel density, scale, and S/front-facing camera reference.
Generate exactly ONE isolated full-body pixel-art sprite pose, not a sprite sheet, not multiple characters, not a contact sheet.
Redraw the entire character as one coherent full-frame pose. Keep the same cap, face, sack, bottles, staff in the same hand/screen side, clothing, proportions, outline and lighting.
Keep the head, torso, pelvis and staff vertically aligned to the reference. Feet must remain visible. Flat exact #00FF00 background. No text, labels, numbers, floor, scenery, shadow, VFX or border.
This is one frame from a neutral → one-foot-cross → neutral → opposite-foot-cross RPG walk loop.'''

POSES = {
    # The image model repeatedly advances the visible screen-left boot. Generate frame 2 from a
    # whole-sprite mirrored reference, then flip the whole coherent result back. This restores
    # staff/sack handedness while converting the generated lead boot to screen-right.
    'frame2_screen_right': {
        'reference': mirrored_ref_data,
        'flip_back': True,
        'prompt': '''MIRRORED-REFERENCE STEP POSE: advance only the SCREEN-LEFT boot inward beneath the pelvis and visibly in front of the planted SCREEN-RIGHT leg. Make that screen-left sole the clear large/front boot. Keep the screen-right foot planted behind. Preserve every mirrored equipment side exactly.''',
    },
    'frame4_screen_left': {
        'reference': ref_data,
        'flip_back': False,
        'prompt': '''STEP POSE: advance only the SCREEN-LEFT boot inward beneath the pelvis and visibly in front of the planted SCREEN-RIGHT leg. Make that screen-left sole the clear large/front boot. Keep the screen-right foot planted behind. Preserve staff and sack sides exactly.''',
    },
}

if os.environ.get('ASSET_STUDIO_FRAME2_DIRECT') == '1':
    POSES['frame2_screen_right'] = {
        'reference': ref_data,
        'flip_back': False,
        'prompt': '''HARD SCREEN-COORDINATE STEP: advance ONLY the SCREEN-RIGHT boot toward the viewer. The large foreground sole and toes must be visibly on the RIGHT half of the pelvis centerline. Keep the SCREEN-LEFT boot small, planted and behind. Do not enlarge, lift or advance the screen-left boot. Preserve the staff on screen-left and sack on screen-right.''',
    }

if os.environ.get('ASSET_STUDIO_FRAME2_ANNOTATED') == '1':
    POSES['frame2_screen_right'] = {
        'reference': annotated_ref_data,
        'flip_back': False,
        'prompt': '''The cyan ring/arrow is an instruction marker only and must not appear in the output. It identifies the SCREEN-RIGHT boot that must swing forward. Advance ONLY that marked screen-right boot toward the viewer and inward beneath the pelvis; show its large sole and toes clearly on the right side. Keep the unmarked screen-left boot small, planted and behind. Preserve the exact goblin, staff on screen-left, sack on screen-right, palette and S/front view. Output no cyan, marker, ring, arrow, text or guide.''',
    }

def post(prompt: str, reference_image: str) -> dict:
    payload = {
        'reference_image': reference_image,
        'prompt': prompt,
        'preset': 'pixel',
        'aspect_ratio': 'square',
        'background_mode': 'chroma_green',
        'target_direction': 'S',
        'reference_direction': 'S',
        'direction_mode': 'single',
        'animation_mode': 'ui_static',
        'frame_count': 1,
        'walk_frames': 1,
        'chroma_mode': 'global',
        'asset_type': 'character',
        'no_baked_vfx': True,
    }
    last = None
    for attempt in range(3):
        req = urllib.request.Request(API, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=420) as r:
                return json.loads(r.read().decode())
        except Exception as exc:
            last = exc
            body = exc.read().decode('utf-8', 'ignore') if hasattr(exc, 'read') else ''
            print(f'API attempt {attempt + 1} failed: {exc} {body[:500]}', flush=True)
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
    raise RuntimeError(f'API failed after retries: {last}')

def place_on_cell(sprite: Image.Image, target: Image.Image, baseline: int, center_x: int, target_height: int):
    bbox = sprite.getchannel('A').getbbox()
    if not bbox:
        raise RuntimeError('empty generated sprite')
    crop = sprite.crop(bbox)
    # The one-frame endpoint returns a larger square canvas than a 4-cell sheet. Normalize the
    # complete coherent pose uniformly to the accepted neutral character height; never resize
    # or move an isolated limb.
    scale = target_height / crop.height
    scaled_size = (max(1, round(crop.width * scale)), target_height)
    crop = crop.resize(scaled_size, Image.Resampling.NEAREST)
    # Independent full-frame generations have no persistent canvas origin; align their production pivot at bottom-center.
    x = center_x - crop.width // 2
    y = baseline - crop.height
    target.alpha_composite(crop, (x, y))
    return {'source_bbox': bbox, 'placed_xy': [x, y], 'size': list(crop.size), 'uniform_scale': scale}

neutral_bbox = neutral.getchannel('A').getbbox()
if not neutral_bbox:
    raise RuntimeError('neutral frame empty')
baseline = neutral_bbox[3]
center_x = round((neutral_bbox[0] + neutral_bbox[2]) / 2)

outputs = {}
for key, job in POSES.items():
    path = OUT / f'{key}.png'
    only = os.environ.get('ASSET_STUDIO_ONLY')
    reuse = os.environ.get('ASSET_STUDIO_REUSE_PER_FRAME') == '1' or bool(only and only != key)
    if reuse and path.exists():
        res = {'success': True, 'path': str(path), 'method': 'reuse-existing-full-frame'}
        img = Image.open(path).convert('RGBA')
    else:
        res = post(BASE + '\n' + job['prompt'], job['reference'])
        if not res.get('success') or not res.get('path'):
            raise RuntimeError(json.dumps(res))
        img = Image.open(res['path']).convert('RGBA')
        if job['flip_back']:
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        img.save(path)
    outputs[key] = {'response': res, 'path': str(path), 'flip_back': job['flip_back']}

assembled = Image.new('RGBA', (cell_w * 4, neutral.height), (0,0,0,0))
assembled.alpha_composite(neutral, (0,0))
assembled.alpha_composite(neutral, (cell_w*2,0))
placements = {}
for idx, key in [(1, 'frame2_screen_right'), (3, 'frame4_screen_left')]:
    slot = Image.new('RGBA', neutral.size, (0,0,0,0))
    placements[key] = place_on_cell(Image.open(outputs[key]['path']).convert('RGBA'), slot, baseline, center_x, neutral_bbox[3] - neutral_bbox[1])
    assembled.alpha_composite(slot, (cell_w*idx, 0))

stamp = int(time.time())
png = OUT / f'goblin_walk4_per_frame_{stamp}.png'; assembled.save(png)
checker = Image.new('RGBA', assembled.size, (40,40,44,255)); d=ImageDraw.Draw(checker); s=24
for y in range(0,checker.height,s):
    for x in range(0,checker.width,s):
        d.rectangle((x,y,x+s-1,y+s-1), fill=(72,72,76,255) if (x//s+y//s)%2 else (42,42,46,255))
checker.alpha_composite(assembled); checker_path=OUT/f'goblin_walk4_per_frame_{stamp}_checker.png'; checker.save(checker_path)
frames=[assembled.crop((i*cell_w,0,(i+1)*cell_w,assembled.height)) for i in range(4)]
transparent_gif = OUT / f'goblin_walk4_per_frame_{stamp}_transparent.gif'
frames[0].save(transparent_gif, save_all=True, append_images=frames[1:], duration=170, loop=0, disposal=2, transparency=0)
gif_frames=[]
for fr in frames:
    bg=Image.new('RGBA',fr.size,(40,40,44,255)); bg.alpha_composite(fr); gif_frames.append(bg.convert('P',palette=Image.Palette.ADAPTIVE,colors=128))
gif=OUT/f'goblin_walk4_per_frame_{stamp}_checker.gif'; gif_frames[0].save(gif,save_all=True,append_images=gif_frames[1:],duration=170,loop=0,disposal=2)
alpha_channel = assembled.getchannel('A')
corner_alpha = [alpha_channel.getpixel((0,0)), alpha_channel.getpixel((assembled.width-1,0)), alpha_channel.getpixel((0,assembled.height-1)), alpha_channel.getpixel((assembled.width-1,assembled.height-1))]
report={'png':str(png),'checker':str(checker_path),'transparent_gif':str(transparent_gif),'gif':str(gif),'corner_alpha':corner_alpha,'neutral_bbox':neutral_bbox,'pivot':[center_x,baseline],'placements':placements,'outputs':outputs}
(OUT/'latest_result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({k:report[k] for k in ['png','checker','transparent_gif','gif','corner_alpha','neutral_bbox','pivot','placements']},ensure_ascii=False,indent=2))
