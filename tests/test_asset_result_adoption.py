"""G3 acceptance: atomic canonical Result adoption (no project persistence)."""
from pathlib import Path
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src/main.js").read_text(encoding="utf-8")
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "styles/app.css").read_text(encoding="utf-8")


def body(name):
    start = re.search(rf"(?:async\s+)?function\s+{name}\s*\(", JS)
    assert start, f"missing {name}"
    # Skip default object literals in the parameter list.
    closing_params = JS.index(")", start.end())
    opening = JS.index("{", closing_params)
    depth = 0
    quote = None
    escaped = False
    for i in range(opening, len(JS)):
        c = JS[i]
        if quote:
            if escaped: escaped = False
            elif c == "\\": escaped = True
            elif c == quote: quote = None
        elif c in "'\"`": quote = c
        elif c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: return JS[start.start():i + 1]
    raise AssertionError("unclosed function")


def test_public_atomic_adopt_api_and_three_modes_exist():
    adopt = body("adoptResult")
    for token in ("new-layer", "replace-source", "library", "adoptionInFlight", "preflightResultImage"):
        assert token in adopt
    assert "adoptResult" in re.search(r"window\.__assetResultApi\s*=\s*\{[^;]+", JS).group(0)


def test_preconditions_decode_budgets_and_no_provider_call():
    adopt = body("adoptResult")
    preflight = body("preflightResultImage")
    for token in ("succeeded", "rejected", "adopted", "qaSummary", "normalizedContract", "artifacts"):
        assert token in adopt
    for token in ("data:", "image/png", "image/jpeg", "arrayBuffer", "createImageBitmap", "pixels", "timeout"):
        assert token in preflight
    assert "fetch(" not in adopt and "/api/" not in adopt


def test_compact_provenance_serializes_only_references():
    for prop in ("resultId", "resultFamily", "resultType", "replacesLayerId"):
        assert prop in re.search(r"const SERIALIZED_PROPS\s*=\s*\[[^;]+", JS).group(0)
    adopt = body("adoptResult")
    assert "sourceRequest:" not in adopt and "normalizedContract:" not in adopt


def test_accessible_mode_control_and_adopt_buttons_are_styled():
    assert 'id="assetResultAdoptMode"' in HTML
    for mode in ("new-layer", "replace-source", "library"):
        assert f'value="{mode}"' in HTML
    assert "button('채택','adopt'" in JS
    assert ".asset-result-adopt" in CSS


def test_rollback_and_exactly_one_history_commit_are_explicit():
    adopt = body("adoptResult")
    assert "historySnapshot" in adopt and "rollback" in adopt
    assert adopt.count("saveHistory(") == 1
    assert "assetLibrary" in adopt


def test_history_undo_executes_atomically_with_fabric5_and_fabric6():
    script = body("loadCanvasJson") + "\n" + body("loadHistory") + r'''
const SERIALIZED_PROPS=[],$=()=>null,clone=x=>JSON.parse(JSON.stringify(x));
let suppressHistory=false,historyLoadInFlight=null,historyIndex=1,editor=null;
let history=[{json:JSON.stringify({objects:[],tag:'target'}),label:'target',assetResultSnapshot:{values:[],selectedId:null,compareIds:[],marker:'new'},assetLibrary:[{id:'new'}],adoptionRecords:[{id:'new'}]}];
let assetLibrary=[{id:'old'}],adoptionRecords=[{id:'old'}],storeState={values:[],selectedId:null,compareIds:[],marker:'old'};
const assetResultStore={snapshot:()=>clone(storeState),restore:x=>{storeState=clone(x)}};
const parseCanvasJson=x=>typeof x==='string'?JSON.parse(x):x;
const validateProjectResultState=x=>x,validateCanvasResultReferences=()=>true;
const currentEditorState=()=>({marker:'old'}),applyEditorState=x=>{editor=x};
for(const name of ['refreshMaskStateFromCanvas','syncProps','renderLayers','renderHistory','renderAssetResultTray','refreshAiChatState','setStatus'])globalThis[name]=()=>{};
async function run(version,fail){
  globalThis.fabric={version};historyIndex=1;suppressHistory=false;historyLoadInFlight=null;
  assetLibrary.splice(0,assetLibrary.length,{id:'old'});adoptionRecords.splice(0,adoptionRecords.length,{id:'old'});storeState={values:[],selectedId:null,compareIds:[],marker:'old'};
  let state={objects:[],tag:'before'};
  globalThis.canvas={width:10,height:10,backgroundColor:null,toJSON:()=>clone(state),renderAll(){},loadFromJSON(value,done){
    value=clone(value);if(version[0]==='5'){if(fail&&value.tag==='target')throw Error('v5 fail');return setTimeout(()=>{state=value;done()},1)}
    return new Promise((resolve,reject)=>setTimeout(()=>{state=value;fail&&value.tag==='target'?reject(Error('v6 fail')):resolve()},1));
  }};
  let error=null;try{await loadHistory(0)}catch(e){error=e.message}
  return {error,canvas:state.tag,index:historyIndex,suppress:suppressHistory,library:assetLibrary[0].id,store:storeState.marker};
}
(async()=>console.log(JSON.stringify([await run('5.3.0',false),await run('5.3.0',true),await run('6.4.0',false),await run('6.4.0',true)])))();
'''
    cp = subprocess.run(["node", "-e", script], cwd=ROOT, text=True, capture_output=True)
    assert cp.returncode == 0, cp.stderr
    results = json.loads(cp.stdout)
    for success in (results[0], results[2]):
        assert success == {"error": None, "canvas": "target", "index": 0, "suppress": False, "library": "new", "store": "new"}
    for failure in (results[1], results[3]):
        assert failure["error"] and failure["canvas"] == "before"
        assert failure["index"] == 1 and failure["suppress"] is False
        assert failure["library"] == "old" and failure["store"] == "old"


def test_keyboard_history_shortcuts_handle_async_rejections():
    shortcut = body("handleHistoryShortcut")
    assert "undoHistory().catch(reportHistoryError)" in shortcut
    assert shortcut.count("redoHistory().catch(reportHistoryError)") == 2
