#!/usr/bin/env python3
from __future__ import annotations
import base64, io, json, time, urllib.request, shutil
from pathlib import Path
from PIL import Image, ImageDraw

API='http://127.0.0.1:4184/api/generate-reference'
OUT=Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/diag_se_base')
OUT.mkdir(parents=True, exist_ok=True)
REF_SRC=Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/whitelist_walk4/walk4_refroot_aligned_1783567110.png')
img=Image.open(REF_SRC).convert('RGBA')
w,h=img.size; cell=w//4
ref=img.crop((0,0,cell,h))
buf=io.BytesIO(); ref.save(buf, format='PNG')
ref_data='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode('ascii')

prompt='''Use the supplied front-facing reference only for identity and style.
Create exactly ONE static pixel-art game character sprite, not an animation sheet.

Target direction: SE / right-down diagonal 3/4 view.
The character must clearly face screen-right while still slightly toward the camera: visible near side and front plane, one shoulder slightly forward, feet angled diagonally, broom/tool held on the correct side.
Do NOT output pure front view. Do NOT output pure side profile. Do NOT output four directions or multiple poses.

Preserve identity: same small hooded dungeon cleanup worker, brass goggles, dark robe, scarf, pouch, short broom/tool, muted dark fantasy palette, refined 32-bit pixel art, clean silhouette.
Single centered sprite with enough transparent/chroma margin.
Flat exact RGB(0,255,0) chroma green background edge-to-edge before postprocess.
No text, no numbers, no watermark, no UI frame, no VFX, no particles, no background scene.'''

payload={
  'reference_image':ref_data,
  'prompt':prompt,
  'preset':'pixel',
  'aspect_ratio':'square',
  'background_mode':'chroma_green',
  'target_direction':'SE',
  'reference_direction':'S',
  'direction_mode':'single',
  'animation_mode':'ui_static',
  'frame_count':1,
  'walk_frames':1,
  'chroma_mode':'global',
  'asset_type':'character',
}

def post(payload):
    req=urllib.request.Request(API, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=420) as r:
        return json.loads(r.read().decode('utf-8'))

def make_checker(src:Path, dst:Path):
    im=Image.open(src).convert('RGBA')
    bg=Image.new('RGBA', im.size, (34,34,38,255))
    d=ImageDraw.Draw(bg); s=24
    for y in range(0, im.height, s):
        for x in range(0, im.width, s):
            d.rectangle([x,y,x+s-1,y+s-1], fill=(72,72,76,255) if ((x//s+y//s)%2) else (42,42,46,255))
    bg.alpha_composite(im); bg.save(dst)

def qa(path:Path):
    im=Image.open(path).convert('RGBA')
    w,h=im.size; px=im.load(); bbox=im.getchannel('A').getbbox()
    return {'size':[w,h],'corner_alpha':[px[0,0][3],px[w-1,0][3],px[0,h-1][3],px[w-1,h-1][3]],'bbox':bbox}

started=time.time(); res=post(payload)
out={'started':started,'elapsed':round(time.time()-started,2),'response':res,'prompt':prompt}
if not res.get('success') or not res.get('path'):
    out['success']=False
    (OUT/'se_base_result.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(json.dumps(out, ensure_ascii=False, indent=2))
stem=f'se_base_{int(time.time())}'
dst=OUT/f'{stem}.png'; shutil.copy2(res['path'], dst)
chk=OUT/f'{stem}_checker.png'; make_checker(dst, chk)
out.update({'success':True,'local_path':str(dst),'checker_path':str(chk),'qa':qa(dst)})
(OUT/'se_base_result.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(json.dumps({'local_path':str(dst),'checker_path':str(chk),'qa':out['qa'],'elapsed':out['elapsed']}, ensure_ascii=False, indent=2))
