import json, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def extract(name):
    text=(ROOT/'src/main.js').read_text()
    start=text.index(f'function {name}(')
    markers={
        'familyExportDescriptor':'\nfunction buildUnifiedFamilyExportPackage(',
        'buildUnifiedFamilyExportPackage':'\nwindow.__assetStudioDebug=',
    }
    if name in markers:
        return text[start:text.index(markers[name],start)]
    raise AssertionError(name)


def run(script):
    p=subprocess.run(['node','-e',script],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    return json.loads(p.stdout)


def test_descriptor_routes_selected_result_and_exposes_exact_options():
    src=extract('familyExportDescriptor')
    cases=[('sprite','character','actor',['sheets','frames','fps','pivot']),('sprite','effect','effect',['full-cell','trim','fps','pivot']),('tile','autotile','tile',['atlas','rules','collision','navigation']),('ui','button','ui',['states','nine-slice','safe-area']),('object','interactable','object',['states','pivot','ground','collision','interaction'])]
    script=src+"\nconsole.log(JSON.stringify("+json.dumps([{'family':a,'type':b,'status':'succeeded'} for a,b,_,_ in cases])+".map(familyExportDescriptor)))"
    out=run(script)
    assert [(x['route'],x['options']) for x in out]==[(c[2],c[3]) for c in cases]
    assert all(x['schema_version']=='asset-studio.family-export-center/v1' for x in out)


def test_dispatch_invokes_exactly_one_family_builder_and_preserves_manifest():
    src=extract('familyExportDescriptor')+'\n'+extract('buildUnifiedFamilyExportPackage')
    script=src+r'''
const calls=[];const mk=n=>(...a)=>{calls.push([n,a.length]);return {manifest:{family:n,schema_version:'x/v1'},files:[],zipName:n+'.zip'}};
const builders={actor:mk('actor'),effect:mk('effect'),tile:mk('tile'),ui:mk('ui'),object:mk('object')};
const families=[['sprite','character'],['sprite','effect'],['tile','autotile'],['ui','button'],['object','interactable']];
const out=families.map(([family,type])=>buildUnifiedFamilyExportPackage({id:'r1',family,type,status:'succeeded'}, {frames:[],contract:{},imageData:{},gridContract:{}}, {}, builders));
console.log(JSON.stringify({calls,out:out.map(x=>({route:x.exportCenter.route,family:x.manifest.family}))}));'''
    out=run(script)
    assert [x[0] for x in out['calls']]==['actor','effect','tile','ui','object']
    assert [x['route'] for x in out['out']]==['actor','effect','tile','ui','object']


def test_export_center_rejects_failed_unknown_and_cross_family_options_before_builder():
    src=extract('familyExportDescriptor')+'\n'+extract('buildUnifiedFamilyExportPackage')
    script=src+r'''
let calls=0;const builders={actor:()=>{calls++},effect:()=>{calls++},tile:()=>{calls++},ui:()=>{calls++},object:()=>{calls++}};const errors=[];
for(const [r,o] of [[{family:'audio',type:'x',status:'succeeded'},{}],[{family:'tile',type:'autotile',status:'failed'},{}],[{family:'ui',type:'button',status:'succeeded'},{mode:'trim'}]])try{buildUnifiedFamilyExportPackage(r,{imageData:{},contract:{}},o,builders)}catch(e){errors.push(e.message)}
console.log(JSON.stringify({calls,errors}));'''
    out=run(script); assert out['calls']==0 and len(out['errors'])==3
