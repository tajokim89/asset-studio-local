"""E4 Object package strict RED/GREEN acceptance: independent ZIP/Pillow audit."""
import base64,hashlib,io,json,re,subprocess,zipfile,zlib
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]; JS=(ROOT/'src/main.js').read_text(); HTML=(ROOT/'index.html').read_text()
def source():
 s=JS; return s[s.index('function effectConcatBytes'):s.index('const EFFECT_EXPORT_LIMITS')]+s[s.index('let crc32Table = null;'):s.index('function exportFull')]+s[s.index('const TILE_EXPORT_LIMITS'):s.index('const TILE_PREVIEW_BUDGETS')]
def run(extra=''):
 fixture=r'''const mk=(seed)=>{const d=new Uint8ClampedArray(4*3*4);for(let i=0;i<12;i++)d.set([seed+i,i,255-seed,(i%3)?255:7],i*4);return {width:4,height:3,data:d}};
const contract={usage:'world',scale:{tile_relative:{width:2,height:1.5},character_relative:.75,footprint:{width:2,depth:1},world_units_per_pixel:.03125},source:{canvas:{width:4,height:3},padding:{top:0,right:0,bottom:0,left:0}},placement:{pivot:{x:.5,y:1},ground_point:{x:.5,y:1},y_sort_point:{x:.5,y:.9},snap_points:[{id:'door',x:0,y:1}]},shadow:{mode:'soft',baked:false},states:[{id:'closed'},{id:'open'},{id:'requested'}],collision:{shape:'box',offset:{x:0,y:0},size:{width:2,depth:1}},interaction:{point:{x:.5,y:.5},radius:1},custom_properties:{loot:'gold',solid:true}};
'''
 script=source()+fixture+r'''(async()=>{try{const args=[mk(10),contract,{states:[{id:'closed',imageData:mk(20)},{id:'open',imageData:mk(30)}],icon:{mode:'contain',width:5,height:5},shadow:{id:'separate',imageData:mk(40)}}];const a=buildObjectExportPackage(...args),b=buildObjectExportPackage(...args);console.log(JSON.stringify({manifest:a.manifest,names:a.files.map(x=>x.name),zip:Buffer.from(await a.zipBlob.arrayBuffer()).toString('base64'),same:Buffer.from(await a.zipBlob.arrayBuffer()).equals(Buffer.from(await b.zipBlob.arrayBuffer()))}));}catch(e){console.log(JSON.stringify({error:e.message}))}})();'''+extra
 p=subprocess.run(['node','--input-type=module','-e',script],text=True,capture_output=True,cwd=ROOT); assert p.returncode==0,p.stderr; return json.loads(p.stdout)
def test_manifest_png_atlas_inventory_deterministic_roundtrip():
 o=run(); assert 'error' not in o and o['same']; m=o['manifest']; assert m['schema_version']=='asset-studio.object-package/v1' and m['family']=='object'
 assert [x['id'] for x in m['states']]==['base','closed','open']; assert m['requested_only_states']==['requested']
 assert m['sourceSize']=={'width':4,'height':3}; assert m['coordinate_convention']=='source-pixel-top-left; normalized anchors; world ground x-right/y-depth-down'
 assert m['placement']['pivot']['coordinate_convention']=='source-normalized-top-left'
 assert m['scale']['footprint']=={'width':2,'depth':1}; assert m['collision']['shape']=='box' and m['custom_properties']['loot']=='gold'
 assert m['shadow']['separate_file']=='shadow/separate.png' and m['icon']['recipe']['resampling']=='nearest-neighbor'
 with zipfile.ZipFile(io.BytesIO(base64.b64decode(o['zip']))) as z:
  assert z.testzip() is None and z.namelist()==o['names']; assert len(z.namelist())==len(set(z.namelist()))
  mm=json.loads(z.read('manifest.json')); assert mm==m
  for state in m['states']:
   im=Image.open(io.BytesIO(z.read(state['path']))).convert('RGBA'); assert im.size==(4,3)
  assert Image.open(io.BytesIO(z.read(m['atlas']['path']))).size==(12,3)
  assert Image.open(io.BytesIO(z.read(m['icon']['path']))).size==(5,5)
  assert all(len(x['sha256'])==64 for x in m['inventory'])
def test_requested_only_not_fake_and_shadow_not_duplicated_when_baked():
 s=source(); script=s+"\n"+r'''const c={usage:'world',scale:{tile_relative:{width:1,height:1},character_relative:1,footprint:{width:1,depth:1}},source:{canvas:{width:1,height:1}},placement:{pivot:{x:.5,y:1},ground_point:{x:.5,y:1},y_sort_point:{x:.5,y:1},snap_points:[]},shadow:{mode:'soft',baked:true},states:[{id:'wish'}],collision:{shape:'box',offset:{x:0,y:0},size:{width:1,depth:1}},interaction:{point:{x:.5,y:.5},radius:1}};const im={width:1,height:1,data:new Uint8ClampedArray([1,2,3,4])};const r=buildObjectExportPackage(im,c,{states:[],shadow:{imageData:im}});console.log(JSON.stringify({m:r.manifest,n:r.files.map(x=>x.name)}));'''
 o=json.loads(subprocess.run(['node','-e',script],text=True,capture_output=True,check=True).stdout); assert o['m']['requested_only_states']==['wish']; assert not any('wish.png' in x for x in o['n']); assert o['m']['shadow']['separate_file'] is None
def test_preflight_rejects_before_pixel_read_or_png_encode_and_unsafe_ids():
 assert 'checkObjectExportBudget' in JS
 s=source(); script=s+'''\nlet reads=0,calls=0;const old=encodeEffectFramePng;encodeEffectFramePng=(...a)=>{calls++;return old(...a)};const data=new Proxy({length:0},{get(o,k){reads++;return o[k]}});try{buildObjectExportPackage({width:99999,height:99999,data},{})}catch(e){console.log(JSON.stringify({error:e.message,reads,calls}))}'''
 o=json.loads(subprocess.run(['node','-e',script],text=True,capture_output=True,check=True).stdout); assert 'budget' in o['error'].lower(); assert o['reads']==0 and o['calls']==0
 assert 'objectExportStatePath' in JS and 'path traversal' in JS.lower() and 'duplicate' in JS.lower()
def test_contract_complexity_and_result_descriptors_fail_before_hostile_pixels():
 s=source(); script=s+r'''
let reads=0,calls=0;encodeEffectFramePng=()=>{calls++;throw Error('encode')};const hostile=new Proxy({},{get(){reads++;throw Error('pixel getter')}});const deep={};let p=deep;for(let i=0;i<40;i++)p=p.x={};try{buildObjectExportPackage({width:1,height:1,data:hostile},{custom_properties:deep},{states:[]})}catch(e){console.log(JSON.stringify({error:e.message,reads,calls}))}'''
 o=json.loads(subprocess.run(['node','-e',script],text=True,capture_output=True,check=True).stdout); assert 'budget' in o['error'].lower() and ('depth' in o['error'].lower() or 'complex' in o['error'].lower()); assert o['reads']==o['calls']==0
 s=source(); script=s+r'''
let reads=0;const hostile=new Proxy({},{get(){reads++;throw Error('pixel getter')}});try{buildObjectExportPackage({width:1,height:1,data:hostile},{states:Array.from({length:129},(_,i)=>({id:'s'+i,imageData:{width:1,height:1,data:hostile}}))})}catch(e){console.log(JSON.stringify({error:e.message,reads}))}'''
 o=json.loads(subprocess.run(['node','-e',script],text=True,capture_output=True,check=True).stdout); assert 'budget' in o['error'].lower() and o['reads']==0
def _audit(raw):
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  infos=z.infolist(); assert len(infos)==len({i.filename for i in infos})
  for i in infos:
   assert i.date_time==(1980,1,1,0,0,0); assert i.create_system==3; assert (i.external_attr>>16)==0o100644
   assert not i.filename.startswith(('/', '\\\\')) and '..' not in i.filename.split('/')
  m=json.loads(z.read('manifest.json')); assert m['inventory_policy']=='payload-files-only; manifest.json excluded to avoid self-reference'
  assert {x['path'] for x in m['inventory']}==set(z.namelist())-{'manifest.json'}
  for x in m['inventory']:
   b=z.read(x['path']); assert x['bytes']==len(b); assert x['crc32']==f'{zlib.crc32(b)&0xffffffff:08x}'; assert x['sha256']==hashlib.sha256(b).hexdigest()
def test_zip_metadata_inventory_and_malicious_fixture_rejection():
 raw=base64.b64decode(run()['zip']); _audit(raw)
 for mutation in (raw[:-3], raw.replace(b'states/base.png',b'../unsafe123.png',1)):
  try: _audit(mutation)
  except Exception: pass
  else: raise AssertionError('malformed/unsafe ZIP accepted')
def test_actual_button_download_finally_history_fabric_provider_isolation():
 assert 'id="exportObjectPackageZip"' in HTML and 'id="objectExportSummary"' in HTML
 block=JS[JS.index('async function exportObjectPackageZip'):JS.index("if ($('buildPixelPrompt'))")]
 assert 'downloadBlob(result.zipBlob,result.zipName)' in block and 'finally' in block and 'button.disabled=false' in block
 for bad in ('saveHistory','canvas.add','fetch(','provider'): assert bad.lower() not in block.lower()
 assert "$('exportObjectPackageZip').onclick" in JS
