"""Executable C4 acceptance tests.

Production JavaScript is extracted verbatim and run in Node; the resulting package
is then audited by Python implementations which share no ZIP/PNG/XML code with it.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import textwrap
import xml.etree.ElementTree as ET
import zipfile
import zlib

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "src/main.js"
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def _range(source: str, start: str, end: str) -> str:
    """Copy an audited, declaration-anchored production source range."""
    a, b = source.index(start), source.index(end, source.index(start))
    return source[a:b]


@pytest.fixture(scope="session")
def node_driver(tmp_path_factory):
    source = MAIN.read_text(encoding="utf-8")
    # Exact shared primitives, followed by the complete C4 implementation.
    extracted = (_range(source, "function effectConcatBytes", "const EFFECT_EXPORT_LIMITS")
                 + _range(source, "let crc32Table = null;", "function buildStoredZip")
                 + _range(source, "const TILE_EXPORT_LIMITS", "const TILE_PREVIEW_BUDGETS"))
    driver = tmp_path_factory.mktemp("c4-node") / "driver.js"
    driver.write_text(extracted + textwrap.dedent(r"""
      if (typeof Blob === 'undefined') globalThis.Blob = class Blob { constructor(parts){this.parts=parts;} };
      const b64 = b => Buffer.from(b).toString('base64');
      const unb64 = s => new Uint8Array(Buffer.from(s,'base64'));
      function fixture(shape='square') {
        const width=19,height=19,data=new Uint8ClampedArray(width*height*4);
        const colors=[[241,17,31,255],[19,223,43,129],[47,59,239,64],[251,199,7,254]];
        data.set([9,8,7,1],0); // outside/gutter alpha=1 sentinel
        for(let r=0;r<2;r++)for(let c=0;c<2;c++)for(let y=0;y<8;y++)for(let x=0;x<8;x++)
          data.set(colors[r*2+c],(((1+r*9+y)*width)+(1+c*9+x))*4);
        const contract={schema_version:'asset-studio.tile-contract/v2',shape,tile_size:{width:8,height:8},rows:2,columns:2,margin:1,spacing:1,
          topology:'wang-8',inner_corners:true,outer_corners:true,
          transitions:[{from:'grass',to:'water',tiles:[1]}],terrain_types:[{id:'grass',tile_indices:[0,2]},{id:'water',tile_indices:[1,3]}],
          variants:[{name:'damaged',indices:[2,3]}],metadata:{collision:{tiles:[0,3]},occlusion:{tile_indices:[1]},navigation:{costs:[1,2,3,4]},custom:{author:'C4',alpha:true}}};
        return {image:{width,height,data},contract,colors};
      }
      async function main(q){
        if(q.op==='build') { const f=fixture(q.shape),a=buildTileExportPackage(f.image,f.contract,'terrain & test'),b=buildTileExportPackage(f.image,f.contract,'terrain & test');
          return {zip:b64(a.zipBytes),same:b64(a.zipBytes)===b64(b.zipBytes),manifest:a.manifest,colors:f.colors}; }
        if(q.op==='parse') { const p=parseTileExportPackage(unb64(q.zip)); return {tilesCompared:p.tilesCompared,manifest:p.manifest,atlas:{width:p.atlas.width,height:p.atlas.height,alpha0:p.atlas.data[3]}}; }
        if(q.op==='png-limit') {
          if(q.kind==='above') { const png=encodeEffectFramePng(3072,3072,new Uint8ClampedArray(3072*3072*4));let defaultError='';try{decodeEffectFramePng(png)}catch(e){defaultError=e.message}const tile=decodeEffectFramePng(png,{maxPixels:TILE_EXPORT_LIMITS.maxSourcePixels});return {defaultError,width:tile.width,height:tile.height}; }
          const png=encodeEffectFramePng(1,1,new Uint8ClampedArray(4));png.set([0,0,0x10,1,0,0,0x10,1],16);try{decodeEffectFramePng(png,{maxPixels:TILE_EXPORT_LIMITS.maxSourcePixels});return {accepted:true}}catch(e){return {error:e.message}}
        }
        if(q.op==='budget') { let calls=0,old=encodeEffectFramePng; encodeEffectFramePng=(...x)=>{calls++;return old(...x)}; try { const f=fixture();
          if(q.kind==='cells'){f.contract.rows=65;f.contract.columns=65;f.image={width:100000,height:100000};}
          if(q.kind==='source')f.image={width:4097,height:4097};
          if(q.kind==='work'){f.contract.tile_size={width:2000,height:2000};f.contract.rows=2;f.contract.columns=2;f.contract.margin=0;f.contract.spacing=0;f.image={width:4000,height:4000};}
          if(q.kind==='archive'){const d=new Uint8Array(TILE_EXPORT_LIMITS.maxPayloadBytes);tileZipBytes([{name:'a',bytes:d},{name:'b',bytes:new Uint8Array(1)}]);return;}
          buildTileExportPackage(f.image,f.contract); return {ok:true,calls};
        } catch(e){return {error:e.message,calls};}}
      }
      let input='';process.stdin.on('data',x=>input+=x).on('end',async()=>{try{console.log(JSON.stringify(await main(JSON.parse(input))))}catch(e){console.log(JSON.stringify({error:e.message}))}});
    """), encoding="utf-8")

    def run(payload):
        cp = subprocess.run(["node", str(driver)], input=json.dumps(payload), text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return json.loads(cp.stdout)
    return run


@pytest.fixture(scope="session")
def built(node_driver):
    out = node_driver({"op":"build"})
    assert out["same"], "production builds must be byte deterministic"
    return out, base64.b64decode(out["zip"])


def _files(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert all(i.compress_type == zipfile.ZIP_STORED for i in z.infolist())
        return {i.filename: z.read(i) for i in z.infolist()}


def _repack(files):
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_STORED) as z:
        for name,data in files.items():
            zi=zipfile.ZipInfo(name,(1980,1,1,0,0,0)); zi.compress_type=zipfile.ZIP_STORED
            z.writestr(zi,data)
    return out.getvalue()


def _png(data):
    im=Image.open(io.BytesIO(data)); im.load()
    return im.convert("RGBA")


def _refresh_manifest(files, changed):
    m=json.loads(files["manifest.json"])
    for item in m["inventory"]:
        if item["path"] in changed:
            d=files[item["path"]]; item.update(bytes=len(d),crc32=f"{zlib.crc32(d)&0xffffffff:08x}",sha256=hashlib.sha256(d).hexdigest())
    files["manifest.json"]=(json.dumps(m,sort_keys=True,indent=2)+"\n").encode()


def test_production_build_parse_and_independent_roundtrip(built,node_driver):
    out,raw=built; parsed=node_driver({"op":"parse","zip":out["zip"]})
    assert "error" not in parsed and parsed["tilesCompared"]==4 and parsed["atlas"]["alpha0"]==1
    files=_files(raw); m=json.loads(files["manifest.json"])
    expected={"manifest.json","atlas.png","terrain-mapping.json","engine-metadata.json","tileset.tsx","map.tmx",*(f"tiles/tile-{i:04}.png" for i in range(4))}
    assert set(files)==expected
    assert m==out["manifest"] and m["contract"]["topology"]=="wang-8"
    assert m["contract"]["transitions"] and m["contract"]["variants"] and m["order"]=="row-major"
    for x in m["inventory"]:
        d=files[x["path"]]; assert x["bytes"]==len(d); assert x["crc32"]==f"{zlib.crc32(d)&0xffffffff:08x}"; assert x["sha256"]==hashlib.sha256(d).hexdigest()
    atlas=_png(files["atlas.png"]); assert atlas.size==(19,19) and atlas.getpixel((0,0))==(9,8,7,1)
    for i,t in enumerate(m["tiles"]):
        tile=_png(files[t["path"]]); assert tile.size==(8,8)
        assert set(tile.getdata())=={tuple(out["colors"][i])}
        assert list(tile.getdata())==list(atlas.crop((t["x"],t["y"],t["x"]+8,t["y"]+8)).getdata())
    terrain=json.loads(files["terrain-mapping.json"]); meta=json.loads(files["engine-metadata.json"])
    assert terrain["topology"]=="wang-8" and len(terrain["terrain_types"])==2 and terrain["mapping"]["tile_count"]==4
    assert meta["collision"]["tiles"]==[0,3] and meta["custom"]["author"]=="C4" and meta["tile_index_validation"]["valid"]
    tsx=ET.fromstring(files["tileset.tsx"])
    assert {"tilewidth":"8","tileheight":"8","tilecount":"4","columns":"2","margin":"1","spacing":"1"}.items() <= tsx.attrib.items()
    assert tsx.find("image").attrib=={"source":"atlas.png","width":"19","height":"19"}
    tmx=ET.fromstring(files["map.tmx"]); assert tmx.attrib["width"]==tmx.attrib["height"]=="2"
    assert tmx.find("tileset").attrib["source"]=="tileset.tsx" and tmx.find("layer/data").text=="1,2,3,4"


def test_non_square_explicitly_omits_xml(node_driver):
    out=node_driver({"op":"build","shape":"hex"}); files=_files(base64.b64decode(out["zip"]))
    assert "tileset.tsx" not in files and "map.tmx" not in files
    assert out["manifest"]["artifacts"]["tsx"] is None and "unsupported tile shape hex" in out["manifest"]["warnings"][0]


def _mutate(raw, kind):
    f=_files(raw)
    if kind=="path": f["../evil"]=f.pop("atlas.png")
    elif kind=="duplicate":
        # Construct two entries deliberately; dict cannot represent duplicates.
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w",zipfile.ZIP_STORED) as z:
            for n,d in f.items(): z.writestr(n,d)
            z.writestr("atlas.png",f["atlas.png"])
        return out.getvalue()
    elif kind=="schema":
        m=json.loads(f["manifest.json"]);m["family"]="effect";f["manifest.json"]=json.dumps(m).encode()
    elif kind=="inventory": f["atlas.png"]+=b"x"
    elif kind=="png_crc":
        d=bytearray(f["atlas.png"]); d[45]^=1; f["atlas.png"]=bytes(d); _refresh_manifest(f,{"atlas.png"})
    elif kind=="png_dimensions":
        m=json.loads(f["manifest.json"]);m["atlas"]["width"]=20;f["manifest.json"]=json.dumps(m).encode()
    elif kind=="geometry":
        m=json.loads(f["manifest.json"]);m["tiles"][0]["x"]=2;f["manifest.json"]=json.dumps(m).encode()
    elif kind=="terrain":
        d=json.loads(f["terrain-mapping.json"]);d["topology"]="wrong";f["terrain-mapping.json"]=json.dumps(d).encode();_refresh_manifest(f,{"terrain-mapping.json"})
    elif kind=="metadata":
        d=json.loads(f["engine-metadata.json"]);d["collision"]={"tiles":[99]};f["engine-metadata.json"]=json.dumps(d).encode();_refresh_manifest(f,{"engine-metadata.json"})
    elif kind=="xml":
        f["tileset.tsx"]=f["tileset.tsx"].replace(b'tilecount="4"',b'tilecount="3"');_refresh_manifest(f,{"tileset.tsx"})
    return _repack(f)


@pytest.mark.parametrize("kind,needle",[("path","path traversal"),("duplicate","duplicate"),("schema","schema/version/family"),("inventory","checksum"),("png_crc","PNG chunk CRC"),("png_dimensions","dimensions"),("geometry","geometry"),("terrain","terrain"),("metadata","metadata"),("xml","TSX")])
def test_parser_rejects_mutation_classes(built,node_driver,kind,needle):
    result=node_driver({"op":"parse","zip":base64.b64encode(_mutate(built[1],kind)).decode()})
    assert "error" in result and needle.lower() in result["error"].lower(), (kind,result)


def _zip_structure_mutation(raw, kind):
    data=bytearray(raw); eocd=len(data)-22
    assert struct.unpack_from('<I',data,eocd)[0]==0x06054b50
    central=struct.unpack_from('<I',data,eocd+16)[0]
    if kind=="central_crc": data[central+16]^=1
    elif kind=="central_name": data[central+46]^=1
    elif kind=="central_size": data[central+24]^=1
    elif kind=="central_offset": data[central+42]^=1
    elif kind=="central_count": struct.pack_into('<H',data,eocd+10,struct.unpack_from('<H',data,eocd+10)[0]-1)
    elif kind=="eocd_disk_count": struct.pack_into('<H',data,eocd+8,struct.unpack_from('<H',data,eocd+8)[0]-1)
    elif kind=="eocd_offset": data[eocd+16]^=1
    elif kind=="eocd_size": data[eocd+12]^=1
    elif kind=="missing_eocd": del data[eocd:]
    elif kind=="trailing": data.extend(b'x')
    return bytes(data)


@pytest.mark.parametrize("kind",["central_crc","central_name","central_size","central_offset","central_count","eocd_disk_count","eocd_offset","eocd_size","missing_eocd","trailing"])
def test_parser_rejects_central_directory_and_eocd_mutations(built,node_driver,kind):
    mutated=_zip_structure_mutation(built[1],kind)
    result=node_driver({"op":"parse","zip":base64.b64encode(mutated).decode()})
    assert "error" in result, (kind,result)


def test_tile_png_limit_extends_effect_default_without_weakening_it(node_driver):
    above=node_driver({"op":"png-limit","kind":"above"})
    assert "dimensions" in above["defaultError"] and (above["width"],above["height"])==(3072,3072)
    over=node_driver({"op":"png-limit","kind":"over"})
    assert "dimensions" in over["error"] and not over.get("accepted")


@pytest.mark.parametrize("kind,needle",[("cells","cells"),("source","source pixels"),("work","working bytes"),("archive","archive byte")])
def test_direct_build_budgets_are_preflighted(node_driver,kind,needle):
    out=node_driver({"op":"budget","kind":kind}); assert needle in out["error"]
    if kind!="archive": assert out["calls"]==0, "budget must reject before PNG/per-cell encoding"


def test_ui_wiring_busy_recovery_and_history_isolation():
    for control in ("exportTileZip","verifyTileZip","importTileZip","tilePackageSummary"): assert f'id="{control}"' in HTML
    js=MAIN.read_text(encoding="utf-8"); block=js[js.index("async function verifyTilePackageFile"):js.index("window.__assetStudioDebug",js.index("async function verifyTilePackageFile"))]
    assert "finally" in block and "button.disabled=false" in block and "input.value=''" in block
    assert "saveHistory" not in block and "canvas.add" not in block
    assert "$('verifyTileZip').onclick=()=>$('importTileZip')?.click()" in js
