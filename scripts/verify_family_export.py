#!/usr/bin/env python3
"""Independently verify Asset Studio family ZIP downloads.

This intentionally does not import browser exporter code. It validates ZIP safety,
manifest/schema, payload inventory hashes, PNG decoding, and family coordinate
contracts. Usage: python scripts/verify_family_export.py download.zip
"""
from __future__ import annotations
import hashlib, io, json, sys, zipfile, zlib
from pathlib import Path, PurePosixPath
from PIL import Image

SCHEMAS={
 "actor":"asset-studio.actor-package/v1",
 "effect":"asset-studio.effect-sequence/v1",
 "tile":"asset-studio.tile-package/v1",
 "ui":"asset-studio.ui-state-package/v1",
 "object":"asset-studio.object-package/v1",
}


def _point(value,name):
 if not isinstance(value,dict) or set(value)!={"x","y"}: raise ValueError(f"invalid {name}")
 if any(isinstance(value[k],bool) or not isinstance(value[k],(int,float)) or not 0<=value[k]<=1 for k in ("x","y")): raise ValueError(f"invalid {name}")


def verify_family_export(path_or_bytes):
 raw=Path(path_or_bytes).read_bytes() if isinstance(path_or_bytes,(str,Path)) else bytes(path_or_bytes)
 if not raw or len(raw)>256*1024*1024: raise ValueError("archive byte budget")
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  infos=z.infolist(); names=[i.filename for i in infos]
  if len(names)!=len(set(names)) or len(names)>4096 or "manifest.json" not in names: raise ValueError("unsafe/duplicate/missing ZIP entries")
  if z.testzip() is not None: raise ValueError("ZIP CRC failure")
  for info in infos:
   p=PurePosixPath(info.filename)
   if p.is_absolute() or ".." in p.parts or "\\" in info.filename or info.file_size>128*1024*1024: raise ValueError("unsafe ZIP path/budget")
  manifest=json.loads(z.read("manifest.json"))
  family=manifest.get("family"); schema=manifest.get("schema_version")
  if family not in SCHEMAS or schema!=SCHEMAS[family]: raise ValueError("manifest family/schema mismatch")
  inventory=manifest.get("inventory")
  if not isinstance(inventory,list): raise ValueError("inventory missing")
  expected=set(names)-{"manifest.json"}; seen=set()
  for item in inventory:
   if not isinstance(item,dict) or not {"path","bytes","crc32","sha256"}<=set(item): raise ValueError("invalid inventory item")
   name=item["path"]
   if name in seen or name not in expected: raise ValueError("inventory path mismatch")
   data=z.read(name); seen.add(name)
   if item["bytes"]!=len(data) or item["crc32"]!=f"{zlib.crc32(data)&0xffffffff:08x}" or item["sha256"]!=hashlib.sha256(data).hexdigest(): raise ValueError("inventory digest mismatch")
  if seen!=expected: raise ValueError("inventory coverage mismatch")
  png={}
  for name in expected:
   if name.lower().endswith(".png"):
    with Image.open(io.BytesIO(z.read(name))) as image:
     if image.format!="PNG": raise ValueError("non-PNG payload")
     image.load(); png[name]=image.convert("RGBA").size
  if family=="actor":
   size=manifest["sourceSize"]; _point(manifest["anchors"]["pivot"],"actor pivot")
   for frame in manifest["frames"]:
    if png.get(frame["path"])!=(size["width"],size["height"]): raise ValueError("actor frame geometry")
    rect=frame["atlas"]
    if any(not isinstance(rect[k],int) or rect[k]<0 for k in ("x","y")): raise ValueError("actor atlas coordinates")
   if not all(isinstance(a.get("fps"),int) and a["fps"]>0 for a in manifest["actions"]): raise ValueError("actor FPS")
  elif family=="effect":
   size=manifest["source_size"]
   for frame in manifest["frames"]:
    rect=frame["trim_rect"]; _point(frame["pivot"],"effect pivot")
    if any(not isinstance(rect[k],int) or rect[k]<0 for k in ("x","y","width","height")): raise ValueError("effect trim rect")
    if rect["x"]+rect["width"]>size["width"] or rect["y"]+rect["height"]>size["height"] or png.get(frame["file"])!=(rect["width"],rect["height"]): raise ValueError("effect reconstruction geometry")
  elif family=="tile":
   atlas=manifest["atlas"]
   if png.get(atlas["path"])!=(atlas["width"],atlas["height"]): raise ValueError("tile atlas geometry")
   for tile in manifest["tiles"]:
    if any(not isinstance(tile[k],int) or tile[k]<0 for k in ("x","y","width","height")): raise ValueError("tile coordinates")
    if tile["x"]+tile["width"]>atlas["width"] or tile["y"]+tile["height"]>atlas["height"]: raise ValueError("tile outside atlas")
  elif family=="ui":
   size=manifest["sourceSize"]
   for key in ("sliceMargins","safeArea"):
    value=manifest[key]
    if set(value)!={"top","right","bottom","left"} or any(not isinstance(v,int) or v<0 for v in value.values()): raise ValueError("UI coordinates")
   for state in manifest["states"]:
    if png.get(state["file"])!=(size["width"],size["height"]): raise ValueError("UI state geometry")
  else:
   size=manifest["sourceSize"]
   for state in manifest["states"]:
    if png.get(state["path"])!=(size["width"],size["height"]): raise ValueError("object state geometry")
    for key in ("pivot","ground_point","y_sort_point"): _point(state[key],"object "+key)
  return {"schema_version":"asset-studio.family-import-verification/v1","family":family,"manifest_schema":schema,"files_verified":len(expected),"pngs_verified":len(png),"status":"PASS"}


if __name__=="__main__":
 try: print(json.dumps(verify_family_export(sys.argv[1]),ensure_ascii=False,sort_keys=True))
 except Exception as exc: print(json.dumps({"status":"FAIL","error":str(exc)},ensure_ascii=False)); raise SystemExit(1)
