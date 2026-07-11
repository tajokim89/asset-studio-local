#!/usr/bin/env python3
from __future__ import annotations
import base64, io, json, time, urllib.request, shutil
from pathlib import Path
from PIL import Image, ImageDraw

API='http://127.0.0.1:4184/api/generate-reference'
OUT=Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/whitelist_jump4')
OUT.mkdir(parents=True, exist_ok=True)
REF_SRC=Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/whitelist_walk4/walk4_refroot_aligned_1783567110.png')

img=Image.open(REF_SRC).convert('RGBA')
w,h=img.size
cell=w//4
ref=img.crop((0,0,cell,h))
buf=io.BytesIO(); ref.save(buf, format='PNG')
ref_data='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode('ascii')

prompt='''Use the supplied reference as the exact character identity.
Generate a STRICT 4-frame S/front-facing jump sprite sheet for this same hooded dungeon cleanup worker with broom/tool.

Critical registration requirement: every frame must keep the same S/front-facing direction and same character identity. Keep the horizontal head/torso/pelvis center nearly fixed. For jump, vertical movement is allowed and required, but horizontal sliding is not allowed.

Frame beats left to right:
1 crouch anticipation: knees bent / body compressed, feet on ground, broom/tool kept attached
2 takeoff: legs extend, body rising from ground, clear upward motion
3 airborne peak: body clearly above ground/baseline, feet lifted, still front-facing
4 landing/recovery: feet return to ground, body compresses slightly, connects back to crouch/idle

PASS only if it reads as a jump from pose/body movement alone. If it reads as walking, idle bobbing, dancing, flailing, attack, or vague fidgeting, it is FAIL.

Same hood, goggles, scarf, robe, pouch, broom/tool, palette, outline thickness, proportions, scale, and S/front-facing direction in every frame. Broom/tool stays attached to the same hand/side and does not become a new object.
No baked VFX: no dust clouds, impact sparks, magic glow, particles, smoke, shockwaves, motion trails, detached debris, or background effects.
One horizontal row, exactly 4 equal cells, wide #00FF00 gutters, flat chroma green background, no text, no numbers, no watermark, no mockup frame, no background scene.'''

payload={
  'reference_image':ref_data,
  'prompt':prompt,
  'preset':'pixel',
  'aspect_ratio':'square',
  'background_mode':'chroma_green',
  'target_direction':'S',
  'reference_direction':'S',
  'direction_mode':'single',
  'animation_mode':'jump4',
  'frame_count':4,
  'walk_frames':4,
  'chroma_mode':'global',
  'asset_type':'character',
  'no_baked_vfx':True,
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

def make_gifs(src:Path, stem:str):
    im=Image.open(src).convert('RGBA')
    w,h=im.size; frames=4; cell=w//frames
    cells=[im.crop((i*cell,0,w if i==frames-1 else (i+1)*cell,h)) for i in range(frames)]
    scale=max(1, int((max(cell,h)+319)//320))
    canvas=(cell//scale, h//scale)
    frs=[c.resize(canvas, Image.Resampling.NEAREST) if scale>1 else c.copy() for c in cells]
    trans=[]
    for f in frs:
        p=f.convert('P', palette=Image.Palette.ADAPTIVE, colors=255)
        mask=Image.eval(f.getchannel('A'), lambda a: 255 if a<=10 else 0)
        p.paste(255, mask); p.info['transparency']=255
        trans.append(p)
    trans_path=OUT/f'{stem}_transparent.gif'
    trans[0].save(trans_path, save_all=True, append_images=trans[1:], duration=155, loop=0, transparency=255, disposal=2)
    chk=[]
    for f in frs:
        bg=Image.new('RGBA', canvas, (34,34,38,255)); d=ImageDraw.Draw(bg); s=8
        for y in range(0, canvas[1], s):
            for x in range(0, canvas[0], s):
                d.rectangle([x,y,x+s-1,y+s-1], fill=(72,72,76,255) if ((x//s+y//s)%2) else (42,42,46,255))
        bg.alpha_composite(f); chk.append(bg.convert('P', palette=Image.Palette.ADAPTIVE, colors=128))
    chk_path=OUT/f'{stem}_checker.gif'
    chk[0].save(chk_path, save_all=True, append_images=chk[1:], duration=155, loop=0, disposal=2)
    return str(trans_path), str(chk_path), {'gif_frames':len(frs),'canvas':canvas,'alignment':'preserve_cell_offsets','scale':scale}

def qa(path:Path):
    im=Image.open(path).convert('RGBA')
    w,h=im.size; px=im.load(); cell=w//4
    corners=[px[0,0][3],px[w-1,0][3],px[0,h-1][3],px[w-1,h-1][3]]
    centers=[]; bottoms=[]; tops=[]; frames=[]
    for i in range(4):
        crop=im.crop((i*cell,0,w if i==3 else (i+1)*cell,h))
        bbox=crop.getchannel('A').getbbox(); item={'frame':i+1,'bbox':bbox}
        if bbox:
            x0,y0,x1,y1=bbox
            centers.append((x0+x1)/2); bottoms.append(y1); tops.append(y0)
            item.update({'center':[round((x0+x1)/2,2),round((y0+y1)/2,2)],'top':y0,'bottom':y1,'size':[x1-x0,y1-y0]})
        frames.append(item)
    return {'size':[w,h],'corner_alpha':corners,'alpha_pass':corners==[0,0,0,0],'frames':frames,'anchor_metrics':{'bbox_center_x_range':round(max(centers)-min(centers),2) if centers else None,'bbox_top_range':max(tops)-min(tops) if tops else None,'bbox_bottom_range':max(bottoms)-min(bottoms) if bottoms else None}}

started=time.time()
res=post(payload)
out={'started':started,'elapsed':round(time.time()-started,2),'response':res,'prompt':prompt}
if not res.get('success') or not res.get('path'):
    out['success']=False
    (OUT/'jump4_result.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(json.dumps(out, ensure_ascii=False, indent=2))

stem=f'jump4_refroot_{int(time.time())}'
dst=OUT/f'{stem}.png'
shutil.copy2(res['path'], dst)
chk=OUT/f'{stem}_checker.png'
make_checker(dst, chk)
trans_gif, checker_gif, gif_meta=make_gifs(dst, stem)
out.update({'success':True,'local_path':str(dst),'checker_path':str(chk),'transparent_gif':trans_gif,'checker_gif':checker_gif,'gif_meta':gif_meta,'qa':qa(dst)})
(OUT/'jump4_result.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(json.dumps({'local_path':str(dst),'checker_path':str(chk),'transparent_gif':trans_gif,'checker_gif':checker_gif,'qa':out['qa'],'elapsed':out['elapsed']}, ensure_ascii=False, indent=2))
