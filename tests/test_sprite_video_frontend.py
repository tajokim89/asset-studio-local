"""Local sprite-video frontend: no network generation or cloud requests."""
from pathlib import Path
import subprocess
import shutil

ROOT = Path(__file__).resolve().parents[1]


def test_sprite_prompt_forwarding_and_generation_gates():
    script = r'''
const vm=require('node:vm'), fs=require('node:fs'), assert=require('node:assert/strict');
const ids={};
function element(id){return ids[id] ||= {value:'',listeners:{},hidden:false,addEventListener(e,cb){this.listeners[e]=cb},removeAttribute(){},closest(){return {textContent:id}},focus(){},close(){},showModal(){}}}
Object.assign(element('spriteVideoModel'),{value:'h3_fast'});
Object.assign(element('providerStatus'),{dataset:{state:'ready',referenceImages:'true'}});
for(const [id,value] of Object.entries({spriteVideoDuration:2,spriteVideoFrames:25,spriteVideoFps:12,spriteVideoName:'walk_SW',spriteVideoBackground:'#00ff00'}))element(id).value=String(value);
let selected=null, family='sprite'; const selectionHandlers={};
const context={console, document:{getElementById:element,querySelector(){return {click(){}}}}, canvas:{getActiveObject:()=>selected,on:(event,callback)=>{selectionHandlers[event]=callback}},currentAssetFamily:()=>family,nameOf:object=>object.name || 'source',imageObjectToDataUrl:object=>object.bytes,assetGenerationInFlight:null,window:{},fetch:async()=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>({available:true,models:[{id:'h3_fast',available:true},{id:'h3',available:false}]})})};
vm.runInNewContext(fs.readFileSync('src/sprite-video.js','utf8'),context);
(async()=>{
await new Promise(resolve=>setImmediate(resolve));
const api=context.window.SpriteVideo;
assert.equal(element('familyGenerateAi').disabled,true);
element('assetCorePrompt').value='  final prompt\n[0s-2s] Walk.  ';
api.updateGenerateAvailability(); assert.equal(element('familyGenerateAi').disabled,true);
selected={type:'image'};api.updateGenerateAvailability();assert.equal(element('familyGenerateAi').disabled,false);
let payload=api.buildRequest(element('assetCorePrompt').value,'data:image/png;base64,ORIGINAL');
assert.equal(payload.prompt,'  final prompt\n[0s-2s] Walk.  ');
assert.equal(payload.reference_image,'data:image/png;base64,ORIGINAL');
assert.equal(payload.frame_count,25);assert.equal(payload.fps,12);
assert.equal('style_profile' in payload,false);assert.equal('sprite' in payload,false);
element('spriteVideoDuration').value='6';assert.equal(api.buildRequest('prompt','data:image/png;base64,X').duration,6);
element('spriteVideoDuration').value='7';assert.throws(()=>api.buildRequest('prompt','data:image/png;base64,X'),/1~6/);
element('spriteWizardApply').listeners.click();assert.match(element('spriteWizardError').textContent,/1~6/);
element('spriteVideoDuration').value='2';element('spriteWizardApply').listeners.click();assert.ok(element('spriteWizardError').textContent.length > 0);
element('spriteVideoModel').value='h3';api.updateGenerateAvailability();assert.equal(element('familyGenerateAi').disabled,true);
assert.throws(()=>api.buildRequest('prompt','data:image/png;base64,X'),/H3/);
element('spriteVideoModel').value='h3_fast';element('spriteVideoFrames').value='1.5';assert.throws(()=>api.buildRequest('prompt','data:image/png;base64,X'));
element('spriteWizardSubject').value='내가 작성한 오크 설명';
element('spriteWizardBeats').value='';
const framesBeforeExample=element('spriteVideoFrames').value;
element('spriteWizardAction').value='walk';element('spriteWizardExampleApply').listeners.click();
assert.match(element('spriteWizardBeats').value,/오른발/);
assert.equal(element('spriteWizardSubject').value,'내가 작성한 오크 설명');
const walkExample=element('spriteWizardBeats').value;
context.window.confirm=()=>false;
element('spriteWizardAction').value='idle';element('spriteWizardExampleApply').listeners.click();assert.equal(element('spriteWizardBeats').value,walkExample);
context.window.confirm=()=>true;
element('spriteWizardAction').value='idle';element('spriteWizardExampleApply').listeners.click();assert.match(element('spriteWizardBeats').value,/숨을/);
assert.equal(element('spriteWizardLoop').checked,true);
assert.equal(element('spriteVideoFrames').value,framesBeforeExample);
for(const [kind,pattern,loop] of [['run',/달린다/,true],['jump',/착지/,false],['attack',/벤다/,false]]) {
 element('spriteWizardAction').value=kind;element('spriteWizardExampleApply').listeners.click();
 assert.match(element('spriteWizardBeats').value,pattern);assert.equal(element('spriteWizardLoop').checked,loop);
 assert.equal(element('spriteWizardBeats').value.split('\n').length,4);
 assert.equal(element('spriteWizardSubject').value,'내가 작성한 오크 설명');
 assert.equal(element('spriteVideoFrames').value,framesBeforeExample);
}
assert.match(element('spriteWizardBeats').value,/새 무기나 장비를 만들지/);
element('spriteWizardAction').value='unknown';const previousBeats=element('spriteWizardBeats').value;
element('spriteWizardExampleApply').listeners.click();assert.equal(element('spriteWizardBeats').value,previousBeats);
const shieldAttack=api.buildAttackExample('shield','slash');
assert.match(shieldAttack,/몸통보다 약간 뒤로 당긴다/);assert.match(shieldAttack,/한 번 벤다/);assert.doesNotMatch(shieldAttack,/주먹|시위를|석궁/);
for(const type of ['slash','thrust','smash','custom']) {
 const phases=api.buildAttackExample('shield',type,'right','한 번 위로 벤다').split('\n');
 assert.match(phases[0],/방패를 든 팔은 팔꿈치를 굽혀/);
 assert.match(phases[1],/무기를 든 팔만 앞으로 공격/);
 assert.match(phases[2],/방패 팔은 접은 채/);
 assert.match(phases[3],/거둔 다음에만 방패 팔/);
}
assert.doesNotMatch(api.buildAttackExample('shield','shield_bash'),/무기를 든 팔만 앞으로 공격|방패 팔은 접은 채/);
const unarmed=api.buildAttackExample('unarmed','punch','left');assert.match(unarmed,/왼손/);assert.match(unarmed,/주먹/);
const twohand=api.buildAttackExample('twohand','smash');assert.match(twohand,/두 손은 같은 무기/);assert.match(twohand,/내려친다/);
const dual=api.buildAttackExample('dual','thrust','right');assert.match(dual,/서로 다른 두 무기/);assert.match(dual,/오른손/);assert.match(dual,/반대손 무기는 방어/);
assert.match(api.buildAttackExample('twohand','bow'),/시위를 놓아/);
assert.match(api.buildAttackExample('shield','shield_bash'),/방패를 든 팔과 어깨/);
assert.throws(()=>api.buildAttackExample('shield','bow'));
assert.throws(()=>api.buildAttackExample('onehand','custom','right',''));
assert.match(api.buildAttackExample('onehand','custom','right','아래에서 위로 벤다'),/아래에서 위로 벤다/);
for(const [eq,types] of Object.entries({unarmed:['punch'],onehand:['slash','thrust','smash','crossbow'],shield:['slash','thrust','smash','shield_bash'],twohand:['slash','thrust','smash','bow','crossbow'],dual:['slash','thrust','smash']}))for(const type of types)assert.equal(api.buildAttackExample(eq,type).split('\n').length,4);
element('spriteWizardAction').value='attack';element('spriteWizardEquipment').value='twohand';element('spriteWizardAttackType').value='bow';element('spriteWizardEquipment').listeners.change();
element('spriteWizardEquipment').value='shield';element('spriteWizardEquipment').listeners.change();assert.equal(element('spriteWizardAttackType').value,'slash');assert.equal(element('spriteWizardAttackControls').hidden,false);
element('spriteWizardAction').value='walk';element('spriteWizardAction').listeners.change();assert.equal(element('spriteWizardAttackControls').hidden,true);
const koreanPrompt=api.composePrompt({subject:'오크',style:'도트',background:'초록',camera:'고정',beats:walkExample,duration:2,loop:true});
assert.ok(koreanPrompt.includes('[0s-0.5s]'));assert.ok(koreanPrompt.includes('[1.5s-2s]'));assert.ok(koreanPrompt.includes('오른발'));
family='image';selected=null;api.syncFamily();assert.equal(element('familyGenerateAi').disabled,false);assert.equal(element('spriteVideoControls').hidden,true);
element('providerStatus').dataset.state='unavailable';api.updateGenerateAvailability();assert.equal(element('familyGenerateAi').disabled,true);
element('providerStatus').dataset.state='ready';context.assetGenerationInFlight={};api.updateGenerateAvailability();assert.equal(element('familyGenerateAi').disabled,true);
context.assetGenerationInFlight=null;
const sourceA={type:'image',id:'a',name:'A',bytes:'data:image/png;base64,FULL_A',getSrc:()=>'/a.png',getElement:()=>({naturalWidth:730,naturalHeight:411})};
const sourceB={type:'image',id:'b',name:'B',bytes:'data:image/png;base64,FULL_B',getSrc:()=>'/b.png',getElement:()=>({naturalWidth:512,naturalHeight:512})};
selected=sourceA;selectionHandlers['selection:updated']();assert.equal(api.getImageReference(),null);
element('imageReferencePin').listeners.click();assert.equal(element('familyGenerateAi').disabled,false);delete element('providerStatus').dataset.referenceImages;api.updateGenerateAvailability();assert.equal(element('familyGenerateAi').disabled,true);assert.match(element('primaryGenerationHint').textContent,/서버를 다시 시작/);element('providerStatus').dataset.referenceImages='true';api.updateGenerateAvailability();assert.equal(element('familyGenerateAi').disabled,false);assert.equal(api.getImageReference().image,sourceA.bytes);assert.equal(api.getImageReference().name,'A');
sourceA.bytes='data:image/png;base64,EDITED_A';selected=sourceB;selectionHandlers['selection:updated']();
assert.equal(api.getImageReference().image,'data:image/png;base64,FULL_A');assert.equal(element('imageReferenceName').textContent,'고정 기준 · A');
family='ui';api.syncFamily();family='image';api.syncFamily();assert.equal(api.getImageReference().name,'A');
selected=null;selectionHandlers['selection:cleared']();assert.equal(api.getImageReference().image,'data:image/png;base64,FULL_A');
const copy=api.getImageReference();copy.image='CHANGED';assert.equal(api.getImageReference().image,'data:image/png;base64,FULL_A');
selected=sourceB;element('imageReferencePin').listeners.click();assert.equal(api.getImageReference().image,sourceB.bytes);
selected={...sourceA,isMaskOverlay:true};element('imageReferencePin').listeners.click();assert.equal(api.getImageReference().image,sourceB.bytes);
element('imageReferenceClear').listeners.click();assert.equal(api.getImageReference(),null);assert.equal(element('imageReferencePreview').hidden,true);
const prompt=api.composePrompt({subject:'Orc',style:'Pixel art',background:'Green',camera:'Fixed',beats:'Step left\nStep right',duration:2,loop:true});
assert.ok(prompt.includes('[0s-1s] Step left'));assert.ok(prompt.includes('[1s-2s] Step right'));assert.ok(prompt.includes('non_diegetic_music: None.'));
console.log('sprite prompt and gates passed');
})().catch(err=>{console.error(err);process.exitCode=1});
'''
    result = subprocess.run([shutil.which('node'), '-e', script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_primary_generation_snapshots_source_and_does_not_expand_user_prompt():
    source = (ROOT / 'src/main.js').read_text(encoding='utf-8')
    body = source.split('function generateAiAsset() {', 1)[1].split('function setFrontIdleGridForImage', 1)[0]
    assert "const prompt = $('assetCorePrompt').value;" in body
    assert 'canvas.getActiveObject()' in body
    assert 'imageObjectToDataUrl(referenceObj)' in body
    assert body.index('imageObjectToDataUrl(referenceObj)') < body.index('submitGenerationJob')
    assert "'/api/sprite-video'" in body
    assert "prompt_mode:'direct'" in body
    assert "timeoutMs:(family === 'sprite' ? 31 : 15) * 60 * 1000" in body
    for forbidden in ['generateActorWalk(', 'buildAssetGenerationPayload(', 'buildPixelAssetPrompt(', 'isRecipeRegistryReady(', 'selectedLayerObject(']:
        assert forbidden not in body


def test_removed_integrations_and_hidden_legacy_controls():
    html=(ROOT / 'index.html').read_text(encoding='utf-8')
    for obsolete in ['data-studio-workspace="motion"', 'data-studio-workspace="pipeline"', 'data-asset-family="tile"', 'src/motion-studio', 'src/pixel-pipeline', 'type="importmap"']:
        assert obsolete not in html
    assert 'id="legacyGenerationControls" hidden aria-hidden="true"' in html
    assert 'id="spriteVideoExecution" class="asset-options-disclosure"' in html
    assert html.index('id="familyGenerateAi"') < html.index('id="spriteVideoExecution"')


def test_result_preview_slices_multirow_video_sheet_without_empty_cells():
    source=(ROOT / 'src/main.js').read_text(encoding='utf-8')
    function='function deriveSpriteFrameRectangles'+source.split('function deriveSpriteFrameRectangles',1)[1].split('function deriveWalkBeatLabels',1)[0]
    script='const assert=require("node:assert/strict"); const RESULT_SPRITE_LIMITS={maxPixels:33554432,maxWorkingBytes:268435456};\n'+function+'''
const rects=deriveSpriteFrameRectangles({frameCount:8,columns:3,rows:3},{width:192,height:192});
assert.equal(rects.length,8);
assert.equal(deriveSpriteFrameRectangles({frameCount:25,columns:5,rows:5},{width:2240,height:2240})[24].width,448);
assert.throws(()=>deriveSpriteFrameRectangles({frameCount:25,columns:5,rows:5},{width:32765,height:32765}));
assert.throws(()=>deriveSpriteFrameRectangles({frameCount:4,columns:4,rows:1},{width:128,height:128}));
assert.deepEqual(rects[7],{index:7,x:64,y:128,width:64,height:64});
assert.throws(()=>deriveSpriteFrameRectangles({frameCount:10,columns:3,rows:3},{width:192,height:192}));
'''
    result=subprocess.run([shutil.which('node'),'-e',script],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_video_result_direction_preserves_source_instead_of_guessing_south():
    source=(ROOT / 'src/main.js').read_text(encoding='utf-8')
    function='function deriveResultSpriteAnimation'+source.split('function deriveResultSpriteAnimation',1)[1].split('function deriveSpriteFrameRectangles',1)[0]
    script='const assert=require("node:assert/strict"); const RESULT_SPRITE_LIMITS={maxFrames:256};\n'+function+"\nconst result=deriveResultSpriteAnimation({status:'succeeded',family:'sprite',type:'character',preview:{url:'/sheet.png'},normalizedContract:{engine:'sprite-video',sprite:{frame_count:25,columns:5,rows:5,fps:12,animation_mode:'walk_SW'}}});assert.equal(result.direction,'SOURCE');"
    result=subprocess.run([shutil.which('node'),'-e',script],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_selection_ai_tools_are_grouped_and_closed():
    html=(ROOT / 'index.html').read_text(encoding='utf-8')
    opening='<details id="selectionAiTools" class="asset-options-disclosure">'
    assert opening in html
    group=html.split(opening,1)[1].split('<div id="layersPanel"',1)[0]
    for control in ['aiChatInput','aiEditPanel','replaceObjectPrompt','inpaintPrompt']:
        assert f'id="{control}"' in group


def test_general_image_preserves_native_pixels_alpha_and_exact_prompt(tmp_path):
    from PIL import Image
    from unittest import mock
    import json
    import server
    from tests.helpers.http_generation_harness import GenerationHttpHarness
    from tests.helpers.fake_image_provider import FakeImageProvider

    native = tmp_path / 'native.png'
    Image.new('RGBA', (730, 411), (91, 23, 201, 127)).save(native)
    provider = FakeImageProvider(tmp_path / 'provider')
    harness = GenerationHttpHarness(provider, tmp_path / 'generated')
    with mock.patch.object(provider, 'generate', return_value={'success':True,'image':str(native)}) as generate:
        result = harness.post_json('/api/generate', {'prompt_mode':'direct','asset_family':'image','asset_type':'image','prompt':'  Full color painting\n no forced pixel style  '})
    assert result.status == 200, result.json()
    assert generate.call_args.args[0] == '  Full color painting\n no forced pixel style  '
    data=result.json()
    assert (data['width'],data['height']) == (730,411)
    assert data['asset_family'] == 'image' and data['asset_type'] == 'image'
    output=tmp_path / 'generated' / data['url'].rsplit('/',1)[1]
    with Image.open(output) as image:
        assert image.size == (730,411)
        assert image.getpixel((0,0)) == (91,23,201,127)
    assert json.loads(output.with_suffix('.png.json').read_text(encoding='utf-8'))['output']['width'] == 730


def test_general_image_tab_and_active_frame_defaults_are_explicit():
    from html.parser import HTMLParser
    class Controls(HTMLParser):
        def __init__(self): super().__init__(); self.ids={}; self.families=[]
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            if 'id' in attrs: self.ids[attrs['id']]=attrs
            if 'data-asset-family' in attrs:self.families.append(attrs['data-asset-family'])
    parser=Controls();parser.feed((ROOT/'index.html').read_text(encoding='utf-8'))
    assert parser.families==['image','sprite','ui','object']
    assert parser.ids['assetFamilyTab-image']['aria-selected']=='true'
    assert parser.ids['spriteVideoFrames']['value']=='25'
    assert parser.ids['spriteVideoFrames']['max']=='64'
    assert parser.ids['animFrameCount']['value']=='25'
    assert parser.ids['gridCols']['value']=='5' and parser.ids['gridRows']['value']=='5'
    source=(ROOT/'src/main.js').read_text(encoding='utf-8')
    assert "let selectedAssetFamily = 'image';" in source
    assert "if (!$('legacyGenerationControls')?.hidden) applyPixelWorkflowGridDefaults();" in source
    adoption=source.split('async function adoptResult(',1)[1].split('function compactAssetResultPayload',1)[0]
    assert 'canvas.setActiveObject(img)' in adoption
    assert "family:'image'" not in adoption  # Generic adoption does not relabel image results.


def test_image_generation_result_can_be_selected_as_next_sprite_source():
    source=(ROOT/'src/main.js').read_text(encoding='utf-8')
    generate='function generateAiAsset() {'+source.split('function generateAiAsset() {',1)[1].split('function setFrontIdleGridForImage',1)[0]
    create='function createAssetResult'+source.split('function createAssetResult',1)[1].split('function transitionAssetResult',1)[0]
    script=r'''
const assert=require('node:assert/strict');
let family='image',active=null,assetGenerationInFlight=null,calls=[],adopted=[],reference=null;
const controls={assetCorePrompt:{value:'  painted source\n'},familyGenerateAi:{disabled:false},providerStatus:{dataset:{referenceImages:'true'}}};
const $=id=>controls[id],currentAssetFamily=()=>family,currentAssetSubtype=()=>family==='image'?'image':'character';
const canvas={getActiveObject:()=>active};
const imageObjectToDataUrl=object=>{assert.equal(object.url,'/generated.png');return 'data:image/png;base64,SNAPSHOT'};
const window={SpriteVideo:{getImageReference:()=>reference,buildRequest:(prompt,reference_image)=>({prompt,reference_image,fps:12,name:'walk',frame_count:25}),showResult(){},updateGenerateAvailability(){}}};
const beginGenerationProgress=()=>{},finishGenerationProgress=()=>{},setStatus=()=>{};
const submitGenerationJob=async(endpoint,payload)=>{calls.push({endpoint,payload});return {job_id:'job'}};
const waitForGenerationJob=async()=>({success:true,url:'/generated.png',frame_count:25,columns:5,rows:5});
const assetResultFromGeneration=(payload,data)=>({id:'r',payload,data});
const assetResultStore={add(){},select(){}};
const adoptResult=async(id,mode)=>{adopted.push(mode);active={type:'image',url:'/generated.png'}};
'''+generate+create+r'''
(async()=>{
await generateAiAsset();
assert.equal(calls[0].endpoint,'/api/generate');
assert.deepEqual(calls[0].payload,{prompt:'  painted source\n',prompt_mode:'direct',asset_family:'image',asset_type:'image'});
assert.equal(adopted[0],'new-layer');
reference={image:'data:image/png;base64,PIN_A',layer_id:'A',name:'pinned A',width:730,height:411,captured_at:'2026-10-01T00:00:00.000Z'};
active={type:'image',url:'/different-selection.png'};delete controls.providerStatus.dataset.referenceImages;await assert.rejects(generateAiAsset(),/서버를 다시 시작/);assert.equal(calls.length,1);controls.providerStatus.dataset.referenceImages='true';const pinned=await generateAiAsset();
assert.equal(calls[1].payload.reference_image,reference.image);assert.equal(pinned.result.payload.reference_source.name,'pinned A');assert.equal(adopted[1],'new-layer');
reference=null;family='sprite';await generateAiAsset();
assert.equal(calls[2].endpoint,'/api/sprite-video');assert.equal(calls[2].payload.reference_image,'data:image/png;base64,SNAPSHOT');
const request={asset_family:'image',asset_type:'image',prompt:'free'};
const result=createAssetResult({family:'image',type:'image',status:'succeeded',preview:{url:'/generated.png'},sourceRequest:request,normalizedContract:request});
assert.equal(result.family,'image');assert.equal(result.type,'image');
})().catch(error=>{console.error(error);process.exitCode=1});
'''
    run=subprocess.run([shutil.which('node'),'-e',script],cwd=ROOT,capture_output=True,text=True)
    assert run.returncode==0,run.stdout+run.stderr
