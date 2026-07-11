"""F1 Actor deterministic motion + explicit visual approval acceptance."""
import base64, hashlib, io, json, subprocess, zipfile, zlib
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]; JS=(ROOT/'src/main.js').read_text(); HTML=(ROOT/'index.html').read_text()
def source():
 return JS[JS.index('function effectConcatBytes'):JS.index('const EFFECT_EXPORT_LIMITS')]+JS[JS.index('let crc32Table = null;'):JS.index('function buildStoredZip')]+JS[JS.index('const TILE_EXPORT_LIMITS'):JS.index('const OBJECT_PREVIEW_BUDGETS')]
def run(extra):
 p=subprocess.run(['node','--input-type=module','-e',source()+extra],cwd=ROOT,text=True,capture_output=True);assert p.returncode==0,p.stderr;return json.loads(p.stdout)
FIX="""const dirs=['S','W','E','N'],frames=[];for(let r=0;r<4;r++)for(let f=0;f<4;f++){let d=new Uint8ClampedArray(8*8*4),p=(x,y)=>d.set([60+r*30,120,210,255],(y*8+x)*4);for(let y=2;y<5;y++)for(let x=3;x<5;x++)p(x,y);if(f===0||f===2){p(3,5);p(3,6);p(4,5);p(4,6)}else if(f===1){p(2,5);p(2,6);p(3,5);p(3,6);p(4,5)}else{p(4,5);p(4,6);p(5,5);p(5,6);p(3,5)}frames.push({direction:dirs[r],action:'walk',index:f,beatId:['contact','down','passing','up'][f],imageData:{width:8,height:8,data:d},root:{x:.5,y:.75},contact:{x:.5,y:.75}})};const contract={subtype:'character',directions:{mode:'4dir',requested:dirs,row_order:dirs},actions:[{id:'walk',frame_count:4,fps:8,loop:true,beats:['contact','down','passing','up']}],grid:{cell:{width:8,height:8},gap:1},sourceSize:{width:8,height:8},anchors:{pivot:{x:.5,y:.75},root:{x:.5,y:.75},contact:{x:.5,y:.75}}};const approval={status:'APPROVED',reviewer:'qa',source:'manual-browser-review',timestamp:'2026-07-11T00:00:00.000Z',evidence_id:'fixture-review-v1',artifact_digest:actorArtifactDigest(frames,contract)};"""
def test_contract_qa_package_roundtrip_and_honesty():
 o=run(FIX+"const q=evaluateActorProductionQA(frames,contract,approval),a=buildActorExportPackage(frames,contract,approval),b=buildActorExportPackage(frames,contract,approval);console.log(JSON.stringify({q,m:a.manifest,n:a.files.map(x=>x.name),z:Buffer.from(a.zipBytes).toString('base64'),same:Buffer.from(a.zipBytes).equals(Buffer.from(b.zipBytes))}))")
 assert o['same'] and o['q']['status']=='PASS' and o['q']['deterministic_status']=='PASS';m=o['m'];assert m['qa']['evidence']['visual_review']['status']=='APPROVED'
 with zipfile.ZipFile(io.BytesIO(base64.b64decode(o['z']))) as z:
  assert z.testzip() is None and z.namelist()==o['n']; atlas=Image.open(io.BytesIO(z.read('atlas.png'))).convert('RGBA');assert atlas.size==(35,35)
  for x in m['frames']:
   frame=Image.open(io.BytesIO(z.read(x['path']))).convert('RGBA');assert list(frame.getdata())==list(atlas.crop((x['atlas']['x'],x['atlas']['y'],x['atlas']['x']+8,x['atlas']['y']+8)).getdata())
  for x in m['inventory']:
   b=z.read(x['path']);assert x['crc32']==f'{zlib.crc32(b)&0xffffffff:08x}' and x['sha256']==hashlib.sha256(b).hexdigest()
def test_fail_closed_stable_motion_and_visual_reasons():
 script="""const result={};const check=(name,mut,ap=approval)=>{const fs=frames.map(f=>({...f,imageData:{...f.imageData,data:new Uint8ClampedArray(f.imageData.data)}}));mut(fs);const q=evaluateActorProductionQA(fs,contract,ap);result[name]={status:q.status,det:q.deterministic_status,codes:q.reasons.map(x=>x.code)}};
 check('identical',fs=>{for(const d of dirs){const z=fs.find(x=>x.direction===d&&x.index===0).imageData.data;fs.filter(x=>x.direction===d).forEach(x=>x.imageData.data=new Uint8ClampedArray(z))}});
 check('color',fs=>fs.forEach((x,i)=>{const a=fs.find(y=>y.direction===x.direction&&y.index===0).imageData.data;x.imageData.data=new Uint8ClampedArray(a);x.imageData.data[0]=i}));
 check('edge',fs=>{fs[0].imageData.data.set([1,1,1,255],0)});check('none',()=>{},null);check('visualfail',()=>{},{status:'FAIL',reviewer:'qa',source:'manual',evidence_id:'x'});check('neutral',fs=>{fs.filter(x=>x.index===2).forEach(x=>{x.imageData.data[(2*8+2)*4+3]=255;x.imageData.data[(3*8+2)*4+3]=255})});check('beat',fs=>fs[0].beatId='wrong');console.log(JSON.stringify(result));"""
 o=run(FIX+script)
 assert 'IDENTICAL_FRAMES' in o['identical']['codes'] and 'COLOR_ONLY_MOTION' in o['color']['codes'] and 'ALPHA_EDGE_CONTACT' in o['edge']['codes']
 assert o['none']['codes'][-1]=='VISUAL_APPROVAL_REQUIRED' and 'VISUAL_REVIEW_FAILED' in o['visualfail']['codes'] and 'LOOP_NEUTRAL_MISMATCH' in o['neutral']['codes'] and 'BEAT_ORDER' in o['beat']['codes']
def test_export_block_and_accessible_ui_isolation():
 o=run(FIX+"try{buildActorExportPackage(frames,contract)}catch(e){console.log(JSON.stringify({e:e.message,codes:e.qa.reasons.map(x=>x.code)}))}")
 assert 'blocked' in o['e'] and 'VISUAL_APPROVAL_REQUIRED' in o['codes']
 for x in ('actorProductionPanel','actorDirectionSelect','actorActionSelect','actorPreviewCanvas','actorQaSummary','actorVisualApproval','exportActorPackageZip'):assert f'id=\"{x}\"' in HTML
 block=JS[JS.index('async function exportActorPackageZip'):JS.index('const OBJECT_PREVIEW_BUDGETS')];assert 'finally' in block and 'window.__actorVisualApproval' in block and 'resetActorVisualApproval' in block
 for bad in ('saveHistory','canvas.add','fetch(','provider'):assert bad.lower() not in block.lower()

def test_approval_is_bound_to_exact_artifact_and_metadata_is_strict():
 script="""const out={};const codes=(fs,c,ap)=>evaluateActorProductionQA(fs,c,ap).reasons.map(x=>x.code);for(const [name,value] of [['bool',true],['date','not-a-date'],['object',{}]])out[name]=codes(frames,contract,{...approval,timestamp:value});for(const [name,value] of [['empty',''],['long','x'.repeat(257)],['object',{}]])out['evidence_'+name]=codes(frames,contract,{...approval,evidence_id:value});const mutations={pixel:(fs,c)=>fs[0].imageData.data[4]^=1,order:(fs,c)=>fs.reverse(),contract:(fs,c)=>c.grid.gap=2,action:(fs,c)=>c.actions[0].fps=9,direction:(fs,c)=>c.directions.requested.reverse()};for(const [name,mut] of Object.entries(mutations)){const fs=frames.map(f=>({...f,imageData:{...f.imageData,data:new Uint8ClampedArray(f.imageData.data)}})),c=JSON.parse(JSON.stringify(contract));mut(fs,c);out[name]=codes(fs,c,approval)}console.log(JSON.stringify(out));"""
 o=run(FIX+script)
 for name in ('bool','date','object','evidence_empty','evidence_long','evidence_object'):assert 'VISUAL_APPROVAL_REQUIRED' in o[name]
 for name in ('pixel','order','contract','action','direction'):assert 'VISUAL_APPROVAL_STALE' in o[name]

def test_visual_approval_timestamp_requires_canonical_utc_rfc3339():
 bad={
  'zero':0,'date_only':'2026-07-11','impossible_day':'2026-02-30T00:00:00.000Z',
  'non_padded':'2026-7-11T00:00:00.000Z','space_timezone':'2026-07-11 00:00:00.000Z',
  'positive_offset':'2026-07-11T09:00:00.000+09:00','zero_offset':'2026-07-11T00:00:00.000+00:00',
  'invalid_leap_day':'2025-02-29T00:00:00.000Z','seconds_only':'2026-07-11T00:00:00Z',
  'extra_fraction':'2026-07-11T00:00:00.0000Z','lowercase_z':'2026-07-11T00:00:00.000z',
 }
 script=f"""const out={{}};for(const [name,value] of Object.entries({json.dumps(bad)}))out[name]=evaluateActorProductionQA(frames,contract,{{...approval,timestamp:value}}).reasons.map(x=>x.code);out.canonical=evaluateActorProductionQA(frames,contract,{{...approval,timestamp:'2024-02-29T23:59:59.999Z'}}).status;console.log(JSON.stringify(out));"""
 o=run(FIX+script)
 for name in bad:assert 'VISUAL_APPROVAL_REQUIRED' in o[name],name
 assert o['canonical']=='PASS'

def test_non_walk_one_pixel_motion_is_too_small():
 script="""const c={...contract,directions:{mode:'1dir',requested:['S'],row_order:['S']},actions:[{id:'attack',frame_count:2,fps:8,loop:false,beats:['windup','hit']}]};const fs=frames.slice(0,2).map((f,i)=>({...f,direction:'S',action:'attack',index:i,beatId:c.actions[0].beats[i],imageData:{...f.imageData,data:new Uint8ClampedArray(frames[0].imageData.data)}}));fs[1].imageData.data[(4*8+2)*4+3]=255;const ap={...approval,artifact_digest:actorArtifactDigest(fs,c)};const q=evaluateActorProductionQA(fs,c,ap);console.log(JSON.stringify({codes:q.reasons.map(x=>x.code)}));"""
 assert 'MOTION_TOO_SMALL' in run(FIX+script)['codes']
