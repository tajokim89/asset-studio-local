"""D4 browser UI state-package acceptance tests (production JS + independent ZIP/PNG audit)."""
from __future__ import annotations
import base64, io, json, subprocess, textwrap, zipfile
from pathlib import Path
import pytest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT/'src/main.js'; HTML=(ROOT/'index.html').read_text()

def _range(s,a,b):
    start=s.index(a); return s[start:s.index(b,start)]

@pytest.fixture(scope='session')
def driver(tmp_path_factory):
    s=MAIN.read_text()
    extracted=(_range(s,'function effectConcatBytes','const EFFECT_EXPORT_LIMITS')+
               _range(s,'let crc32Table = null;','function exportFull')+
               _range(s,'const UI_NINE_SLICE_BUDGETS','function renderUiNineSliceImageData')+
               _range(s,'const UI_EXPORT_LIMITS','async function selectedUiSourceImageData'))
    p=tmp_path_factory.mktemp('d4')/'driver.js'
    p.write_text(extracted+textwrap.dedent(r'''
      const b64=x=>Buffer.from(x).toString('base64');
      function fixture(layout='horizontal',states=['Normal','hover state','pressed']){
        const sw=3,sh=2,n=states.length,W=layout==='horizontal'?sw*n:sw,H=layout==='vertical'?sh*n:sh;
        const data=new Uint8ClampedArray(W*H*4);
        for(let i=0;i<n;i++)for(let y=0;y<sh;y++)for(let x=0;x<sw;x++){
          const xx=layout==='horizontal'?i*sw+x:x,yy=layout==='vertical'?i*sh+y:y;
          data.set([i*40+x,y+10,200-i,i===1?7:255],(yy*W+xx)*4);
        }
        return {image:{width:W,height:H,data},contract:{source_size:{width:sw,height:sh},slice_margins:{top:1,right:1,bottom:1,left:1},content_safe_area:{top:1,right:2,bottom:3,left:4},padding:{top:5,right:6,bottom:7,left:8},sizing_mode:'nine-slice',edge_mode:'tile',center_mode:'stretch',states,text_free:true}};
      }
      async function main(q){try{
        const f=fixture(q.layout,q.states),a=buildUiExportPackage(f.image,f.contract),b=buildUiExportPackage(f.image,f.contract);
        const ab=new Uint8Array(await a.zipBlob.arrayBuffer()),bb=new Uint8Array(await b.zipBlob.arrayBuffer());
        return {manifest:a.manifest,names:a.files.map(x=>x.name),zip:b64(ab),same:b64(ab)===b64(bb),frames:extractUiStateFrames(f.image,f.contract).map(x=>Array.from(x.data))};
      }catch(e){return {error:e.message}}}
      let z='';process.stdin.on('data',x=>z+=x).on('end',async()=>console.log(JSON.stringify(await main(JSON.parse(z)))));
    '''))
    def run(x):
        cp=subprocess.run(['node',str(p)],input=json.dumps(x),text=True,capture_output=True,check=True)
        return json.loads(cp.stdout)
    return run

def _audit(result):
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(result['zip']))) as z:
        assert z.testzip() is None
        names=z.namelist(); manifest=json.loads(z.read('manifest.json'))
        pixels=[]
        for state in manifest['states']:
            im=Image.open(io.BytesIO(z.read(state['file']))).convert('RGBA'); pixels.append(list(im.tobytes()))
            assert im.size==(3,2)
    return names,manifest,pixels

def test_horizontal_exact_png_manifest_and_independent_roundtrip(driver):
    out=driver({'layout':'horizontal','states':['normal','hover','pressed']}); assert 'error' not in out
    names,m,pixels=_audit(out)
    assert names==['manifest.json','states/normal.png','states/hover.png','states/pressed.png']
    assert m['schema_version']=='asset-studio.ui-state-package/v1' and m['family']=='ui' and m['text_free'] is True
    assert m['sourceSize']=={'width':3,'height':2}
    assert m['sliceMargins']=={'top':1,'right':1,'bottom':1,'left':1}
    assert m['safeArea']=={'top':1,'right':2,'bottom':3,'left':4} and m['padding']=={'top':5,'right':6,'bottom':7,'left':8}
    assert m['modes']=={'sizing':'nine-slice','edge':'tile','center':'stretch'}
    assert pixels==out['frames']

def test_vertical_cells_and_base_reuse_are_byte_exact(driver):
    vertical=driver({'layout':'vertical','states':['normal','hover','pressed']}); assert _audit(vertical)[2]==vertical['frames']
    base=driver({'layout':'horizontal','states':['base']}); names,m,pixels=_audit(base)
    assert names==['manifest.json','states/base.png'] and m['stateLayout']=='base-reused' and pixels==base['frames']

def test_package_is_byte_deterministic(driver):
    out=driver({'layout':'horizontal','states':['normal','hover','pressed']}); assert out['same'] is True

@pytest.mark.parametrize('states', [['../evil'],['a/b'],['manifest'],['A','a'],['.'],['x'*129]])
def test_state_filenames_fail_closed(driver,states):
    out=driver({'layout':'horizontal','states':states}); assert 'error' in out and 'state' in out['error'].lower()

def test_budget_and_layout_fail_before_png_encoding():
    s=MAIN.read_text(); assert 'checkUiExportBudget' in s
    source=(_range(s,'function effectConcatBytes','const EFFECT_EXPORT_LIMITS')+_range(s,'let crc32Table = null;','function exportFull')+_range(s,'const UI_NINE_SLICE_BUDGETS','function renderUiNineSliceImageData')+_range(s,'const UI_EXPORT_LIMITS','async function selectedUiSourceImageData'))
    script=source+"\nlet calls=0;const old=encodeEffectFramePng;encodeEffectFramePng=(...x)=>{calls++;return old(...x)};try{buildUiExportPackage({width:4097,height:4097},{source_size:{width:4097,height:4097},slice_margins:{top:0,right:0,bottom:0,left:0},content_safe_area:{top:0,right:0,bottom:0,left:0},padding:{top:0,right:0,bottom:0,left:0},sizing_mode:'fixed',edge_mode:'stretch',center_mode:'stretch',states:['base']})}catch(e){console.log(JSON.stringify({error:e.message,calls}))}"
    out=json.loads(subprocess.run(['node','-e',script],text=True,capture_output=True,check=True).stdout)
    assert 'budget' in out['error'].lower() and out['calls']==0

def test_actual_button_download_busy_recovery_and_history_isolation():
    assert 'id="exportUiStateZip"' in HTML and 'id="uiExportSummary"' in HTML
    js=MAIN.read_text(); block=js[js.index('async function exportUiStatePackageZip'):js.index('function validateTilePreviewBudget')]
    assert 'downloadBlob(packageResult.zipBlob,packageResult.zipName)' in block
    assert 'finally' in block and 'button.disabled=false' in block
    assert 'saveHistory' not in block and 'canvas.add' not in block and 'fetch(' not in block and 'provider' not in block.lower()
    assert "$('exportUiStateZip').onclick" in js
