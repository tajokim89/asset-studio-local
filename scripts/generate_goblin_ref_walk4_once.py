#!/usr/bin/env python3
from __future__ import annotations
import base64, io, json, shutil, time, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops

API='http://127.0.0.1:4184/api/generate-reference'
REF=Path('/Users/tajokim/.hermes/image_cache/img_fac8951d5f60.jpeg')
OUT=Path('/Users/tajokim/.hermes/image_cache/asset-studio-local/goblin_ref_walk4')
OUT.mkdir(parents=True, exist_ok=True)

ref_img=Image.open(REF).convert('RGBA')
buf=io.BytesIO(); ref_img.save(buf, format='PNG')
ref_data='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode('ascii')

prompt='''Use the supplied image as the exact character identity/style reference.
Create a game-ready 4-frame walk sprite sheet for this same goblin junk collector / scavenger merchant.

Character identity to preserve from reference:
- small hunched olive-green goblin, long pointed nose, pointed ears, narrow mischievous eyes
- dirty brown leather cap and vest, dark earthy dungeon palette
- huge overstuffed sack/backpack behind him, packed with bottles, sticks, scrap metal and junk
- hooked walking staff/crook held in one hand
- grubby scavenger / junk collector silhouette, not cute, not SD, not bright fantasy
- refined 16-bit / 32-bit pixel-art shading, crisp readable outline, not chunky 8-bit

Target sprite:
- exactly one horizontal 4-frame sprite sheet, single row, target direction S/front-facing for RPG use
- frame beats left to right: neutral planted stance; SCREEN-RIGHT boot swing-cross; same neutral planted stance; SCREEN-LEFT boot swing-cross
- use SCREEN COORDINATES ONLY for the feet—do not reinterpret anatomical left/right. COLUMN 2: only the screen-right boot is lifted/advanced, its center lies to the right of the pelvis centerline, its knee travels inward across the planted leg; the screen-left boot stays planted behind. COLUMN 4: exact opposite lower-body phase—only the screen-left boot is lifted/advanced, its center lies left of the pelvis centerline, its knee travels inward across the planted leg; the screen-right boot stays planted behind
- below the belt, columns 2 and 4 must read as opposite/mirrored leg phases. If the enlarged/front boot appears on the same screen side in columns 2 and 4, reject the image
- crossing means the inward-moving swing shin/boot passes in depth directly beside and partly overlaps the planted leg under the pelvis before emerging in front; no outward kick, no wide split stance, no feet that remain parallel
- real in-place crossover walk cycle: opposite swing feet and stance/support legs in frames 2 and 4; natural depth pass only, no anatomical side swap or X-locked legs; the sack and hooked staff counter-sway coherently
- divide the canvas into four equal cells and place the pelvis/root center at exactly 50% of every cell width and the identical y-coordinate; no progressive left/right drift
- keep same goblin identity, sack size, staff side, palette, pixel scale, pivot/root, foot baseline, and outline thickness in every frame
- feet/contact points must remain visible; do not hide legs under a solid robe or sack
- flat exact #00FF00 chroma green background edge-to-edge before postprocess; no scenery, no floor, no UI, no text, no numbers, no watermark, no VFX, no particles
- every frame fully inside its own cell with wide empty gutters and at least 15 percent margin.'''

payload={
  'reference_image': ref_data,
  'prompt': prompt,
  'preset': 'pixel',
  'aspect_ratio': 'square',
  'background_mode': 'chroma_green',
  'target_direction': 'S',
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

def make_checker(src:Path, dst:Path):
    img=Image.open(src).convert('RGBA')
    bg=Image.new('RGBA', img.size, (34,34,38,255))
    d=ImageDraw.Draw(bg); s=24
    for y in range(0,img.height,s):
        for x in range(0,img.width,s):
            col=(72,72,76,255) if ((x//s+y//s)%2) else (42,42,46,255)
            d.rectangle([x,y,x+s-1,y+s-1], fill=col)
    bg.alpha_composite(img); bg.save(dst)

def make_gifs(src:Path, stem:str):
    img=Image.open(src).convert('RGBA')
    w,h=img.size; frames=4; cell=w//frames
    cells=[]
    for i in range(frames):
        cells.append(img.crop((i*cell,0,w if i==frames-1 else (i+1)*cell,h)))
    maxdim=max(cell,h); scale=max(1, int((maxdim+319)//320))
    canvas=(cell//scale, h//scale)
    frs=[]
    for c in cells:
        frs.append(c.resize(canvas, Image.Resampling.NEAREST) if scale>1 else c.copy())
    trans=[]
    for f in frs:
        p=f.convert('P', palette=Image.Palette.ADAPTIVE, colors=255)
        mask=Image.eval(f.getchannel('A'), lambda a: 255 if a<=10 else 0)
        p.paste(255, mask); p.info['transparency']=255
        trans.append(p)
    trans_path=OUT/f'{stem}_transparent.gif'
    trans[0].save(trans_path, save_all=True, append_images=trans[1:], duration=160, loop=0, transparency=255, disposal=2)
    chk=[]
    for f in frs:
        bg=Image.new('RGBA', canvas, (34,34,38,255)); d=ImageDraw.Draw(bg); s=8
        for y in range(0,canvas[1],s):
            for x in range(0,canvas[0],s):
                col=(72,72,76,255) if ((x//s+y//s)%2) else (42,42,46,255)
                d.rectangle([x,y,x+s-1,y+s-1], fill=col)
        bg.alpha_composite(f); chk.append(bg.convert('P', palette=Image.Palette.ADAPTIVE, colors=128))
    chk_path=OUT/f'{stem}_checker.gif'
    chk[0].save(chk_path, save_all=True, append_images=chk[1:], duration=160, loop=0, disposal=2)
    return str(trans_path), str(chk_path), {'gif_frames':len(frs),'canvas':canvas,'scale':scale,'alignment':'preserve_cell_offsets'}

def qa(path:Path):
    im=Image.open(path).convert('RGBA')
    w,h=im.size; px=im.load(); cell=w//4
    corners=[px[0,0][3],px[w-1,0][3],px[0,h-1][3],px[w-1,h-1][3]]
    stats=[]; centers=[]; bottoms=[]; widths=[]; heights=[]; opaques=[]
    for i in range(4):
        crop=im.crop((i*cell,0,w if i==3 else (i+1)*cell,h))
        a=crop.getchannel('A'); bbox=a.getbbox(); hist=a.histogram(); opaque=sum(hist[21:]); opaques.append(opaque)
        item={'frame':i+1,'bbox':bbox,'opaque':opaque}
        if bbox:
            x0,y0,x1,y1=bbox; centers.append((x0+x1)/2); bottoms.append(y1); widths.append(x1-x0); heights.append(y1-y0)
            item.update({'center':[round((x0+x1)/2,2),round((y0+y1)/2,2)],'bottom':y1,'size':[x1-x0,y1-y0]})
        stats.append(item)
    return {
      'size':[w,h], 'corner_alpha':corners, 'alpha_pass':corners==[0,0,0,0],
      'frames':stats,
      'anchor_drift':{
        'bbox_center_x_range':round(max(centers)-min(centers),2) if centers else None,
        'bbox_bottom_range':max(bottoms)-min(bottoms) if bottoms else None,
        'bbox_width_range':max(widths)-min(widths) if widths else None,
        'bbox_height_range':max(heights)-min(heights) if heights else None,
        'opaque_range':max(opaques)-min(opaques) if opaques else None,
        'note':'mechanical proxy only; visual motion gate still required'
      }
    }

started=time.time(); res=post(payload)
out={'started':started,'elapsed':round(time.time()-started,2),'response':res,'prompt':prompt,'reference':str(REF)}
if not res.get('success') or not res.get('path'):
    out['success']=False
    (OUT/'goblin_walk4_result.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(json.dumps(out, ensure_ascii=False, indent=2))
stem=f'goblin_ref_walk4_{int(time.time())}'
dst=OUT/f'{stem}.png'; shutil.copy2(res['path'], dst)
chk=OUT/f'{stem}_checker.png'; make_checker(dst, chk)
trans_gif, checker_gif, gif_meta=make_gifs(dst, stem)
out.update({'success':True,'local_path':str(dst),'checker_path':str(chk),'transparent_gif':trans_gif,'checker_gif':checker_gif,'gif_meta':gif_meta,'qa':qa(dst)})
(OUT/'goblin_walk4_result.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(json.dumps({'local_path':str(dst),'checker_path':str(chk),'transparent_gif':trans_gif,'checker_gif':checker_gif,'gif_meta':gif_meta,'qa':out['qa'],'elapsed':out['elapsed']}, ensure_ascii=False, indent=2))
