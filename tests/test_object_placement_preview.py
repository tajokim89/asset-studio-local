"""E3 deterministic, read-only Object placement preview contracts."""
import json, re, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/'src/main.js').read_text()
HTML=(ROOT/'index.html').read_text()
CSS=(ROOT/'styles/app.css').read_text()

def fn(name):
    m=re.search(rf'\bfunction\s+{name}\s*\([^)]*\)\s*\{{',JS); assert m, f'missing {name}'
    depth=0; quote=None; esc=False
    for i in range(m.end()-1,len(JS)):
        c=JS[i]
        if quote:
            if esc: esc=False
            elif c=='\\': esc=True
            elif c==quote: quote=None
        elif c in "'\"`": quote=c
        elif c=='{': depth+=1
        elif c=='}':
            depth-=1
            if not depth:return JS[m.start():i+1]
    raise AssertionError('unclosed')

def run(script):
    budget=re.search(r'const OBJECT_PREVIEW_BUDGETS = Object\.freeze\([^;]+;',JS,re.S)
    assert budget
    p=subprocess.run(['node','-e',budget.group(0)+'\n'+script],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    return json.loads(p.stdout)

BASE={"usage":"world","scale":{"tile_relative":{"width":2,"height":1.5},"character_relative":.75,"footprint":{"width":2,"depth":1}},"source":{"canvas":{"width":8,"height":8},"padding":{"top":0,"right":0,"bottom":0,"left":0}},"placement":{"pivot":{"x":.5,"y":1},"ground_point":{"x":.5,"y":1},"y_sort_point":{"x":.5,"y":.875},"snap_points":[{"id":"a","x":0,"y":0}]},"shadow":{"mode":"contact","baked":False},"states":[{"id":"closed"},{"id":"open"}],"collision":{"shape":"box","offset":{"x":0,"y":0},"size":{"width":2,"depth":1}},"interaction":{"point":{"x":.5,"y":.5},"radius":1}}

def test_red_runtime_deterministic_qa_and_precedence():
    src='\n'.join(fn(x) for x in ('validateObjectPreviewBudget','analyzeObjectPlacement','buildObjectPlacementModel'))
    script=f"""{src}
const b={json.dumps(BASE)}; const image={{width:8,height:8,data:new Uint8ClampedArray(256)}};
for(let y=1;y<8;y++)for(let x=2;x<7;x++)image.data[(y*8+x)*4+3]=255;
const cases={{pass:b,foot:{{...b,scale:{{...b.scale,footprint:{{width:1,depth:1}}}}}},float:{{...b,placement:{{...b.placement,ground_point:{{x:.5,y:.5}},pivot:{{x:.5,y:.5}}}}}},pivot:{{...b,placement:{{...b.placement,pivot:{{x:0,y:0}}}}}},collision:{{...b,collision:{{...b.collision,offset:{{x:4,y:0}}}}}}}};
const out=Object.fromEntries(Object.entries(cases).map(([k,v])=>[k,analyzeObjectPlacement(image,v)]));
const states=[{{id:'closed',imageData:image,canvas:{{width:8,height:8}},pivot:{{x:.5,y:1}}}},{{id:'open',imageData:image,canvas:{{width:9,height:8}},pivot:{{x:.5,y:1}}}}];
out.drift=analyzeObjectPlacement(image,b,states); out.model=buildObjectPlacementModel(image,b,'result',states,'soft'); out.again=buildObjectPlacementModel(image,b,'result',states,'soft');process.stdout.write(JSON.stringify(out));"""
    r=run(script)
    assert r['pass']['status']=='PASS'
    assert 'wrong-footprint' in r['foot']['reasons']
    assert r['float']['reasons']==['floating-ground']
    assert 'pivot-mismatch' in r['pivot']['reasons']
    assert 'collision-out-of-bounds' in r['collision']['reasons'] and r['collision']['status']=='FAIL'
    assert 'state-size-drift' in r['drift']['reasons']
    assert r['model']==r['again'] and r['model']['grid']['tileSize']>0
    assert r['model']['overlays']==['pivot','ground','y-sort','snap','collision','interaction']

def test_opaque_bbox_change_alone_is_not_state_drift_and_budget_preflight():
    src='\n'.join(fn(x) for x in ('validateObjectPreviewBudget','analyzeObjectPlacement'))
    script=f"""{src}\nconst b={json.dumps(BASE)};const mk=(x)=>{{const q={{width:8,height:8,data:new Uint8ClampedArray(256)}};q.data[(8+x)*4+3]=255;return q}};let reads=0;const hostile={{width:99999,height:99999,get data(){{reads++;throw Error('read')}}}};let error='';try{{analyzeObjectPlacement(hostile,b)}}catch(e){{error=e.message}}const q=mk(1);const qa=analyzeObjectPlacement(q,b,[{{id:'a',imageData:q,canvas:{{width:8,height:8}},pivot:{{x:.5,y:1}}}},{{id:'b',imageData:mk(6),canvas:{{width:8,height:8}},pivot:{{x:.5,y:1}}}}]);process.stdout.write(JSON.stringify({{qa,reads,error}}));"""
    r=run(script); assert 'state-size-drift' not in r['qa']['reasons']; assert r['reads']==0; assert r['error'].startswith('object preview budget:')

def test_accessible_object_only_source_result_state_shadow_wiring():
    assert 'id="objectPlacementPreviewPanel"' in HTML and 'aria-label="오브젝트 배치 미리보기 및 QA"' in HTML
    for control in ('objectPreviewSource','objectPreviewState','objectPreviewShadow','buildObjectPlacementPreview','objectPlacementPreviewCanvas','objectPlacementQaSummary'): assert f'id="{control}"' in HTML
    assert "$('objectPlacementPreviewPanel')?.classList.toggle('hidden', family !== 'object')" in JS
    source=fn('buildObjectPlacementPreview')
    assert 'canvas.getActiveObject()' in source and 'object?._element' in source
    assert 'object.objectFamilyMetadata' in source and 'family_contract' in source
    assert 'buildObjectContract()' not in source # no flat/control fallback
    assert source.index('validateObjectPreviewBudget') < source.index("document.createElement('canvas')") < source.index('getImageData')

def test_preview_functions_are_read_only_and_no_provider_export_history_fabric_mutation():
    source=''.join(fn(x) for x in ('analyzeObjectPlacement','buildObjectPlacementModel','buildObjectPlacementPreview'))
    forbidden=('saveHistory','history.','fetch(','download','export','toDataURL','toBlob','canvas.add','canvas.remove','setActiveObject','requestRenderAll')
    assert not [x for x in forbidden if x.lower() in source.lower()]
    assert '.object-placement-qa-summary' in CSS and 'overflow-wrap: anywhere' in CSS

def test_renderer_executes_scaled_pivot_geometry_overlays_shadow_and_icon_derivative():
    src='\n'.join(fn(x) for x in ('validateObjectPreviewBudget','analyzeObjectPlacement','buildObjectPlacementModel','renderObjectPlacement'))
    script=f"""{src}\nconst b={json.dumps(BASE)},im={{width:8,height:8,data:new Uint8ClampedArray(256)}};
const calls=[];const ctx=new Proxy({{canvas:{{width:512,height:384}},measureText:()=>({{width:4}})}},{{get:(o,k)=>k in o?o[k]:(...a)=>calls.push([k,...a]),set:(o,k,v)=>(calls.push(['set',k,v]),o[k]=v,true)}});
const world=buildObjectPlacementModel(im,b,'result',[], 'soft','world');renderObjectPlacement(ctx,{{tag:'image'}},world,b);
const icon=buildObjectPlacementModel(im,{{...b,usage:'icon'}},'result',[],'none','icon','crop');renderObjectPlacement(ctx,{{tag:'image'}},icon,{{...b,usage:'icon'}});
process.stdout.write(JSON.stringify({{world,icon,calls}}));"""
    r=run(script); w=r['world']; calls=r['calls']
    assert w['object']['drawWidth']==64 and w['object']['drawHeight']==48
    assert w['object']['origin']['x']==w['object']['ground']['x']-32
    assert w['object']['origin']['y']==w['object']['ground']['y']-48
    names=[x[0] for x in calls]
    assert names.count('drawImage')>=2 and 'ellipse' in names and 'arc' in names
    assert 'strokeRect' in names and 'setLineDash' in names
    assert r['icon']['icon']['mode']=='crop' and r['icon']['icon']['frame']['width']==128
    assert r['icon']['object']['drawWidth']!=w['object']['drawWidth']

def test_states_are_result_honest_auto_populated_and_controls_rerender():
    source=fn('buildObjectPlacementPreview')
    assert 'replaceChildren' in source and 'requested-only' in source and 'dataset.status' in source
    assert 'objectPreviewState' in source and 'state?.image' in source
    for control in ('objectPreviewSource','objectPreviewState','objectPreviewShadow','objectPreviewUsage','objectPreviewIconMode'):
        assert re.search(rf"\$\('{control}'\).*onchange",JS)
    assert 'id="objectPreviewUsage"' in HTML and 'id="objectPreviewIconMode"' in HTML

def test_contract_is_fail_closed_bounded_and_preserves_zero_coordinates():
    src='\n'.join(fn(x) for x in ('normalizeObjectPreviewContract','validateObjectPreviewBudget'))
    script=f"""{src}\nconst b={json.dumps(BASE)};const ok=normalizeObjectPreviewContract(b);const bad=[];
for(const mutate of [c=>c.placement.pivot.x=NaN,c=>c.scale.tile_relative.width=0,c=>c.interaction.radius=Infinity,c=>c.collision.shape='circle',c=>c.collision={{shape:'polygon',offset:{{x:0,y:0}},points:[{{x:0,y:0}},{{x:1,y:1}}]}},c=>c.collision={{shape:'polygon',offset:{{x:0,y:0}},points:[{{x:0,y:0}},{{x:1,y:1}},{{x:2,y:2}}]}}]){{const c=structuredClone(b);mutate(c);try{{normalizeObjectPreviewContract(c);bad.push('accepted')}}catch(e){{bad.push(e.message)}}}}
process.stdout.write(JSON.stringify({{ok,bad}}));"""
    r=run(script); assert r['ok']['placement']['snap_points'][0]['x']==0
    assert all(x.startswith('object preview contract:') for x in r['bad'])

def test_polygon_rejects_zero_length_edges_and_self_intersection_but_accepts_simple_shapes():
    src=fn('normalizeObjectPreviewContract')
    polygons={
        'consecutive_duplicate': [{'x':0,'y':0},{'x':2,'y':0},{'x':2,'y':0},{'x':2,'y':2},{'x':0,'y':2}],
        'closing_duplicate': [{'x':0,'y':0},{'x':2,'y':0},{'x':2,'y':2},{'x':0,'y':2},{'x':0,'y':0}],
        # Crossing edges with non-zero shoelace area, so area-only validation cannot reject it.
        'bow_tie': [{'x':0,'y':0},{'x':3,'y':3},{'x':0,'y':3},{'x':2,'y':0}],
        'convex': [{'x':0,'y':0},{'x':2,'y':0},{'x':2,'y':2},{'x':0,'y':2}],
        'concave': [{'x':0,'y':0},{'x':3,'y':0},{'x':1.5,'y':1},{'x':3,'y':3},{'x':0,'y':3}],
    }
    script=f"""{src}\nconst b={json.dumps(BASE)},polygons={json.dumps(polygons)},out={{}};
for(const [name,points] of Object.entries(polygons)){{const c=structuredClone(b);c.collision={{shape:'polygon',offset:{{x:0,y:0}},points}};try{{normalizeObjectPreviewContract(c);out[name]='accepted'}}catch(e){{out[name]=e.message}}}}process.stdout.write(JSON.stringify(out));"""
    r=run(script)
    for name in ('consecutive_duplicate','closing_duplicate','bow_tie'):
        assert r[name].startswith('object preview contract:'), (name,r[name])
    assert r['convex']=='accepted' and r['concave']=='accepted'

def test_polygon_full_bounds_alpha_scan_and_structural_budgets():
    src='\n'.join(fn(x) for x in ('normalizeObjectPreviewContract','validateObjectPreviewBudget','analyzeObjectPlacement'))
    poly={**BASE,"collision":{"shape":"polygon","offset":{"x":0,"y":0},"points":[{"x":-2,"y":0},{"x":0,"y":.4},{"x":0,"y":-.4}]}}
    script=f"""{src}\nconst c={json.dumps(poly)},im={{width:8,height:8,data:new Uint8ClampedArray(256)}};im.data[(7*8+4)*4+3]=255;let reads=0;const data=new Proxy(im.data,{{get:(o,k)=>{{if(k==='length')return o.length;if(!isNaN(k))reads++;return o[k]}}}});const qa=analyzeObjectPlacement({{width:8,height:8,data}},c);let budget='';try{{const b={json.dumps(BASE)};b.placement.snap_points=Array(300).fill({{id:'x',x:0,y:0}});normalizeObjectPreviewContract(b)}}catch(e){{budget=e.message}}process.stdout.write(JSON.stringify({{qa,reads,budget}}));"""
    r=run(script); assert 'collision-out-of-bounds' in r['qa']['reasons']; assert r['reads']<=64
    assert r['budget'].startswith('object preview contract:')

def test_display_image_is_selected_before_qa_read_and_dom_mutation_is_bounded():
    source=fn('buildObjectPlacementPreview')
    assert source.index('state?.image') < source.index('getImageData')
    assert source.index('validateObjectPreviewBudget') < source.index('replaceChildren')
    assert 'replaceChildren(...' not in source and '.appendChild(option)' in source
