#!/usr/bin/env python3
from __future__ import annotations
import base64, io, json, shutil, time, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw

API='http://127.0.0.1:4184/api/generate-reference'
REF=Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/goblin_ref_single/bottom_right_goblin_sprite_transparent.png')
OUT=Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/goblin_bottom_right_walk4_true_lr')
OUT.mkdir(parents=True, exist_ok=True)

ref_img=Image.open(REF).convert('RGBA')
buf=io.BytesIO(); ref_img.save(buf, format='PNG')
ref_data='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode('ascii')

prompt='''Generate a 4-frame RPG walk animation from the supplied transparent goblin sprite.
This is NOT a full contact/passing cycle. It is exactly: STILL, LEFT FOOT, STILL, RIGHT FOOT.

REFERENCE LOCK — preserve the supplied bottom-right sprite identity:
- same small hunched green goblin junk collector, long nose, pointed ear
- same huge sack/backpack, same hooked staff/crook, same dirty olive/brown palette
- same screen-left/down-left 3/4 facing angle, same sprite scale and refined 16/32-bit pixel-art density
- do not redesign, do not make front-facing, do not change the sack/staff/hat.

MANDATORY FRAME PLAN, left to right, exactly four cells:
1. NEUTRAL STILL: copy the reference standing pose as the base planted stance. Both feet planted, no step.
2. LEFT STEP: same body/root/facing, only one visible left-side foot/leg moves forward/down for a small walking step. Staff and sack counter-sway slightly.
3. NEUTRAL STILL AGAIN: return to the same planted stance as frame 1. Frame 3 must look nearly identical to frame 1 except tiny breathing/sack settling. No new step, no drift.
4. RIGHT STEP: same body/root/facing, the opposite/right-side foot/leg moves forward/down. It must clearly be the opposite step from frame 2.

HARD FAIL CONDITIONS:
- frame 1 is not still, or frame 3 is not still
- frame 2 and frame 4 use the same foot/contact shape
- character slides sideways inside the cell, bobs like a jump, turns front-facing, or changes equipment
- legs/feet hidden by the sack/body so left/right steps cannot be read
- staff or sack changes identity, appears/disappears, or switches side

Layout/output:
- one horizontal row, exactly 4 evenly spaced cells, wide gutters
- flat exact #00FF00 chroma green background edge-to-edge before postprocess
- no scenery, no floor, no UI, no text, no numbers, no watermark, no VFX or motion trails
- all pixels fully inside each cell.'''

payload={
  'reference_image': ref_data,
  'prompt': prompt,
  'preset': 'pixel',
  'aspect_ratio': 'square',
  'background_mode': 'chroma_green',
  'target_direction': 'SW',
  'reference_direction': 'SW',
  'direction_mode': 'single',
  'animation_mode': 'walk4',
  'frame_count': 4,
  'walk_frames': 4,
  'chroma_mode': 'global',
  'asset_type': 'character',
  'no_baked_vfx': True,
}

def post(payload):
    req=urllib.request.Request(API, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=420) as r:
        return json.loads(r.read().decode('utf-8'))

def checker_bg(size, s):
    bg=Image.new('RGBA', size, (34,34,38,255)); d=ImageDraw.Draw(bg)
    for y in range(0,size[1],s):
        for x in range(0,size[0],s):
            d.rectangle([x,y,x+s-1,y+s-1], fill=(72,72,76,255) if ((x//s+y//s)%2) else (42,42,46,255))
    return bg

def align_sheet(src:Path, dst:Path):
    im=Image.open(src).convert('RGBA')
    w,h=im.size; frames=4; cell=w//frames
    crops=[]; bboxes=[]
    for i in range(frames):
        crop=im.crop((i*cell,0,(i+1)*cell if i<3 else w,h))
        crops.append(crop); bboxes.append(crop.getchannel('A').getbbox())
    valid=[b for b in bboxes if b]
    if not valid:
        im.save(dst); return []
    ref=valid[0]; ref_cx=(ref[0]+ref[2])/2; ref_bottom=ref[3]
    out=Image.new('RGBA',(cell*frames,h),(0,0,0,0)); shifts=[]
    for i,(crop,bbox) in enumerate(zip(crops,bboxes)):
        if not bbox: continue
        cx=(bbox[0]+bbox[2])/2; bottom=bbox[3]
        dx=round(ref_cx-cx); dy=round(ref_bottom-bottom)
        layer=Image.new('RGBA',(cell,h),(0,0,0,0)); layer.alpha_composite(crop,(dx,dy))
        out.alpha_composite(layer,(i*cell,0)); shifts.append({'frame':i+1,'dx':dx,'dy':dy,'bbox_before':bbox})
    out.save(dst); return shifts

def make_checker(src:Path, dst:Path):
    img=Image.open(src).convert('RGBA'); bg=checker_bg(img.size,24); bg.alpha_composite(img); bg.save(dst)

def make_gifs(src:Path, stem:str):
    img=Image.open(src).convert('RGBA')
    w,h=img.size; cell=w//4; scale=max(1,int((max(cell,h)+319)//320)); canvas=(cell//scale,h//scale)
    frs=[]
    for i in range(4):
        c=img.crop((i*cell,0,(i+1)*cell,h))
        frs.append(c.resize(canvas,Image.Resampling.NEAREST) if scale>1 else c)
    trans=[]
    for f in frs:
        p=f.convert('P',palette=Image.Palette.ADAPTIVE,colors=255)
        mask=Image.eval(f.getchannel('A'), lambda a: 255 if a<=10 else 0)
        p.paste(255,mask); p.info['transparency']=255; trans.append(p)
    trans_path=OUT/f'{stem}_transparent.gif'
    trans[0].save(trans_path,save_all=True,append_images=trans[1:],duration=180,loop=0,transparency=255,disposal=2)
    chks=[]
    for f in frs:
        bg=checker_bg(canvas,8); bg.alpha_composite(f); chks.append(bg.convert('P',palette=Image.Palette.ADAPTIVE,colors=128))
    chk_path=OUT/f'{stem}_checker.gif'
    chks[0].save(chk_path,save_all=True,append_images=chks[1:],duration=180,loop=0,disposal=2)
    return str(trans_path), str(chk_path), {'gif_frames':4,'canvas':canvas,'scale':scale}

def qa(path:Path):
    im=Image.open(path).convert('RGBA'); w,h=im.size; cell=w//4; px=im.load()
    corners=[px[0,0][3],px[w-1,0][3],px[0,h-1][3],px[w-1,h-1][3]]
    stats=[]; centers=[]; bottoms=[]
    for i in range(4):
        crop=im.crop((i*cell,0,(i+1)*cell,h)); a=crop.getchannel('A'); bbox=a.getbbox(); hist=a.histogram(); opaque=sum(hist[21:])
        item={'frame':i+1,'bbox':bbox,'opaque':opaque}
        if bbox:
            x0,y0,x1,y1=bbox; centers.append((x0+x1)/2); bottoms.append(y1); item.update({'center':[round((x0+x1)/2,2),round((y0+y1)/2,2)],'bottom':y1,'size':[x1-x0,y1-y0]})
        stats.append(item)
    return {'size':[w,h],'corner_alpha':corners,'alpha_extrema':im.getchannel('A').getextrema(),'alpha_pass':corners==[0,0,0,0] and im.getchannel('A').getextrema()[0]==0,'frames':stats,'anchor_drift':{'bbox_center_x_range':round(max(centers)-min(centers),2) if centers else None,'bbox_bottom_range':max(bottoms)-min(bottoms) if bottoms else None}}

started=time.time(); res=post(payload)
out={'started':started,'elapsed':round(time.time()-started,2),'response':res,'prompt':prompt,'reference':str(REF)}
if not res.get('success') or not res.get('path'):
    out['success']=False; (OUT/'true_lr_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)); raise SystemExit(json.dumps(out,ensure_ascii=False,indent=2))
stem=f'bottom_right_goblin_walk4_true_lr_{int(time.time())}'
raw=OUT/f'{stem}_raw.png'; shutil.copy2(res['path'],raw)
aligned=OUT/f'{stem}.png'; shifts=align_sheet(raw,aligned)
checker=OUT/f'{stem}_checker.png'; make_checker(aligned,checker)
trans_gif,checker_gif,gif_meta=make_gifs(aligned,stem)
out.update({'success':True,'raw_path':str(raw),'local_path':str(aligned),'checker_path':str(checker),'transparent_gif':trans_gif,'checker_gif':checker_gif,'gif_meta':gif_meta,'shifts':shifts,'qa':qa(aligned)})
(OUT/'true_lr_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({'local_path':str(aligned),'checker_path':str(checker),'transparent_gif':trans_gif,'checker_gif':checker_gif,'gif_meta':gif_meta,'shifts':shifts,'qa':out['qa'],'elapsed':out['elapsed']},ensure_ascii=False,indent=2))
