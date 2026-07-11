"""G4: Project v2 canonical Result persistence and fail-closed hydration."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src/main.js").read_text(encoding="utf-8")


def decl(name):
    m = re.search(rf"(?:async\s+)?function\s+{name}\s*\([^)]*\)\s*\{{", JS)
    assert m, f"missing {name}"
    opening = JS.index("{", m.end()-1); depth=0; quote=None; escaped=False
    for i in range(opening, len(JS)):
        c=JS[i]
        if quote:
            if escaped: escaped=False
            elif c=="\\": escaped=True
            elif c==quote: quote=None
        elif c in "'\"`": quote=c
        elif c=="{": depth+=1
        elif c=="}":
            depth-=1
            if depth==0: return JS[m.start():i+1]
    raise AssertionError("unclosed")


def run_runtime():
    names=("createAssetResult","createAssetResultStore","validateProjectResultState")
    source="\n".join(decl(n) for n in names)
    script=source+r'''
const iso='2026-07-11T01:02:03.004Z';
const result={id:'r1',family:'sprite',type:'character',status:'succeeded',preview:{url:'data:image/png;base64,AA=='},sourceRequest:{asset_family:'sprite',asset_type:'character'},normalizedContract:{asset_family:'sprite',asset_type:'character',sprite:{directions:8}},qaSummary:{status:'PASS'},artifacts:[{kind:'png',url:'data:image/png;base64,AA=='}],adopted:true,rejected:false,adoptedAt:iso,rejectedAt:null,createdAt:iso,updatedAt:iso,error:null};
const base={results:[result],selectedId:'r1',compareIds:['r1'],library:[{id:'lib1',resultId:'r1',family:'sprite',type:'character',url:'data:image/png;base64,AA==',createdAt:iso}]};
const capture=x=>{try{return {ok:true,value:validateProjectResultState(x)}}catch(e){return {ok:false,error:e.message}}};
const cases={valid:capture(base),legacy:capture(undefined),duplicate:capture({...base,results:[result,{...result}]}),danglingSelection:capture({...base,selectedId:'missing'}),danglingLibrary:capture({...base,library:[{...base.library[0],resultId:'missing'}]}),duplicateLibrary:capture({...base,library:[base.library[0],{...base.library[0]}]}),mismatch:capture({...base,library:[{...base.library[0],family:'tile'}]}),blob:capture({...base,results:[{...result,preview:{url:'blob:x'},artifacts:[]}]}),missingAdoptedAt:capture({...base,results:[{...result,adoptedAt:null}]}),orphanAdoptedAt:capture({...base,results:[{...result,adopted:false}]}),proto:capture(JSON.parse('{"results":[],"__proto__":{"polluted":true}}'))};
const store=createAssetResultStore(); const safe=cases.valid.value; safe.results.forEach(x=>store.add(x)); store.select(safe.selectedId); store.toggleCompare('r1'); const snap=store.snapshot(); safe.results[0].qaSummary.status='MUTATED';
process.stdout.write(JSON.stringify({cases,snap}));
'''
    cp=subprocess.run(["node","-e",script],cwd=ROOT,text=True,capture_output=True,timeout=15)
    assert cp.returncode==0, cp.stderr
    return json.loads(cp.stdout)


def test_project_v2_additively_serializes_result_ecosystem():
    build=decl("buildProjectV2")
    serializer=decl("serializeAssetResultProjectState")
    for token in ("assetResults", "serializeAssetResultProjectState"):
        assert token in build
    assert "assetLibrary" in serializer


def test_runtime_roundtrip_deep_copy_selection_compare_and_legacy_defaults():
    out=run_runtime(); valid=out["cases"]["valid"]
    assert valid["ok"] and out["cases"]["legacy"]["value"]=={"results":[],"selectedId":None,"compareIds":[],"library":[]}
    assert out["snap"]["selectedId"]=="r1" and out["snap"]["compareIds"]==["r1"]
    assert out["snap"]["values"][0][1]["qaSummary"]["status"]=="PASS"


def test_invalid_graphs_and_nondurable_success_fail_closed():
    cases=run_runtime()["cases"]
    for name in ("duplicate","danglingSelection","danglingLibrary","duplicateLibrary","mismatch","blob","missingAdoptedAt","orphanAdoptedAt","proto"):
        assert not cases[name]["ok"], name


def test_atomic_loader_validates_before_canvas_and_hydrates_tray():
    body=decl("loadProjectV2")
    assert body.index("validateProjectResultState") < body.index("await loadCanvasJson")
    for token in ("rollback", "assetResultStore.restore", "assetLibrary.splice", "renderAssetResultTray"):
        assert token in body


def test_async_canvas_adapter_supports_fabric_promise_and_legacy_callback():
    body=decl("loadCanvasJson")
    assert "fabric?.version" in body
    assert "await canvas.loadFromJSON" in body
    assert "new Promise" in body and "canvas.loadFromJSON(json, resolve)" in body

    script=body+r'''
(async()=>{
  const events=[];
  globalThis.fabric={version:'6.4.0'};
  globalThis.canvas={loadFromJSON:async json=>{events.push('v6-start');await new Promise(r=>setTimeout(r,5));events.push(json.tag);}};
  await loadCanvasJson({tag:'v6-done'}); events.push('v6-awaited');
  globalThis.fabric={version:'5.3.0'};
  globalThis.canvas={loadFromJSON:(json,done)=>{events.push('v5-start');setTimeout(()=>{events.push(json.tag);done();},5);}};
  await loadCanvasJson({tag:'v5-done'}); events.push('v5-awaited');
  process.stdout.write(JSON.stringify(events));
})().catch(error=>{console.error(error);process.exit(1)});'''
    cp=subprocess.run(["node","-e",script],cwd=ROOT,text=True,capture_output=True,timeout=15)
    assert cp.returncode==0, cp.stderr
    assert json.loads(cp.stdout)==['v6-start','v6-done','v6-awaited','v5-start','v5-done','v5-awaited']


def test_v2_loader_awaits_load_and_rollback_and_restores_editor_state():
    body=decl("loadProjectV2")
    assert body.startswith("async function loadProjectV2")
    assert "await loadCanvasJson(targetJson)" in body
    assert "await rollback()" in body
    assert "editorStateBefore=currentEditorState()" in body
    assert "applyEditorState(editorStateBefore)" in body


def test_file_byte_budget_is_checked_before_json_parse():
    handler=JS.split("$('loadProject').onchange",1)[1].split("function generateAiAsset",1)[0]
    assert "PROJECT_MAX_BYTES" in handler
    assert handler.index("PROJECT_MAX_BYTES") < handler.index("JSON.parse")


def test_legacy_load_resets_additive_result_state_and_rerenders_tray():
    body=decl("loadLegacyProjectV1")
    for token in ("assetResultStore.restore", "assetLibrary.splice", "renderAssetResultTray"):
        assert token in body


def test_every_project_history_canvas_result_and_replacement_reference_is_runtime_validated():
    source=decl("validateCanvasResultReferences")
    script=source+r'''const state={results:[{id:'r1',family:'sprite',type:'character'}]};
const capture=x=>{try{validateCanvasResultReferences(x,state);return true}catch(_){return false}};
const cases=[capture({objects:[{id:'source'},{id:'adopted',resultId:'r1',resultFamily:'sprite',resultType:'character',replacesLayerId:'source'}]}),capture({objects:[{id:'x',resultId:'missing',resultFamily:'sprite',resultType:'character'}]}),capture({objects:[{id:'x',resultId:'r1',resultFamily:'tile',resultType:'character'}]}),capture({objects:[{id:'x',replacesLayerId:'missing'}]}),capture({objects:[{id:'x',resultId:'r1'}]})];
process.stdout.write(JSON.stringify(cases));'''
    cp=subprocess.run(["node","-e",script],cwd=ROOT,text=True,capture_output=True,timeout=15)
    assert cp.returncode==0, cp.stderr
    assert json.loads(cp.stdout)==[True,False,False,False,False]


def test_history_entries_persist_additive_undo_snapshot_fields():
    build=decl("buildProjectV2"); loader=decl("loadProjectV2")
    for token in ("assetResultSnapshot","assetLibrary","adoptionRecords"):
        assert token in build and token in loader
    assert "validatedEntries=entries.map" in loader
