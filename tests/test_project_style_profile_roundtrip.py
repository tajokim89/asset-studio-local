"""H3 runtime contracts: lossless family drafts and strict project identity."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src/main.js").read_text(encoding="utf-8")


def decl(name):
    match = re.search(rf"function\s+{name}\s*\([^)]*\)\s*\{{", JS)
    assert match, name
    start = match.start(); opening = JS.index("{", match.end()-1)
    depth=0; quote=None; escaped=False
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
            if depth==0: return JS[start:i+1]
    raise AssertionError("unclosed")


def node(script):
    cp=subprocess.run(["node","-e",script],cwd=ROOT,text=True,capture_output=True,timeout=15)
    assert cp.returncode==0, cp.stderr
    return json.loads(cp.stdout)


def test_four_family_drafts_keep_accepted_lexical_values_byte_identical_at_runtime():
    source="\n".join(decl(n) for n in ("projectAssetSubtypesForFamily","defaultProjectFamilyDraft","validateProjectFamilyDrafts","hydrateProjectFamilyDrafts"))
    script=r'''
const PROJECT_FAMILIES=['sprite','tile','ui','object'];
const ASSET_FAMILY_SUBTYPES={sprite:['character'],tile:['floor'],ui:['button'],object:['item']};
const assetRecipeRegistryState={status:'ready',registry:{},production:{},known:ASSET_FAMILY_SUBTYPES};
const ASSET_FAMILY_OUTPUT_DEFAULTS={sprite:{width:512,height:512,background:'transparent'},tile:{width:512,height:512,background:'opaque'},ui:{width:1024,height:512,background:'transparent'},object:{width:512,height:512,background:'transparent'}};
const PROJECT_DRAFT_SHARED_CONTROLS=['assetCorePrompt','assetOutputWidth','assetOutputHeight','assetBackground'];
const PROJECT_DRAFT_FAMILY_CONTROLS={sprite:[],tile:[],ui:[],object:[]};
const assetFamilyDrafts=new Map(); let selectedAssetFamily='sprite';
const elements={}; const $=id=>elements[id]||(elements[id]={type:'text',value:'',dataset:{},addEventListener(){}});
const renderAssetSubtypeOptions=()=>{},restoreAssetCreationDraft=()=>{},updateAssetFamilyUi=()=>{};
'''+source+r'''
const widths=['0512','+512','0001','4096'];
const input=Object.fromEntries(PROJECT_FAMILIES.map((f,i)=>[f,{subtype:ASSET_FAMILY_SUBTYPES[f][0],controls:{assetCorePrompt:'draft-'+f,assetOutputWidth:widths[i],assetOutputHeight:'0512',assetBackground:i===1?'opaque':'transparent'}}]));
const before=JSON.stringify(input); hydrateProjectFamilyDrafts(input,'ui');
const stored=Object.fromEntries(PROJECT_FAMILIES.map(f=>[f,assetFamilyDrafts.get(f)]));
const bad=['','0','4097','1e3',' 512','-1'];
const rejected=bad.map(value=>{const x=structuredClone(input);x.sprite.controls.assetOutputWidth=value;try{validateProjectFamilyDrafts(x);return false}catch{return true}});
const emptyBg=structuredClone(input);emptyBg.sprite.controls.assetBackground='';let bgRejected=false;try{validateProjectFamilyDrafts(emptyBg)}catch{bgRejected=true}
process.stdout.write(JSON.stringify({same:before===JSON.stringify(input),stored,selectedAssetFamily,rejected,bgRejected}));
'''
    out=node(script)
    assert out["same"] and out["selectedAssetFamily"]=="ui"
    assert [out["stored"][f]["width"] for f in ("sprite","tile","ui","object")]==["0512","+512","0001","4096"]
    assert all(out["rejected"]) and out["bgRejected"]


def test_project_timestamp_validation_precedes_first_canvas_mutation_and_identity_is_exact():
    body=decl("loadProjectV2")
    assert body.index("canonicalTimestamp") < body.index("await loadCanvasJson(targetJson)")
    assert "Date.parse(projectUpdatedAt)<Date.parse(projectCreatedAt)" in body
    assert "projectV2Identity={createdAt:projectCreatedAt,updatedAt:projectUpdatedAt}" in body
    assert "projectCreatedAt===undefined&&projectUpdatedAt===undefined" in body


def test_legacy_runtime_loader_has_full_async_rollback_surface():
    body=decl("loadLegacyProjectV1")
    for token in ("canvasBefore", "historyBefore", "editorStateBefore", "storeBefore", "libraryBefore", "recordsBefore", "styleBefore", "draftsBefore", "selectedFamilyBefore", "identityBefore", "await loadCanvasJson(canvasBefore)", "applyEditorState(editorStateBefore)"):
        assert token in body
