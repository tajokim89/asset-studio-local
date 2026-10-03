from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def test_generated_artifact_survives_canvas_download_failure():
    source=(ROOT/'src/main.js').read_text(encoding='utf-8')
    fn='function generateAiAsset() {'+source.split('function generateAiAsset() {',1)[1].split('function setFrontIdleGridForImage',1)[0]
    setup=r"""
const assert=require('node:assert/strict');let assetGenerationInFlight=null, calls=0, stored=[], completion, shown=false;
const elements={assetCorePrompt:{value:'walk'},familyGenerateAi:{disabled:false}};
const $=id=>elements[id],currentAssetFamily=()=> 'sprite', currentAssetSubtype=()=> 'character';
const canvas={getActiveObject:()=>({type:'image'})}, imageObjectToDataUrl=()=> 'data:image/png;base64,abc';
const window={SpriteVideo:{buildRequest:()=>({fps:12,name:'walk'}),showResult:()=>{shown=true},updateGenerateAvailability(){}}};
const beginGenerationProgress=()=>{},setStatus=()=>{},finishGenerationProgress=(ok,text)=>{completion={ok,text}};
const submitGenerationJob=async()=>{calls++;return {job_id:'one'}};
const waitForGenerationJob=async()=>({success:true,url:'/saved.png',frame_count:25,columns:5,rows:5});
const assetResultFromGeneration=()=>({id:'saved',status:'succeeded'});
const assetResultStore={add:r=>stored.push(r),select:()=>{}};
const adoptResult=async()=>{throw new Error('download timed out')};
"""
    checks=r"""
(async()=>{const r=await generateAiAsset();assert.equal(calls,1);assert.equal(stored.length,1);assert.equal(r.result.status,'succeeded');assert.equal(r.adoptionWarning,'download timed out');assert.equal(completion.ok,true);assert.equal(shown,true)})().catch(e=>{console.error(e);process.exit(1)});
"""
    result=subprocess.run(['node','-e',setup+fn+checks],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr

def test_download_timeout_is_separate_from_decode_and_has_recovery_message():
    source=(ROOT/'src/main.js').read_text(encoding='utf-8')
    fn=source.split('async function preflightResultImage(',1)[1].split('function loadAdoptionFabricImage',1)[0]
    assert 'timeout=limits.timeout || 120000' in fn
    assert fn.index('clearTimeout(timer);') < fn.index('createImageBitmap(blob)')
    assert 'clearTimeout(decodeTimer)' in fn
    assert "error.name==='AbortError'" in fn
    assert '생성된 파일은 결과 탭에 보관돼 있습니다.' in fn
