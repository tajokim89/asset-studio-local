"""Result-card sprite animation and conservative walk QA behavior tests."""
import json, re, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JS_PATH=ROOT/'src/main.js'

def decl(source,name):
    m=re.search(rf'function\s+{name}\s*\(',source); assert m, f'missing {name}'
    opening=source.index('{',source.index(')',m.end()))
    depth=0; quote=None; esc=False
    for i in range(opening,len(source)):
        c=source[i]
        if quote:
            if esc: esc=False
            elif c=='\\': esc=True
            elif c==quote: quote=None
        elif c in "'\"`": quote=c
        elif c=='{': depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return source[m.start():i+1]
    raise AssertionError('unclosed')

def runtime():
    source=JS_PATH.read_text()
    names=['deriveResultSpriteAnimation','deriveSpriteFrameRectangles','deriveWalkBeatLabels','detectRepeatedAnimationFrames','resultWalkQaGate']
    code="const RESULT_SPRITE_LIMITS={maxPixels:33554432,maxWorkingBytes:268435456,maxFrames:256};\n"+'\n'.join(decl(source,n) for n in names)
    script=code+r'''
const result={family:'sprite',type:'character',status:'succeeded',preview:{url:'/walk.png'},artifacts:[],sourceRequest:{asset_family:'sprite',asset_type:'character',sprite:{animation_mode:'walk',frame_count:4,target_direction:'SW'}},normalizedContract:{asset_family:'sprite',asset_type:'character',sprite:{animation_mode:'walk',frame_count:4,target_direction:'SW'}}};
const capture=f=>{try{return {ok:true,value:f()}}catch(e){return {ok:false,message:e.message}}};
const desc=deriveResultSpriteAnimation(result);
const rects=deriveSpriteFrameRectangles(desc,{width:128,height:32});
const repeated=detectRepeatedAnimationFrames([new Uint8Array([0,0,0,255]),new Uint8Array([0,0,0,255]),new Uint8Array([1,0,0,255]),new Uint8Array([1,0,0,255])]);
const moving=detectRepeatedAnimationFrames([new Uint8Array([0,0,0,255]),new Uint8Array([255,0,0,255]),new Uint8Array([0,255,0,255]),new Uint8Array([0,0,255,255])]);
console.log(JSON.stringify({desc,rects,beats4:deriveWalkBeatLabels('walk',4),beats6:deriveWalkBeatLabels('walk',6),repeated,moving,badGrid:capture(()=>deriveSpriteFrameRectangles(desc,{width:127,height:32})),implausibleStrip:capture(()=>deriveSpriteFrameRectangles(desc,{width:128,height:128})),budget:capture(()=>deriveSpriteFrameRectangles(desc,{width:32768,height:32768})),gateFail:resultWalkQaGate(desc,{status:'FAIL'},true),gatePending:resultWalkQaGate(desc,{status:'PASS'},false),gatePass:resultWalkQaGate(desc,{status:'PASS'},true)}));
'''
    cp=subprocess.run(['node','-e',script],cwd=ROOT,text=True,capture_output=True)
    assert cp.returncode==0,cp.stderr
    return json.loads(cp.stdout)

def test_pure_descriptor_rectangles_and_fail_closed_budgets():
    out=runtime(); d=out['desc']
    assert d['url']=='/walk.png' and d['frameCount']==4 and d['direction']=='SW' and d['autoPlay'] is True
    assert [r['x'] for r in out['rects']]==[0,32,64,96]
    assert out['badGrid']['ok'] is False and out['implausibleStrip']['ok'] is False and out['budget']['ok'] is False

def test_walk_labels_are_semantically_exact_only_for_canonical_four_frame_walk():
    out=runtime()
    assert out['beats4']==[{'label':'N','semantic':True},{'label':'L','semantic':True},{'label':'N','semantic':True},{'label':'R','semantic':True}]
    assert [x['label'] for x in out['beats6']]==['N','L','N','R','N','L']
    assert all(x['semantic'] is False for x in out['beats6'])
def test_deterministic_repeat_failure_is_the_only_walk_adoption_gate():
    out=runtime()
    assert out['repeated']['status']=='FAIL' and out['moving']['status']=='PASS'
    assert out['gateFail']['allowed'] is False and out['gatePending']['allowed'] is True and out['gatePass']['allowed'] is True


def test_result_card_has_inline_controls_cleanup_and_safe_static_fallback():
    source=JS_PATH.read_text(); render=decl(source,'renderAssetResultTray')+decl(source,'mountResultSpritePlayer')
    for token in ('result-sprite-animation','play-pause','previous-frame','next-frame','animation-fps','정적 이미지로 표시'):
        assert token in render
    assert 'manual-walk-pass' not in render
    for token in ('visibilitychange','clearInterval','imageSmoothingEnabled'):
        assert token in source
    adopt=decl(source,'adoptResult')
    assert 'resultWalkQaGate' not in adopt

def test_single_direction_walk_prompt_has_four_explicit_beats_and_translation_lock():
    source=JS_PATH.read_text()
    assert "recipe.beats.join(',') !== 'N,L,N,R'" in source
    for phrase in ('root_foot_lock', 'silhouette_lock'):
        assert phrase in source.lower()
