#!/usr/bin/env python3
from __future__ import annotations
import base64, io, json, time, urllib.request, shutil
from pathlib import Path
from PIL import Image, ImageDraw

API='http://127.0.0.1:4184/api/generate-reference'
BASE_OUT=Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/diag_se_actions_v2')
BASE_OUT.mkdir(parents=True, exist_ok=True)
REF_SRC=Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/diag_se_base/se_base_1783575206.png')
img=Image.open(REF_SRC).convert('RGBA')
buf=io.BytesIO(); img.save(buf, format='PNG')
ref_data='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode('ascii')

COMMON='''Use the supplied SE/right-down diagonal 3/4 character as the exact reference pose and identity.
Do NOT rotate from front. Preserve the same SE 3/4 facing angle in every frame: face/body angled screen-right and slightly toward camera.

Universal locks:
- Same hood, brass goggles, dark robe, scarf, pouch, broom/tool, palette, outline thickness, proportions, pixel density, and scale in every frame.
- Direction Lock: every frame remains SE/right-down diagonal 3/4 view; no pure front, no pure side, no back, no direction drift.
- Root Lock: keep head/goggles/torso/pelvis horizontally anchored; no whole-body slide inside cells.
- Equipment Lock: broom/tool remains attached to the same hand/side and does not become a different object.
- Production Clean: one horizontal row, exactly 4 equal cells, wide #00FF00 gutters, flat chroma green background, no text/numbers/watermark/UI/background.
- No baked VFX, particles, slash arcs, smoke, dust, motion trails, or detached debris.'''

ACTIONS={
 'idle4': '''Create a 4-frame SE idle breathing loop.
Frame 1 neutral, frame 2 subtle chest/shoulder/hood lift, frame 3 neutral, frame 4 subtle breath down.
Feet planted. Broom planted. Only tiny upper-body breathing; no walking, no attack, no sliding.
PASS only if it reads as breathing idle.''',
 'walk4': '''Create a 4-frame SE in-place walk loop.
Frame 1 near/front foot contact, frame 2 passing, frame 3 far/back foot contact, frame 4 passing back to loop.
Both feet must visibly alternate. The body stays centered while legs and arms/tool counter-swing. Do not keep one foot forward for every frame.
PASS only if left/right foot contacts alternate and it reads as walking, not foot tapping.''',
 'attack4': '''Create a 4-frame SE attack loop using the broom/tool.
Frame 1 ready stance, frame 2 clear wind-up, frame 3 decisive strike pose, frame 4 recover toward ready.
Attack must read from body/tool pose alone. No VFX or slash arc. Head stays stable enough to read as same character.
PASS only if ready-windup-strike-recover is clear.''',
}

def post(payload):
    req=urllib.request.Request(API, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=420) as r:
        return json.loads(r.read().decode('utf-8'))

def checker(src:Path, dst:Path):
    im=Image.open(src).convert('RGBA'); bg=Image.new('RGBA', im.size, (34,34,38,255)); d=ImageDraw.Draw(bg); s=24
    for y in range(0,im.height,s):
        for x in range(0,im.width,s): d.rectangle([x,y,x+s-1,y+s-1], fill=(72,72,76,255) if ((x//s+y//s)%2) else (42,42,46,255))
    bg.alpha_composite(im); bg.save(dst)

def gif(src:Path, stem:str, out_dir:Path, dur=150):
    im=Image.open(src).convert('RGBA'); w,h=im.size; frames=4; cell=w//frames
    cells=[im.crop((i*cell,0,w if i==3 else (i+1)*cell,h)) for i in range(4)]
    scale=max(1,int((max(cell,h)+319)//320)); canvas=(cell//scale,h//scale)
    frs=[c.resize(canvas,Image.Resampling.NEAREST) if scale>1 else c.copy() for c in cells]
    trans=[]
    for f in frs:
        p=f.convert('P',palette=Image.Palette.ADAPTIVE,colors=255); m=Image.eval(f.getchannel('A'), lambda a:255 if a<=10 else 0); p.paste(255,m); p.info['transparency']=255; trans.append(p)
    tp=out_dir/f'{stem}_transparent.gif'; trans[0].save(tp,save_all=True,append_images=trans[1:],duration=dur,loop=0,transparency=255,disposal=2)
    chk=[]
    for f in frs:
        bg=Image.new('RGBA',canvas,(34,34,38,255)); d=ImageDraw.Draw(bg); s=8
        for y in range(0,canvas[1],s):
            for x in range(0,canvas[0],s): d.rectangle([x,y,x+s-1,y+s-1], fill=(72,72,76,255) if ((x//s+y//s)%2) else (42,42,46,255))
        bg.alpha_composite(f); chk.append(bg.convert('P',palette=Image.Palette.ADAPTIVE,colors=128))
    cp=out_dir/f'{stem}_checker.gif'; chk[0].save(cp,save_all=True,append_images=chk[1:],duration=dur,loop=0,disposal=2)
    return str(tp), str(cp), {'canvas':canvas,'scale':scale,'alignment':'preserve_cell_offsets'}

def qa(path:Path):
    im=Image.open(path).convert('RGBA'); w,h=im.size; px=im.load(); cell=w//4
    centers=[]; bottoms=[]; frames=[]
    for i in range(4):
        c=im.crop((i*cell,0,w if i==3 else (i+1)*cell,h)); b=c.getchannel('A').getbbox(); item={'frame':i+1,'bbox':b}
        if b:
            cx=(b[0]+b[2])/2; centers.append(cx); bottoms.append(b[3]); item.update({'center':[round(cx,2),round((b[1]+b[3])/2,2)],'bottom':b[3],'size':[b[2]-b[0],b[3]-b[1]]})
        frames.append(item)
    return {'size':[w,h],'corner_alpha':[px[0,0][3],px[w-1,0][3],px[0,h-1][3],px[w-1,h-1][3]],'frames':frames,'bbox_center_x_range':round(max(centers)-min(centers),2) if centers else None,'bbox_bottom_range':max(bottoms)-min(bottoms) if bottoms else None}

results=[]
for action, act_prompt in ACTIONS.items():
    out_dir=BASE_OUT/action; out_dir.mkdir(parents=True, exist_ok=True)
    payload={'reference_image':ref_data,'prompt':COMMON+'\n\n'+act_prompt,'preset':'pixel','aspect_ratio':'square','background_mode':'chroma_green','target_direction':'SE','reference_direction':'SE','direction_mode':'single','animation_mode':action,'frame_count':4,'walk_frames':4,'chroma_mode':'global','asset_type':'character','no_baked_vfx':True}
    started=time.time(); res=post(payload); item={'action':action,'elapsed':round(time.time()-started,2),'response':res,'prompt':payload['prompt']}
    if res.get('success') and res.get('path'):
        stem=f'{action}_se_v2_{int(time.time())}'; dst=out_dir/f'{stem}.png'; shutil.copy2(res['path'],dst)
        chk=out_dir/f'{stem}_checker.png'; checker(dst,chk)
        tg,cg,gm=gif(dst,stem,out_dir,dur=150 if action!='attack4' else 135)
        item.update({'success':True,'local_path':str(dst),'checker_path':str(chk),'transparent_gif':tg,'checker_gif':cg,'gif_meta':gm,'qa':qa(dst)})
    else:
        item['success']=False
    (out_dir/f'{action}_result.json').write_text(json.dumps(item,ensure_ascii=False,indent=2))
    results.append(item)
print(json.dumps(results,ensure_ascii=False,indent=2))
