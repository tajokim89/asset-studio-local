#!/usr/bin/env python3
from __future__ import annotations
import json, time, urllib.request, shutil
from pathlib import Path
from PIL import Image, ImageDraw

API='http://127.0.0.1:4184/api/generate'
OUT=Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/whitelist_walk4')
OUT.mkdir(parents=True, exist_ok=True)

prompt='''small hooded dungeon cleanup worker with brass goggles and short broom/tool, same character in every frame

Create exactly one horizontal 4-frame sprite sheet for ACTION walk4, target direction S/front-facing.

WHITELIST PASS CONTRACT FOR WALK:
PASS only if the sheet reads as a front-facing in-place walk cycle.
Required frame beats, left to right:
1 left foot contact: left foot clearly forward/down, right foot back, opposite arm/tool phase
2 passing pose: feet close under body, weight passing, same front-facing torso
3 right foot contact: right foot clearly forward/down, left foot back, opposite arm/tool phase reversed from frame 1
4 passing pose: feet close under body, weight passing, connects back to frame 1

Hard acceptance criteria:
- Every frame remains S/front-facing, looking toward camera/front; no side profile, diagonal turn, or back view.
- Feet must visibly alternate left/right contact. Frame 1 and frame 3 must be different mirrored/opposite foot contact poses.
- Arms/tool counter-swing consistently and the broom/tool stays attached to the same hand/side in every frame.
- Character keeps a fixed pelvis/root anchor: same head/torso center, same foot baseline, same scale, and same pivot in all four cells.
- Only legs/arms/tool swing around the fixed body anchor; the whole character must not slide left/right inside the cell.
- No moonwalk, no skating, no hopping, no dancing/flailing, no horse-like or quadruped gait, no duplicate idle-only frames.
- Same identity, costume, goggles, hood, broom/tool, palette, outline thickness, proportions, pivot, and scale in all frames.
- If the dominant readable action is not walking, this is FAIL.

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
  'animation_mode':'walk4',
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

def make_checker(src:Path, dst:Path):
    img=Image.open(src).convert('RGBA')
    bg=Image.new('RGBA', img.size, (34,34,38,255))
    d=ImageDraw.Draw(bg); s=24
    for y in range(0,img.height,s):
        for x in range(0,img.width,s):
            col=(72,72,76,255) if ((x//s+y//s)%2) else (42,42,46,255)
            d.rectangle([x,y,x+s-1,y+s-1], fill=col)
    bg.alpha_composite(img)
    bg.save(dst)

def make_gifs(src:Path, stem:str):
    img=Image.open(src).convert('RGBA')
    w,h=img.size; frames=4; cell=w//frames
    # Preserve each sprite's original cell-relative offset. Do not crop by bbox and
    # re-center, because bbox-centering hides root drift and can create a horse-like
    # bounce in the preview. The GIF preview is a scaled view of the fixed cells.
    cells=[]
    for i in range(frames):
        crop=img.crop((i*cell,0,w if i==frames-1 else (i+1)*cell,h))
        cells.append(crop)
    maxdim=max(cell,h)
    scale=max(1, int((maxdim + 319)//320))
    canvas=(cell//scale, h//scale)
    frs=[]
    for c in cells:
        f=c.resize(canvas, Image.Resampling.NEAREST) if scale>1 else c.copy()
        frs.append(f)
    trans=[]
    for f in frs:
        p=f.convert('P', palette=Image.Palette.ADAPTIVE, colors=255)
        mask=Image.eval(f.getchannel('A'), lambda a: 255 if a<=10 else 0)
        p.paste(255, mask); p.info['transparency']=255
        trans.append(p)
    trans_path=OUT/f'{stem}_transparent.gif'
    trans[0].save(trans_path, save_all=True, append_images=trans[1:], duration=150, loop=0, transparency=255, disposal=2)
    chk=[]
    for f in frs:
        bg=Image.new('RGBA', canvas, (34,34,38,255)); d=ImageDraw.Draw(bg); s=8
        for y in range(0,canvas[1],s):
            for x in range(0,canvas[0],s):
                col=(72,72,76,255) if ((x//s+y//s)%2) else (42,42,46,255)
                d.rectangle([x,y,x+s-1,y+s-1], fill=col)
        bg.alpha_composite(f)
        chk.append(bg.convert('P', palette=Image.Palette.ADAPTIVE, colors=128))
    chk_path=OUT/f'{stem}_checker.gif'
    chk[0].save(chk_path, save_all=True, append_images=chk[1:], duration=150, loop=0, disposal=2)
    return str(trans_path), str(chk_path), {'gif_frames':len(frs),'canvas':canvas,'alignment':'preserve_cell_offsets','scale':scale}

def qa(path:Path):
    im=Image.open(path).convert('RGBA')
    w,h=im.size; px=im.load(); cell=w//4
    corners=[px[0,0][3],px[w-1,0][3],px[0,h-1][3],px[w-1,h-1][3]]
    stats=[]
    centers=[]; bottoms=[]; heights=[]; widths=[]
    for i in range(4):
        crop=im.crop((i*cell,0,w if i==3 else (i+1)*cell,h))
        alpha=crop.getchannel('A')
        bbox=alpha.getbbox()
        hist=alpha.histogram()
        opaque=sum(hist[21:])
        item={'frame':i+1,'bbox':bbox,'opaque':opaque}
        if bbox:
            x0,y0,x1,y1=bbox
            cx=round((x0+x1)/2,2); cy=round((y0+y1)/2,2)
            item.update({'center':[cx,cy],'bottom':y1,'size':[x1-x0,y1-y0]})
            centers.append(cx); bottoms.append(y1); widths.append(x1-x0); heights.append(y1-y0)
        stats.append(item)
    drift={
        'bbox_center_x_range': round(max(centers)-min(centers),2) if centers else None,
        'bbox_bottom_range': max(bottoms)-min(bottoms) if bottoms else None,
        'bbox_width_range': max(widths)-min(widths) if widths else None,
        'bbox_height_range': max(heights)-min(heights) if heights else None,
        'anchor_note': 'bbox metrics are a coarse proxy; final PASS still requires visual pelvis/root QA',
    }
    return {'size':[w,h],'corner_alpha':corners,'alpha_pass':corners==[0,0,0,0],'frames':stats,'anchor_drift':drift}

started=time.time()
res=post(payload)
out={'started':started,'elapsed':round(time.time()-started,2),'response':res,'prompt':prompt}
if not res.get('success') or not res.get('path'):
    out['success']=False
    (OUT/'walk4_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    raise SystemExit(json.dumps(out,ensure_ascii=False,indent=2))

src=Path(res['path'])
stem=f'walk4_whitelist_{int(time.time())}'
dst=OUT/f'{stem}.png'
shutil.copy2(src,dst)
chk=OUT/f'{stem}_checker.png'
make_checker(dst,chk)
trans_gif, checker_gif, gif_meta=make_gifs(dst,stem)
out.update({'success':True,'local_path':str(dst),'checker_path':str(chk),'transparent_gif':trans_gif,'checker_gif':checker_gif,'gif_meta':gif_meta,'qa':qa(dst)})
(OUT/'walk4_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({'local_path':str(dst),'checker_path':str(chk),'transparent_gif':trans_gif,'checker_gif':checker_gif,'qa':out['qa'],'elapsed':out['elapsed']},ensure_ascii=False,indent=2))
