#!/usr/bin/env python3
from __future__ import annotations
import json, time, urllib.request, shutil
from pathlib import Path
from PIL import Image, ImageDraw

API='http://127.0.0.1:4184/api/generate'
OUT=Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/whitelist_idle4')
OUT.mkdir(parents=True, exist_ok=True)

prompt='''small hooded dungeon cleanup worker with brass goggles and short broom/tool, same character in every frame

Create exactly one horizontal 4-frame sprite sheet for ACTION idle4, target direction S/front-facing.

WHITELIST PASS CONTRACT FOR IDLE:
PASS only if the sheet reads as an idle/breathing loop.
Required frame beats, left to right:
1 neutral standing pose
2 subtle breath-up pose: tiny torso/shoulder/head rise only
3 neutral standing pose again
4 subtle breath-down pose: tiny torso/shoulder/head settle only

Hard acceptance criteria:
- Every frame remains S/front-facing, looking toward camera/front.
- Feet remain planted on the same baseline; no stepping, no walking, no turning, no attack, no jump, no cast, no hurt, no death.
- Same identity, costume, goggles, hood, broom/tool, palette, outline thickness, proportions, pivot, and scale in all frames.
- Motion should be tiny and readable only as breathing/idle; body center should barely move.
- If the dominant readable action is not idle breathing, this is FAIL.

Sheet/layout:
- exactly 1 row x 4 evenly spaced cells, wide empty #00FF00 gutters.
- every body part/tool/shadow fully inside its own cell with at least 20% empty side margin.
- flat exact RGB(0,255,0) chroma green background edge-to-edge before postprocess.
- refined 32-bit pixel art, dark muted fantasy palette, clean silhouette, game-ready sprite.
- no text, no numbers, no watermark, no mockup frame, no VFX, no particles, no background scene.'''

payload={
  'prompt':prompt,
  'preset':'pixel',
  'aspect_ratio':'square',
  'background_mode':'chroma_green',
  'target_direction':'S',
  'reference_direction':'S',
  'direction_mode':'single',
  'animation_mode':'idle4',
  'frame_count':4,
  'walk_frames':4,
  'chroma_mode':'global',
  'asset_type':'character',
  'no_baked_vfx':True,
}

def post(payload):
    req=urllib.request.Request(API, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=360) as r:
        return json.loads(r.read().decode('utf-8'))

def checker(src:Path, dst:Path):
    img=Image.open(src).convert('RGBA')
    bg=Image.new('RGBA', img.size, (34,34,38,255))
    d=ImageDraw.Draw(bg); s=24
    for y in range(0,img.height,s):
        for x in range(0,img.width,s):
            col=(72,72,76,255) if ((x//s+y//s)%2) else (42,42,46,255)
            d.rectangle([x,y,x+s-1,y+s-1], fill=col)
    bg.alpha_composite(img)
    bg.save(dst)

def qa(path:Path):
    im=Image.open(path).convert('RGBA')
    w,h=im.size; px=im.load(); cell=w//4
    corners=[px[0,0][3],px[w-1,0][3],px[0,h-1][3],px[w-1,h-1][3]]
    stats=[]
    for i in range(4):
        crop=im.crop((i*cell,0,w if i==3 else (i+1)*cell,h))
        bbox=crop.getbbox()
        stats.append({'frame':i+1,'bbox':bbox,'opaque':sum(1 for p in crop.getdata() if p[3]>0)})
    return {'size':[w,h],'corner_alpha':corners,'alpha_pass':corners==[0,0,0,0],'frames':stats}

started=time.time()
res=post(payload)
out={'started':started,'elapsed':round(time.time()-started,2),'response':res,'prompt':prompt}
if not res.get('success') or not res.get('path'):
    out['success']=False
    (OUT/'idle4_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    raise SystemExit(json.dumps(out,ensure_ascii=False,indent=2))

src=Path(res['path'])
dst=OUT/f'idle4_whitelist_{int(time.time())}.png'
shutil.copy2(src,dst)
chk=OUT/f'idle4_whitelist_{int(time.time())}_checker.png'
checker(dst,chk)
out.update({'success':True,'local_path':str(dst),'checker_path':str(chk),'qa':qa(dst)})
(OUT/'idle4_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({'local_path':str(dst),'checker_path':str(chk),'qa':out['qa'],'elapsed':out['elapsed']},ensure_ascii=False,indent=2))
