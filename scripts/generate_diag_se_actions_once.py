#!/usr/bin/env python3
from __future__ import annotations
import base64, io, json, time, urllib.request, shutil
from pathlib import Path
from PIL import Image, ImageDraw

API='http://127.0.0.1:4184/api/generate-reference'
BASE_OUT=Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/diag_se_actions')
BASE_OUT.mkdir(parents=True, exist_ok=True)
REF_SRC=Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/whitelist_walk4/walk4_refroot_aligned_1783567110.png')
img=Image.open(REF_SRC).convert('RGBA')
w,h=img.size; cell=w//4
ref=img.crop((0,0,cell,h))
buf=io.BytesIO(); ref.save(buf, format='PNG')
ref_data='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode('ascii')

COMMON='''Use the supplied S/front reference as the exact character identity, then rotate the SAME character into target direction SE/right-down diagonal (3/4 view facing screen-right and slightly toward camera). Do not keep pure front view. Do not turn into pure side profile.

Universal 7-lock requirements:
- Same hood, goggles, scarf, robe, pouch, broom/tool, palette, outline thickness, proportions, pixel density, and scale in every frame.
- Direction Lock: every frame must stay SE/right-down diagonal 3/4 view; no front/side/back drift.
- Root Lock: stable horizontal root/pelvis/head/torso center and stable foot baseline except vertical motion where explicitly requested.
- Equipment Lock: broom/tool remains attached to same hand/side; no swapped, dropped, stretched, or invented tool.
- Production Clean: one horizontal row, exactly 4 equal cells, wide #00FF00 gutters, flat chroma green background, no text, no numbers, no watermark, no mockup frame, no background scene.
- No baked VFX: no slash arcs, hit sparks, magic glow, particles, smoke, shockwaves, motion trails, detached debris, or background effects.'''

ACTIONS={
 'idle4': '''Create a STRICT 4-frame SE/right-down diagonal idle/breathing sprite sheet.
Frame beats: 1 neutral stance, 2 subtle breath-up, 3 neutral stance, 4 subtle breath-down.
PASS only if it reads as standing idle breathing in place with planted feet. If it reads as walking, attacking, dancing, or sliding, FAIL.''',
 'walk4': '''Create a STRICT 4-frame SE/right-down diagonal in-place walk sprite sheet.
Frame beats: 1 left-foot contact, 2 passing pose, 3 right-foot contact, 4 passing pose returning to frame 1.
PASS only if it reads as biped walking in place in SE 3/4 view, with alternating feet and opposite arm/tool swing around a stable root. If it reads as idle tapping, moonwalk, skating, dancing, horse-like gait, or body slide, FAIL.''',
 'attack4': '''Create a STRICT 4-frame SE/right-down diagonal attack sprite sheet.
Frame beats: 1 ready stance, 2 wind-up, 3 decisive broom/tool strike, 4 recover toward ready.
PASS only if it reads as an attack from pose/body/tool motion alone. If it reads as walking, idle, casting, dancing, or vague fidgeting, FAIL.''',
}

def post(payload):
    req=urllib.request.Request(API, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=420) as r:
        return json.loads(r.read().decode('utf-8'))

def make_checker(src:Path, dst:Path):
    im=Image.open(src).convert('RGBA'); bg=Image.new('RGBA', im.size, (34,34,38,255)); d=ImageDraw.Draw(bg); s=24
    for y in range(0, im.height, s):
        for x in range(0, im.width, s):
            d.rectangle([x,y,x+s-1,y+s-1], fill=(72,72,76,255) if ((x//s+y//s)%2) else (42,42,46,255))
    bg.alpha_composite(im); bg.save(dst)

def make_gifs(src:Path, stem:str, out_dir:Path, duration=150):
    im=Image.open(src).convert('RGBA'); w,h=im.size; frames=4; cell=w//frames
    cells=[im.crop((i*cell,0,w if i==frames-1 else (i+1)*cell,h)) for i in range(frames)]
    scale=max(1, int((max(cell,h)+319)//320)); canvas=(cell//scale, h//scale)
    frs=[c.resize(canvas, Image.Resampling.NEAREST) if scale>1 else c.copy() for c in cells]
    trans=[]
    for f in frs:
        p=f.convert('P', palette=Image.Palette.ADAPTIVE, colors=255)
        mask=Image.eval(f.getchannel('A'), lambda a:255 if a<=10 else 0)
        p.paste(255, mask); p.info['transparency']=255; trans.append(p)
    tp=out_dir/f'{stem}_transparent.gif'; trans[0].save(tp, save_all=True, append_images=trans[1:], duration=duration, loop=0, transparency=255, disposal=2)
    chk=[]
    for f in frs:
        bg=Image.new('RGBA', canvas, (34,34,38,255)); d=ImageDraw.Draw(bg); s=8
        for y in range(0,canvas[1],s):
            for x in range(0,canvas[0],s): d.rectangle([x,y,x+s-1,y+s-1], fill=(72,72,76,255) if ((x//s+y//s)%2) else (42,42,46,255))
        bg.alpha_composite(f); chk.append(bg.convert('P', palette=Image.Palette.ADAPTIVE, colors=128))
    cp=out_dir/f'{stem}_checker.gif'; chk[0].save(cp, save_all=True, append_images=chk[1:], duration=duration, loop=0, disposal=2)
    return str(tp), str(cp), {'gif_frames':len(frs),'canvas':canvas,'alignment':'preserve_cell_offsets','scale':scale}

def qa(path:Path):
    im=Image.open(path).convert('RGBA'); w,h=im.size; px=im.load(); cell=w//4
    corners=[px[0,0][3],px[w-1,0][3],px[0,h-1][3],px[w-1,h-1][3]]
    centers=[]; bottoms=[]; frames=[]
    for i in range(4):
        crop=im.crop((i*cell,0,w if i==3 else (i+1)*cell,h)); bbox=crop.getchannel('A').getbbox(); item={'frame':i+1,'bbox':bbox}
        if bbox:
            x0,y0,x1,y1=bbox; cx=(x0+x1)/2; centers.append(cx); bottoms.append(y1)
            item.update({'center':[round(cx,2),round((y0+y1)/2,2)],'bottom':y1,'size':[x1-x0,y1-y0]})
        frames.append(item)
    return {'size':[w,h],'corner_alpha':corners,'alpha_pass':corners==[0,0,0,0],'frames':frames,'anchor_metrics':{'bbox_center_x_range':round(max(centers)-min(centers),2) if centers else None,'bbox_bottom_range':max(bottoms)-min(bottoms) if bottoms else None}}

results=[]
for action, action_prompt in ACTIONS.items():
    out_dir=BASE_OUT/action; out_dir.mkdir(parents=True, exist_ok=True)
    prompt=COMMON+'\n\n'+action_prompt
    payload={
      'reference_image':ref_data,
      'prompt':prompt,
      'preset':'pixel',
      'aspect_ratio':'square',
      'background_mode':'chroma_green',
      'target_direction':'SE',
      'reference_direction':'S',
      'direction_mode':'single',
      'animation_mode':action,
      'frame_count':4,
      'walk_frames':4,
      'chroma_mode':'global',
      'asset_type':'character',
      'no_baked_vfx':True,
    }
    started=time.time(); res=post(payload)
    item={'action':action,'elapsed':round(time.time()-started,2),'response':res,'prompt':prompt}
    if res.get('success') and res.get('path'):
        stem=f'{action}_se_{int(time.time())}'
        dst=out_dir/f'{stem}.png'; shutil.copy2(res['path'], dst)
        chk=out_dir/f'{stem}_checker.png'; make_checker(dst, chk)
        tg,cg,gm=make_gifs(dst, stem, out_dir, duration=150 if action!='attack4' else 135)
        item.update({'success':True,'local_path':str(dst),'checker_path':str(chk),'transparent_gif':tg,'checker_gif':cg,'gif_meta':gm,'qa':qa(dst)})
    else:
        item.update({'success':False})
    (out_dir/f'{action}_result.json').write_text(json.dumps(item, ensure_ascii=False, indent=2))
    results.append(item)
print(json.dumps(results, ensure_ascii=False, indent=2))
