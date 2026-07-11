"""G1 RED contract for the canonical, DOM-independent asset Result model.

The tests execute declarations extracted from ``src/main.js`` in Node.  They do
not provide test implementations or evaluate the browser bootstrap.  G1's
small public seam is intentionally named so later tray/adopt/project work can
share it: createAssetResult, transitionAssetResult, and createAssetResultStore.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS_PATH = ROOT / "src" / "main.js"
HELPERS = ("createAssetResult", "transitionAssetResult", "createAssetResultStore")
REPRESENTATIVES = (
    ("sprite", "character"),
    ("sprite", "effect"),
    ("tile", "terrain"),
    ("ui", "button"),
    ("object", "interactable"),
)


def _declaration(source: str, name: str):
    """Return a complete function/const declaration using a quote-aware scan."""
    match = re.search(
        rf"(?:\b(?:async\s+)?function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{|"
        rf"\bconst\s+{re.escape(name)}\s*=)",
        source,
    )
    if not match:
        return None
    depths = {"(": 0, "[": 0, "{": 0}
    closing = {")": "(", "]": "[", "}": "{"}
    quote = None
    escaped = False
    saw_body = False
    for index in range(match.end() - 1, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char in depths:
            depths[char] += 1
            saw_body = saw_body or char == "{"
        elif char in closing:
            depths[closing[char]] -= 1
            if min(depths.values()) < 0:
                raise AssertionError(f"Unbalanced production declaration for {name}")
            if match.group(0).lstrip().startswith(("function", "async function")) and saw_body and not any(depths.values()):
                return source[match.start():index + 1]
        elif char == ";" and saw_body and not any(depths.values()):
            return source[match.start():index + 1]
    raise AssertionError(f"Unclosed production declaration for {name}")


def _sources_or_skip():
    source = JS_PATH.read_text(encoding="utf-8")
    declarations = [_declaration(source, name) for name in HELPERS]
    missing = [name for name, declaration in zip(HELPERS, declarations) if declaration is None]
    if missing:
        pytest.skip("canonical Result model not implemented yet: " + ", ".join(missing))
    assert all(declaration is not None for declaration in declarations)
    return "\n\n".join(declaration for declaration in declarations if declaration is not None)


def _runtime():
    declarations = _sources_or_skip()
    cases = json.dumps(REPRESENTATIVES)
    script = declarations + f"""
const clone = value => JSON.parse(JSON.stringify(value));
const clockValues = ['2026-07-11T01:02:03.004Z','2026-07-11T01:02:04.005Z','2026-07-11T01:02:05.006Z'];
let clockIndex = 0, idIndex = 0;
const deps = {{ clock: () => clockValues[Math.min(clockIndex++, clockValues.length - 1)], idFactory: () => `result-${{++idIndex}}` }};
const base = (family, type) => ({{
  family, type, status:'pending', preview:null,
  sourceRequest:{{asset_family:family,asset_type:type,prompt:'exact',nested:{{n:1}}}},
  normalizedContract:{{asset_family:family,asset_type:type,[family]:{{marker:`${{family}}-only`}}}},
  qaSummary:null, artifacts:[], adopted:false, rejected:false, error:null,
}});
const capture = fn => {{ try {{ return {{ok:true,value:fn()}}; }} catch (error) {{ return {{ok:false,message:String(error && error.message || error)}}; }} }};
const made = Object.fromEntries({cases}.map(([family,type]) => [`${{family}}/${{type}}`, createAssetResult(base(family,type), deps)]));
const source = base('sprite','character');
const isolated = createAssetResult(source, deps);
source.sourceRequest.nested.n=99; source.normalizedContract.sprite.marker='mutated'; source.artifacts.push({{url:'mutated'}});
const success = transitionAssetResult(isolated, {{status:'succeeded',preview:{{url:'/durable/a.png'}},qaSummary:{{status:'PASS'}},artifacts:[{{kind:'png',url:'/durable/a.png'}}]}}, deps);
const failure = transitionAssetResult(createAssetResult(base('ui','button'), deps), {{status:'failed',error:{{code:'PROVIDER_ERROR',message:'no image',retryable:true}}}}, deps);
const store = createAssetResultStore();
const storeAdd1 = capture(() => store.add(success));
const storeAdd2 = capture(() => store.add(success));
const stored = typeof store.list === 'function' ? store.list() : store.items;
const invalid = {{}};
for (const [name, mutate] of Object.entries({{
 family:x=>x.family='video', type:x=>x.type='', status:x=>x.status='mystery',
 timestamp:x=>x.createdAt='not-a-date', nonJson:x=>x.sourceRequest={{bad:()=>1}},
 proto:x=>x.sourceRequest=JSON.parse('{{"__proto__":{{"polluted":true}}}}'),
 successNoDurable:x=>{{x.status='succeeded';x.preview={{url:'blob:temporary'}};x.artifacts=[];}},
 failedNoError:x=>{{x.status='failed';x.error=null;}},
}})) {{ const value=base('tile','terrain'); mutate(value); invalid[name]=capture(()=>createAssetResult(value,deps)); }}
const rejectThenAdopt = capture(() => transitionAssetResult(transitionAssetResult(success,{{rejected:true}},deps),{{adopted:true}},deps));
const adoptThenReject = capture(() => transitionAssetResult(transitionAssetResult(success,{{adopted:true}},deps),{{rejected:true}},deps));
process.stdout.write(JSON.stringify({{made,isolated,success,failure,invalid,rejectThenAdopt,adoptThenReject,storeAdd1,storeAdd2,stored,domType:typeof document}}));
"""
    completed = subprocess.run(["node", "-e", script], cwd=ROOT, text=True, capture_output=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@pytest.fixture(scope="module")
def runtime():
    return _runtime()


def test_canonical_result_helpers_exist_as_extractable_production_javascript():
    source = JS_PATH.read_text(encoding="utf-8")
    missing = [name for name in HELPERS if _declaration(source, name) is None]
    assert not missing, f"canonical Result helpers missing from production JS: {missing}"


@pytest.mark.parametrize("family,type_", REPRESENTATIVES)
def test_five_representative_types_have_common_envelope_and_exact_isolated_contract(runtime, family, type_):
    result = runtime["made"][f"{family}/{type_}"]
    assert result["family"] == family and result["type"] == type_
    assert result["status"] == "pending"
    assert result["sourceRequest"]["asset_family"] == family
    assert result["sourceRequest"]["asset_type"] == type_
    assert result["normalizedContract"] == {"asset_family": family, "asset_type": type_, family: {"marker": f"{family}-only"}}
    assert set(result) >= {"id","family","type","status","preview","sourceRequest","normalizedContract","qaSummary","artifacts","adopted","rejected","createdAt","updatedAt","error"}


def test_result_owns_deep_json_copies_and_has_stable_injected_ids_and_clock(runtime):
    assert runtime["isolated"]["sourceRequest"]["nested"]["n"] == 1
    assert runtime["isolated"]["normalizedContract"]["sprite"]["marker"] == "sprite-only"
    assert runtime["isolated"]["artifacts"] == []
    ids = [item["id"] for item in runtime["made"].values()] + [runtime["isolated"]["id"]]
    assert len(ids) == len(set(ids)) and ids[0] == "result-1"
    assert runtime["made"]["sprite/character"]["createdAt"] == "2026-07-11T01:02:03.004Z"


def test_pending_transitions_to_succeeded_or_failed_with_semantic_guards(runtime):
    assert runtime["success"]["status"] == "succeeded"
    assert runtime["success"]["preview"]["url"] == "/durable/a.png"
    assert runtime["success"]["artifacts"] and runtime["success"]["qaSummary"]["status"] == "PASS"
    assert runtime["failure"]["status"] == "failed"
    assert runtime["failure"]["error"] == {"code":"PROVIDER_ERROR","message":"no image","retryable":True}
    assert runtime["failure"]["adopted"] is False


def test_rejected_and_adopted_are_mutually_exclusive(runtime):
    assert runtime["rejectThenAdopt"]["ok"] is False
    assert runtime["adoptThenReject"]["ok"] is False


@pytest.mark.parametrize("case", ("family","type","status","timestamp","nonJson","proto","successNoDurable","failedNoError"))
def test_malformed_or_unsafe_results_fail_closed(runtime, case):
    assert runtime["invalid"][case]["ok"] is False, case


def test_store_is_dom_independent_and_deduplicates_by_id(runtime):
    assert runtime["domType"] == "undefined"
    assert runtime["storeAdd1"]["ok"] is True
    assert runtime["storeAdd2"]["ok"] is False
    assert len(runtime["stored"]) == 1


def test_generation_path_hands_the_canonical_result_full_request_response_qa_and_artifacts():
    source = JS_PATH.read_text(encoding="utf-8")
    body = _declaration(source, "generateAiAsset")
    assert body is not None
    assert re.search(r"(?:createAssetResult|recordAssetGenerationResult)\s*\(", body), "generation path does not create a canonical Result"
    for token in ("payload", "data", "qa", "artifacts"):
        assert re.search(rf"\b{token}\b", body), f"generation path drops {token}"


def test_store_restore_rejects_invalid_snapshot_atomically_in_real_node_runtime():
    declarations = _sources_or_skip()
    script = declarations + r'''const iso='2026-07-11T01:02:03.004Z';
const value={id:'r1',family:'sprite',type:'character',status:'succeeded',preview:{url:'/r.png'},sourceRequest:{asset_family:'sprite',asset_type:'character'},normalizedContract:{asset_family:'sprite',asset_type:'character'},qaSummary:{status:'PASS'},artifacts:[{url:'/r.png'}],adopted:false,rejected:false,adoptedAt:null,rejectedAt:null,createdAt:iso,updatedAt:iso,error:null};
const store=createAssetResultStore(); store.add(value); store.select('r1'); const before=store.snapshot();
const bad=[{values:[["r1",value],["r1",value]],selectedId:'r1',compareIds:[]},{values:[["r1",value]],selectedId:'missing',compareIds:[]},{values:[["r1",value]],selectedId:'r1',compareIds:['r1','r1']},{values:[["wrong",value]],selectedId:null,compareIds:[]}];
const rejected=bad.map(snapshot=>{try{store.restore(snapshot);return false}catch(_){return JSON.stringify(store.snapshot())===JSON.stringify(before)}});
const detached=store.snapshot(); detached.values[0][1].qaSummary.status='MUTATED';
process.stdout.write(JSON.stringify({rejected,after:store.snapshot()}));
'''
    completed = subprocess.run(["node", "-e", script], cwd=ROOT, text=True, capture_output=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
    out = json.loads(completed.stdout)
    assert all(out["rejected"])
    assert out["after"]["values"][0][1]["qaSummary"]["status"] == "PASS"
