import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "src" / "motion-studio-core.js"


def node_json(source):
    result = subprocess.run(["node", "-e", source], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_schema_normalization_zero_safety_and_no_mutation():
    data = node_json("""
const C=require('./src/motion-studio-core.js');
const raw={asset:{id:'hero_1',canvas:{width:32,height:48},pivot:{x:0,y:0},ground:{x:0,y:47},facing:'right',sampling:'nearest'},primary:{strategy:'static',data:{}},overlays:[]};
const before=JSON.stringify(raw); const m=C.normalizeManifest(raw);
let errors=[]; for(const bad of [
 {asset:{id:'../bad',canvas:{width:32,height:32},pivot:{x:0,y:0},ground:{x:0,y:0}},primary:{strategy:'static',data:{}}},
 {asset:{id:'x',canvas:{width:'Infinity',height:32},pivot:{x:0,y:0},ground:{x:0,y:0}},primary:{strategy:'static',data:{}}},
 {asset:{id:'x',canvas:{width:20000,height:32},pivot:{x:0,y:0},ground:{x:0,y:0}},primary:{strategy:'static',data:{}}},
 {asset:{id:'x',canvas:{width:32,height:32},pivot:{x:33,y:0},ground:{x:0,y:0}},primary:{strategy:'bogus',data:{}}},
 {asset:{id:'x',canvas:{width:32,height:32},pivot:{x:0,y:0},ground:{x:0,y:0}},primary:{strategy:'transform_tween',data:{pixel_snap:'false'}}}
]) { try { C.normalizeManifest(bad); errors.push(false); } catch(e){errors.push(true)} }
console.log(JSON.stringify({schema:m.schema,zero:[m.asset.pivot.x,m.asset.pivot.y,m.asset.ground.x],same:before===JSON.stringify(raw),errors}));
""")
    assert data == {"schema":"asset-studio.motion-manifest/v1","zero":[0,0,0],"same":True,"errors":[True]*5}


def test_router_precedence_overlay_and_rig_never_auto():
    data = node_json("""
const C=require('./src/motion-studio-core.js');
const cases=[{}, {motion:true}, {motion:true,silhouette_change:true,persistent_states:true},
 {motion:true,silhouette_change:true,rigid_parts:3,meaningful_poses:3},
 {motion:true,silhouette_change:true,meaningful_poses:3},
 {motion:true,silhouette_change:true,meaningful_poses:3,contact_changes:true},
 {motion:true,silhouette_change:true,meaningful_poses:7,weak_feedback:true,rig_candidate:true,rig:{skins:2,equipment:true,clips:3,rest_pose:true,adapter:true}}];
console.log(JSON.stringify(cases.map(C.routeStrategy)));
""")
    assert [x["primary"] for x in data] == ["static","transform_tween","state_swap","rigid_parts","limited_frames","full_frames","full_frames"]
    assert data[-1]["overlays"] == ["vfx"]
    assert data[-1]["rig_gate"]["eligible"] is True
    assert data[-1]["requires_approval"] is True
    assert "rig_paper_doll" in data[-1]["alternatives"]


def test_deterministic_transform_and_frame_sampling():
    data = node_json("""
const C=require('./src/motion-studio-core.js');
const tween={start:{x:0,y:0,rotation:0,scale:1,opacity:1},end:{x:9,y:5,rotation:90,scale:2,opacity:0},duration:1000,easing:'linear',loop:'pingpong',pixel_snap:true};
const clip={loop:'loop',frames:[{id:'a',duration:100},{id:'b',duration:200},{id:'c',duration:100}]};
console.log(JSON.stringify({a:C.sampleTransform(tween,500),b:C.sampleTransform(tween,1500),f:[0,99,100,299,400].map(t=>C.sampleFrameClip(clip,t)),again:C.sampleTransform(tween,500)}));
""")
    assert data["a"] == data["again"] == {"x":5,"y":3,"rotation":45,"scale":1.5,"opacity":0.5,"progress":0.5}
    assert data["b"] == data["a"]
    assert [x["index"] for x in data["f"]] == [0,0,1,1,0]


def test_all_strategy_validation_graphs_rig_gate_and_vfx_separation():
    data = node_json("""
const C=require('./src/motion-studio-core.js');
const valid={
 static:{},
 transform_tween:{start:{x:0,y:0,rotation:0,scale:1,opacity:1},end:{x:1,y:1,rotation:0,scale:1,opacity:1},duration:100,loop:'once',easing:'linear',pixel_snap:false},
 state_swap:{states:[{id:'idle',default:true,duration:100},{id:'on',default:false,duration:100}]},
 rigid_parts:{parts:[{id:'arm',parent:null,pivot:{x:0,y:0},socket:{x:0,y:0},offset:{x:0,y:0},rotation_min:-20,rotation_max:20}]},
 limited_frames:{loop:'loop',frames:[{id:'a',duration:100},{id:'b',duration:100}]},
 full_frames:{loop:'once',frames:[{id:'a',duration:100}]},
 rig_paper_doll:{approved:true,gate:{skins:2,equipment:true,clips:3,rest_pose:true,adapter:true},bones:[{id:'root',parent:null}],slots:[{id:'body',bone:'root'}]}
};
const results=Object.entries(valid).map(([strategy,data])=>C.validateStrategy(strategy,data));
const badCycle=C.validateStrategy('rigid_parts',{parts:[{id:'a',parent:'b'},{id:'b',parent:'a'}]});
const badLimited=C.validateStrategy('limited_frames',{frames:[{id:'a',duration:1}]});
const badRig=C.validateStrategy('rig_paper_doll',{approved:false,gate:valid.rig_paper_doll.gate,bones:[{id:'r'}],slots:[]});
const vfx=C.validateVfx({enabled:true,trigger:'hit',anchor:'root',offset:{x:0,y:0},duration:100,blend:'normal',seed:0});
console.log(JSON.stringify({results,badCycle,badLimited,badRig,vfx}));
""")
    assert all(x["valid"] for x in data["results"])
    assert not data["badCycle"]["valid"]
    assert not data["badLimited"]["valid"]
    assert not data["badRig"]["valid"]
    assert data["vfx"]["valid"]


def test_qa_stable_serialization_import_roundtrip_and_scene_sampler():
    data = node_json("""
const C=require('./src/motion-studio-core.js');
const a={asset:{sampling:'nearest',facing:'right',ground:{y:31,x:0},pivot:{y:0,x:0},canvas:{height:32,width:32},id:'hero',source:{name:'hero.png',uri:'data:image/png;base64,AA=='}},primary:{data:{},strategy:'static'},overlays:[],manual_visual_approval:true};
const b={overlays:[],primary:{strategy:'static',data:{}},asset:{id:'hero',canvas:{width:32,height:32},pivot:{x:0,y:0},ground:{x:0,y:31},facing:'right',sampling:'nearest',source:{uri:'data:image/png;base64,AA==',name:'hero.png'}},manual_visual_approval:true};
const m=C.normalizeManifest(a), text=C.stableStringify(m), imported=C.importManifest(text);
const qa=C.runQA(m,{vfx_off:true});
const invalidQa=C.runQA({...m,primary:{strategy:'limited_frames',data:{frames:[]}}},{vfx_off:true});
const scene=C.samplePreview({...m,primary:{strategy:'static',data:{}}},123,{vfx:true});
console.log(JSON.stringify({same:C.stableStringify(C.normalizeManifest(b))===text,round:C.stableStringify(imported)===text,qa,invalidQa,scene}));
""")
    assert data["same"] and data["round"]
    assert data["qa"]["status"] == "PASS"
    assert data["invalidQa"]["status"] == "FAIL"
    assert data["scene"]["strategy"] == "static"
