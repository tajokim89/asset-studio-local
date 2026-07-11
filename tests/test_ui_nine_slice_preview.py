"""Executable D3 nine-slice/state/QA regressions against production JavaScript."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src/main.js").read_text()
HTML = (ROOT / "index.html").read_text()
DOC = (ROOT / "docs/contracts/UI_NINE_SLICE_PREVIEW_CONTRACT.md").read_text()
FUNCTIONS = ("normalizeUiPreviewContract", "validateUiNineSliceBudget", "validateUiPreviewBudget", "uiNineSliceGeometry", "resolveUiPreviewRenderDimensions", "preflightUiPreview", "analyzeUiComponentImageData", "renderUiNineSliceImageData", "buildUiPreviewModel", "renderUiPreviewModel")


def fn(name):
    match = re.search(rf"\bfunction\s+{name}\s*\([^)]*\)\s*\{{", JS)
    assert match, name
    depth = 0
    quote = None
    escaped = False
    for index in range(match.end() - 1, len(JS)):
        char = JS[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "'\"`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if not depth:
                return JS[match.start():index + 1]
    raise AssertionError("unclosed function")


def run(body):
    budget_match = re.search(r"const UI_NINE_SLICE_BUDGETS = Object\.freeze\(\{[^;]+;", JS, re.S)
    assert budget_match
    budget = budget_match.group()
    fixture = r"""
const contract=(extra={})=>Object.assign({source_size:{width:7,height:6},slice_margins:{top:1,right:2,bottom:2,left:1},content_safe_area:{top:1,right:1,bottom:1,left:1},padding:{top:0,right:0,bottom:0,left:0},states:['normal','hover','pressed'],sizing_mode:'nine-slice',edge_mode:'stretch',center_mode:'stretch'},extra);
const image=(w=7,h=6,frame=false)=>{const data=new Uint8ClampedArray(w*h*4);for(let y=0;y<h;y++)for(let x=0;x<w;x++){let sx=frame?x%7:x,sy=frame?y%6:y,f=frame?(Math.floor(x/7)+Math.floor(y/6)*10):0;let region=(sy<1?0:sy>=4?6:3)+(sx<1?0:sx>=5?2:1);data.set([region*20+f,sx*17,sy*23,(sx===3&&sy===2)?1:255],(y*w+x)*4);}return {width:w,height:h,data};};
const reds=v=>{let a=[];for(let i=0;i<v.data.length;i+=4)a.push(v.data[i]);return a};
"""
    source = budget + "\n" + "\n".join(fn(name) for name in FUNCTIONS) + fixture + "\n" + body
    proc = subprocess.run(["node", "-e", source], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_exact_nine_regions_and_asymmetric_corners_small_medium_large():
    result = run(r"""let out={};for(const [n,w,h] of [['small',7,6],['medium',14,12],['large',21,18]]){let v=renderUiNineSliceImageData(image(),contract(),w,h),at=(x,y)=>v.data[(y*w+x)*4];out[n]={corners:[at(0,0),at(w-1,0),at(0,h-1),at(w-1,h-1)],regions:new Set(reds(v)).size,mismatch:v.qa.metrics.cornerMismatch,dims:[v.width,v.height]};}console.log(JSON.stringify(out));""")
    assert [result[x]["dims"] for x in ("small", "medium", "large")] == [[7, 6], [14, 12], [21, 18]]
    assert all(result[x]["corners"] == [0, 40, 120, 160] for x in result)
    assert all(result[x]["regions"] >= 9 and result[x]["mismatch"] == 0 for x in result)


def test_edge_and_center_stretch_tile_sequences_and_clipping_are_independent():
    result = run(r"""let im=image(), chan=(v,c)=>{let a=[];for(let i=c;i<v.data.length;i+=4)a.push(v.data[i]);return a},row=(v,c,y)=>chan(v,c).slice(y*14,(y+1)*14),col=(v,c)=>chan(v,c).filter((_,i)=>i%14===0);let es=renderUiNineSliceImageData(im,contract({edge_mode:'stretch',center_mode:'tile'}),14,12),et=renderUiNineSliceImageData(im,contract({edge_mode:'tile',center_mode:'stretch'}),14,12);console.log(JSON.stringify({topStretch:row(es,1,0),topTile:row(et,1,0),centerTile:row(es,1,6).slice(1,-2),centerStretch:row(et,1,6).slice(1,-2),leftStretch:col(es,2),leftTile:col(et,2)}));""")
    assert result["topStretch"] != result["topTile"]
    assert result["centerTile"] != result["centerStretch"]
    assert result["leftStretch"] != result["leftTile"]
    assert result["topTile"][-2:] == [85, 102]  # fixed right corner clips the tile


def test_targets_smaller_than_fixed_margins_are_rejected():
    result = run("""let e=[];for(const z of [[2,6],[7,2]])try{renderUiNineSliceImageData(image(),contract(),...z)}catch(x){e.push(x.message)}console.log(JSON.stringify(e));""")
    assert result == ["target smaller than fixed margins"] * 2


def test_zero_span_axis_rejects_expansion_but_exact_source_remains_valid():
    result = run(r"""const cases=[
      [contract({source_size:{width:7,height:6},slice_margins:{top:1,right:3,bottom:2,left:4}}),[8,6]],
      [contract({source_size:{width:7,height:6},slice_margins:{top:2,right:2,bottom:4,left:1}}),[7,7]]
    ],errors=[],exact=[];for(const [c,target] of cases){let reads=0,im=image();Object.defineProperty(im,'data',{get(){reads++;return new Uint8ClampedArray(im.width*im.height*4)}});try{renderUiNineSliceImageData(im,c,...target)}catch(e){errors.push([e.message,reads])}const ok=renderUiNineSliceImageData(image(),c,c.source_size.width,c.source_size.height);exact.push([ok.width,ok.height]);}console.log(JSON.stringify({errors,exact}));""")
    assert result["errors"] == [
        ["zero-width nine-slice stretch span cannot expand", 0],
        ["zero-height nine-slice stretch span cannot expand", 0],
    ]
    assert result["exact"] == [[7, 6], [7, 6]]


def test_zero_span_model_preflight_rejects_before_rgba_analysis():
    result = run(r"""const cases=[
      [contract({source_size:{width:7,height:6},slice_margins:{top:1,right:3,bottom:2,left:4}}),'medium'],
      [contract({source_size:{width:7,height:6},slice_margins:{top:2,right:2,bottom:4,left:1}}),'medium']
    ],out=[];for(const [c,mode] of cases){let reads=0,analyses=0,im={width:7,height:6,get data(){reads++;throw Error('RGBA accessed')}};const original=analyzeUiComponentImageData;analyzeUiComponentImageData=()=>{analyses++;return original(im,c)};try{buildUiPreviewModel(im,c,mode)}catch(e){out.push([e.message,reads,analyses])}analyzeUiComponentImageData=original;}const exact=buildUiPreviewModel(image(),cases[0][0],'source');console.log(JSON.stringify({out,exact:[exact.views[0].width,exact.views[0].height]}));""")
    assert result == {"out": [
        ["zero-width nine-slice stretch span cannot expand", 0, 0],
        ["zero-height nine-slice stretch span cannot expand", 0, 0],
    ], "exact": [7, 6]}


def test_zero_span_browser_preflight_rejects_before_canvas_or_pixel_access():
    source = "\n".join(fn(name) for name in FUNCTIONS) + "\n" + fn("buildUiNineSlicePreview") + r"""
let creates=0,draws=0,reads=0,currentContract;
global.document={createElement(){creates++;return {getContext(){return {drawImage(){draws++},getImageData(){reads++}}}}}};
const sourceImage={naturalWidth:7,naturalHeight:6},canvas={getActiveObject(){return {_element:sourceImage}}};
const $=id=>id==='uiPreviewMode'?{value:'medium'}:null;
const buildUiContract=()=>currentContract;
(async()=>{const out=[];for(currentContract of [
 {source_size:{width:7,height:6},slice_margins:{top:1,right:3,bottom:2,left:4},content_safe_area:{top:0,right:0,bottom:0,left:0},padding:{top:0,right:0,bottom:0,left:0},states:['normal'],sizing_mode:'nine-slice',edge_mode:'stretch',center_mode:'stretch'},
 {source_size:{width:7,height:6},slice_margins:{top:2,right:2,bottom:4,left:1},content_safe_area:{top:0,right:0,bottom:0,left:0},padding:{top:0,right:0,bottom:0,left:0},states:['normal'],sizing_mode:'nine-slice',edge_mode:'stretch',center_mode:'stretch'}
])try{await buildUiNineSlicePreview()}catch(e){out.push(e.message)}console.log(JSON.stringify({out,creates,draws,reads}));})().catch(e=>{console.error(e);process.exit(1)});
"""
    budget = re.search(r"const UI_NINE_SLICE_BUDGETS = Object\.freeze\(\{[^;]+;", JS, re.S).group()
    proc = subprocess.run(["node", "-e", budget + "\n" + source], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {"out": [
        "zero-width nine-slice stretch span cannot expand",
        "zero-height nine-slice stretch span cannot expand",
    ], "creates": 0, "draws": 0, "reads": 0}


def test_state_base_reuse_horizontal_vertical_exact_and_drift_fails():
    result = run(r"""let c=contract(), cases=[image(),image(21,6,true),image(7,18,true),image(8,6)];let a=cases.map(x=>analyzeUiComponentImageData(x,c));let frames=[0,1,2].map(i=>renderUiNineSliceImageData(cases[1],c,7,6,i).data[0]);let vertical=[0,1,2].map(i=>renderUiNineSliceImageData(cases[2],c,7,6,i).data[0]);let drift='';try{renderUiNineSliceImageData(cases[3],c,7,6)}catch(e){drift=e.message}console.log(JSON.stringify({layouts:a.map(x=>[x.stateLayout,x.status,x.stateCount]),frames,vertical,drift}));""")
    assert result["layouts"] == [["base-reused", "PASS", 1], ["horizontal-strip", "PASS", 3], ["vertical-strip", "PASS", 3], ["drift", "FAIL", 0]]
    assert result["frames"] == [0, 1, 2] and result["vertical"] == [0, 10, 20]
    assert result["drift"] == "state-size-drift"


def test_guides_have_exact_coordinates_and_source_is_one_to_one():
    result = run("""let s=buildUiPreviewModel(image(),contract(),'source'),g=buildUiPreviewModel(image(),contract(),'guides');console.log(JSON.stringify({sd:[s.views[0].width,s.views[0].height],same:Array.from(s.views[0].data).join()==Array.from(image().data).join(),coords:g.guideCoordinates,guides:g.guides}));""")
    assert result == {"sd": [7, 6], "same": True, "coords": {"slice": {"x": [1, 5], "y": [1, 4]}, "contentSafe": {"left": 1, "top": 1, "right": 6, "bottom": 5}, "padding": {"left": 1, "top": 1, "right": 6, "bottom": 5}, "sourceScale": 1}, "guides": True}


def test_assembly_placeholders_are_temporary_inside_safe_area_and_impossible_reason():
    result = run(r"""let ok=buildUiPreviewModel(image(),contract(),'assembly').assembly,bad=buildUiPreviewModel(image(),contract({content_safe_area:{left:7,right:7,top:6,bottom:6}}),'assembly');console.log(JSON.stringify({ok,bad:bad.assembly,qa:bad.qa}));""")
    area = result["ok"]["safeArea"]
    assert result["ok"]["temporary"] and result["ok"]["possible"] and result["ok"]["reason"] == "temporary-preview-only"
    assert all(area["left"] <= p["x"] and p["x"] + p["width"] <= area["right"] and area["top"] <= p["y"] and p["y"] + p["height"] <= area["bottom"] for p in result["ok"]["placeholders"])
    assert not result["bad"]["possible"] and result["bad"]["placeholders"] == [] and result["bad"]["reason"] == "safe-area-violation"
    assert result["qa"]["status"] == "FAIL" and "safe-area-violation" in result["qa"]["reasons"]


def test_state_comparison_dimensions_labels_and_reuse_disclosure():
    result = run("""let m=buildUiPreviewModel(image(),contract(),'state-comparison');console.log(JSON.stringify({dims:m.views.map(v=>[v.width,v.height]),labels:m.stateLabels,pixels:m.views.map(v=>v.data[0])}));""")
    assert result["dims"] == [[14, 12]] * 3 and result["pixels"] == [0, 0, 0]
    assert [x["id"] for x in result["labels"]] == ["normal", "hover", "pressed"]
    assert all(x["sourceFrame"] == 0 and x["label"] == "base reused" for x in result["labels"])


def test_integer_scale_integer_and_noninteger_metrics():
    result = run("""let a=buildUiPreviewModel(image(),contract(),'integer-scale',{viewportWidth:25,viewportHeight:20,targetW:14,targetH:12}),b=buildUiPreviewModel(image(),contract(),'integer-scale',{viewportWidth:25,viewportHeight:20,targetW:15,targetH:12});console.log(JSON.stringify([a.integerScale,b.integerScale,[a.views[0].width,a.views[0].height]]));""")
    assert result == [{"scale": 3, "warning": False, "reason": "integer-scale"}, {"scale": 3, "warning": True, "reason": "noninteger-target"}, [21, 18]]


def test_tiled_edges_compare_each_strips_own_repeat_seam_with_exact_metrics():
    result = run(r"""const c=contract({source_size:{width:8,height:7},slice_margins:{top:2,right:2,bottom:1,left:1},states:['normal'],edge_mode:'tile'});
const make=()=>{const data=new Uint8ClampedArray(8*7*4);for(let i=3;i<data.length;i+=4)data[i]=255;const put=(x,y,v)=>data.set([v,v,v,255],(y*8+x)*4);
// Opposite edges match at every coordinate, but each edge strip's repeat endpoints do not.
for(const y of [0,1,6]){put(1,y,20);put(5,y,80)}
for(const x of [0,6,7]){put(x,2,30);put(x,5,90)}return {width:8,height:7,data}};
const bad=make(),good=make();for(const y of [0,1,6])good.data.set(good.data.slice((y*8+1)*4,(y*8+1)*4+4),(y*8+5)*4);for(const x of [0,6,7])good.data.set(good.data.slice((2*8+x)*4,(2*8+x)*4+4),(5*8+x)*4);
console.log(JSON.stringify({bad:analyzeUiComponentImageData(bad,c),good:analyzeUiComponentImageData(good,c),stretch:analyzeUiComponentImageData(bad,{...c,edge_mode:'stretch'})}));""")
    bad, good, stretch = result["bad"], result["good"], result["stretch"]
    assert bad["status"] == "WARN" and bad["reasons"] == ["non-seamless-tiled-edge"]
    assert bad["metrics"]["edgeComparisons"] == 6
    assert bad["metrics"]["edgeMismatch"] == 6 and bad["metrics"]["edgeMismatchRate"] == 1
    assert good["status"] == "PASS" and good["reasons"] == []
    assert good["metrics"]["edgeComparisons"] == 6 and good["metrics"]["edgeMismatch"] == 0
    assert stretch["status"] == "PASS" and stretch["metrics"]["edgeComparisons"] == 0


def test_tiled_edges_skip_seam_comparison_on_zero_span_axis():
    result = run(r"""const solid=()=>{const im=image();im.data.fill(64);return im},horizontal=solid(),vertical=solid();
    for(let y=0;y<6;y++){horizontal.data.fill(10,(y*7+3)*4,(y*7+3)*4+4);horizontal.data.fill(20,(y*7+4)*4,(y*7+4)*4+4)}
    for(let x=0;x<7;x++){vertical.data.fill(10,(1*7+x)*4,(1*7+x)*4+4);vertical.data.fill(20,(2*7+x)*4,(2*7+x)*4+4)}
    const cases=[
      [horizontal,contract({slice_margins:{top:1,right:3,bottom:2,left:4},edge_mode:'tile'})],
      [vertical,contract({slice_margins:{top:2,right:2,bottom:4,left:1},edge_mode:'tile'})]
    ];console.log(JSON.stringify(cases.map(([im,c])=>{const qa=analyzeUiComponentImageData(im,c);return {status:qa.status,reasons:qa.reasons,comparisons:qa.metrics.edgeComparisons,mismatch:qa.metrics.edgeMismatch}})));""")
    assert result == [
        {"status": "PASS", "reasons": [], "comparisons": 7, "mismatch": 0},
        {"status": "PASS", "reasons": [], "comparisons": 6, "mismatch": 0},
    ]


def test_multistate_qa_uses_each_horizontal_and_vertical_frame_and_fails_closed():
    result = run(r"""const make=vertical=>{const w=vertical?7:21,h=vertical?18:6,data=new Uint8ClampedArray(w*h*4);data.fill(128);for(let i=3;i<data.length;i+=4)data[i]=255;const put=(state,x,y,rgba)=>{const gx=x+(vertical?0:state*7),gy=y+(vertical?state*6:0);data.set(rgba,(gy*w+gx)*4)};for(const [x,y] of [[2,1],[2,2],[2,3],[4,1],[4,2],[4,3]])put(1,x,y,[255,255,255,255]);put(2,4,0,[0,0,0,255]);return {width:w,height:h,data}};let out={};for(const vertical of [false,true]){const im=make(vertical),c=contract({edge_mode:'tile'}),analysis=analyzeUiComponentImageData(im,c),model=buildUiPreviewModel(im,c,'state-comparison');out[vertical?'vertical':'horizontal']={status:analysis.status,reasons:analysis.reasons,stateStatuses:analysis.stateQas.map(q=>q.status),stateReasons:analysis.stateQas.map(q=>q.reasons),viewReasons:model.views.map(v=>v.qa.reasons),viewGlyphs:model.views.map(v=>v.qa.metrics.glyphComponents),viewEdges:model.views.map(v=>v.qa.metrics.edgeMismatch)};}console.log(JSON.stringify(out));""")
    for orientation in ("horizontal", "vertical"):
        value = result[orientation]
        assert value["status"] == "WARN"
        assert value["reasons"] == ["baked-text-advisory", "non-seamless-tiled-edge"]
        assert value["stateStatuses"] == ["PASS", "WARN", "WARN"]
        assert value["stateReasons"] == [[], ["baked-text-advisory"], ["non-seamless-tiled-edge"]]
        assert value["viewReasons"] == value["stateReasons"]
        assert value["viewGlyphs"] == [0, 2, 0]
        assert value["viewEdges"] == [0, 0, 1]


def test_stretched_corner_detector_can_fail_against_corrupted_output_path():
    result = run(r"""let base=image(),bad=new Uint8ClampedArray(base.data);bad[0]=255;let reads=0,N=14*12;let changing={width:7,height:6,get data(){reads++;return reads>1+4*N?bad:base.data}};let v=renderUiNineSliceImageData(changing,contract(),14,12);console.log(JSON.stringify({status:v.qa.status,reasons:v.qa.reasons,m:v.qa.metrics.cornerMismatch,reads}));""")
    assert result["status"] == "FAIL" and "stretched-corners" in result["reasons"]
    assert result["m"] > 0 and result["reads"] > 1 + 4 * 14 * 12


def test_baked_text_heuristic_positive_and_smooth_panel_negative_threshold():
    result = run(r"""let smooth=image();smooth.data.fill(128);let glyph=image();glyph.data.fill(128);for(let i=3;i<glyph.data.length;i+=4)glyph.data[i]=255;for(const [x,y] of [[2,1],[2,2],[2,3],[4,1],[4,2],[4,3]])glyph.data.set([255,255,255,255],(y*7+x)*4);let a=analyzeUiComponentImageData(glyph,contract()),b=analyzeUiComponentImageData(smooth,contract());console.log(JSON.stringify({a,b}));""")
    assert result["a"]["metrics"]["glyphComponents"] == 2 and result["a"]["metrics"]["bakedTextHeuristic"]
    assert "baked-text-advisory" in result["a"]["reasons"] and result["a"]["status"] == "WARN"
    assert result["b"]["metrics"]["glyphComponents"] == 0 and result["b"]["status"] == "PASS"
    assert "luminance below 48 or above 207" in DOC and "two or more trigger" in DOC


def test_alpha_one_is_preserved_byte_exactly():
    result = run("""let v=renderUiNineSliceImageData(image(),contract({center_mode:'tile'}),14,12);console.log(JSON.stringify({has:Array.from(v.data).filter((_,i)=>i%4===3).includes(1),source:image().data[(2*7+3)*4+3]}));""")
    assert result == {"has": True, "source": 1}


def test_source_target_work_budgets_and_preallocation_order():
    result = run(r"""let ok=validateUiNineSliceBudget(7,6,contract(),14,12),limit=validateUiNineSliceBudget(4096,4096,contract(),4096,4096),errors=[];for(const z of [[16384,1025,1,1],[1,1,16384,1025]])try{validateUiNineSliceBudget(z[0],z[1],contract(),z[2],z[3])}catch(e){errors.push(e.message)}let reads=0;try{analyzeUiComponentImageData({width:16384,height:1025,get data(){reads++;throw Error('pixel read')}},contract())}catch(e){}console.log(JSON.stringify({ok,limit,errors,reads}));""")
    assert result["ok"] == {"sourcePixels": 42, "targetPixels": 168, "workPixels": 546, "analysisAuxiliaryBytes": 210}
    assert result["limit"]["workPixels"] == 67108864
    assert result["errors"] == ["UI nine-slice budget: source pixels exceed 16777216", "UI nine-slice budget: target pixels exceed 16777216"]
    assert result["reads"] == 0
    build = fn("buildUiNineSlicePreview")
    assert build.index("preflightUiPreview") < build.index("document.createElement('canvas')") < build.index("getImageData")


def test_all_preview_modes_are_deterministic_and_semantically_distinct():
    result = run(r"""let modes=['source','guides','small','medium','large','assembly','state-comparison','integer-scale'],sig=m=>{let x=buildUiPreviewModel(image(),contract(),m,{viewportWidth:25,viewportHeight:20});return JSON.stringify({mode:x.mode,d:x.views.map(v=>[v.width,v.height]),guides:x.guides,assembly:!!x.assembly,states:x.views.length,integer:x.integerScale.scale})};console.log(JSON.stringify(modes.map(m=>[sig(m),sig(m)])));""")
    assert all(a == b for a, b in result)
    assert len({a for a, _ in result}) == 8


def test_ui_accessible_ui_only_wiring_read_only_and_no_export_behavior():
    assert 'id="uiNineSlicePreviewPanel"' in HTML and 'aria-label="UI 나인슬라이스 미리보기 및 QA"' in HTML
    options = re.findall(r'<option value="([^"]+)"', HTML[HTML.index('id="uiPreviewMode"'):HTML.index('id="tilePreviewPanel"')])
    assert options == ["source", "guides", "small", "medium", "large", "assembly", "state-comparison", "integer-scale"]
    assert "family !== 'ui'" in JS and "$('buildUiNineSlicePreview').onclick" in JS
    production = fn("buildUiNineSlicePreview") + fn("buildUiPreviewModel") + fn("renderUiNineSliceImageData")
    assert not re.search(r"saveHistory|download|export|toBlob|toDataURL|canvas\.add|canvas\.remove", production, re.I)


def test_contract_exact_layout_render_qa_and_reason_token_semantics():
    exact = ["base-reused", "horizontal strip", "vertical strip", "state-size-drift", "stretched-corners", "non-seamless-tiled-edge", "safe-area-violation", "baked-text-advisory", "noninteger-target", "alpha `1` is data", "origin-locked", "deterministically clipped", "Before pixel access"]
    assert all(token in DOC for token in exact)
    assert "Statuses have precedence **FAIL**, **WARN**, **PASS**" in DOC
    assert "temporary preview overlays only" in DOC and "does not alter the Fabric canvas" in DOC


def test_d3_review_small_is_real_resize_and_guides_include_distinct_padding():
    result = run("""let s=buildUiPreviewModel(image(),contract(),'small'),g=buildUiPreviewModel(image(),contract({padding:{top:1,right:2,bottom:1,left:2}}),'guides');console.log(JSON.stringify({small:[s.views[0].width,s.views[0].height],reason:s.resizeReason,g:g.guideCoordinates}));""")
    assert result["small"] == [3, 3] and result["reason"] == "resized-to-minimum"
    assert result["g"]["padding"] == {"left": 3, "top": 2, "right": 4, "bottom": 4}
    assert result["g"]["padding"] != result["g"]["contentSafe"]


def test_d3_resized_target_safe_area_uses_padding_and_cannot_inherit_source_pass():
    result = run(r"""const padded=contract({slice_margins:{top:1,right:1,bottom:1,left:1},padding:{top:1,right:1,bottom:1,left:1}});let small=buildUiPreviewModel(image(),padded,'small'),sourceQa={status:'PASS',reasons:[],stateLayout:'base-reused',metrics:{safeWidth:999,safeHeight:999}};analyzeUiComponentImageData=()=>sourceQa;let explicit=renderUiNineSliceImageData(image(),padded,3,3);console.log(JSON.stringify({small:[small.views[0].width,small.views[0].height],smallQa:small.views[0].qa,sourceQa,explicit:explicit.qa}));""")
    assert result["small"] == [5, 5]
    assert result["smallQa"]["status"] == "PASS"
    assert result["smallQa"]["metrics"]["safeWidth"] == 1
    assert result["smallQa"]["metrics"]["safeHeight"] == 1
    assert result["explicit"]["status"] == "FAIL"
    assert "safe-area-violation" in result["explicit"]["reasons"]
    assert result["explicit"]["metrics"]["safeWidth"] == -1
    assert result["explicit"]["metrics"]["safeHeight"] == -1
    assert result["explicit"]["metrics"]["safeWidth"] != result["sourceQa"]["metrics"]["safeWidth"]


def test_d3_review_renderer_all_views_labels_and_aggregated_qa():
    result = run(r"""
global.ImageData=class{constructor(data,width,height){this.data=data;this.width=width;this.height=height}};
const node=tag=>({tag,className:'',dataset:{},children:[],appendChild(x){this.children.push(x)},getContext(){return {putImageData(){},setLineDash(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},strokeRect(){},fillRect(){}}}});
global.document={createElement:node};const stage=node('stage');stage.replaceChildren=function(){this.children=[]};const summary=node('summary');
const q=(id,mismatch,comparisons,safe,status,reason)=>({status,reasons:reason?[reason]:[],metrics:{stateId:id,stateIndex:id==='a'?0:1,sourceFrame:id==='a'?0:1,edgeMismatch:mismatch,edgeComparisons:comparisons,edgeMismatchRate:mismatch/comparisons,safeWidth:safe,safeHeight:safe+1,glyphComponents:id==='a'?1:2,bakedTextHeuristic:id==='b'}});
const model={qa:{status:'PASS',reasons:[],metrics:{}},views:[{width:1,height:1,data:new Uint8ClampedArray(4),qa:q('a',1,2,8,'WARN','first')},{width:1,height:1,data:new Uint8ClampedArray(4),qa:q('b',2,8,3,'FAIL','second')}],stateLabels:[{id:'a',label:'horizontal strip'},{id:'b',label:'horizontal strip'}],integerScale:{scale:1,warning:false,reason:'integer-scale'},assembly:null,guides:false};
const aggregate=renderUiPreviewModel(model,contract(),stage,summary);console.log(JSON.stringify({aggregate,text:summary.textContent,status:summary.dataset.status,labels:stage.children.map(x=>x.children[0].textContent)}));
""")
    assert result["status"] == "FAIL" and result["labels"] == ["a · horizontal strip", "b · horizontal strip"]
    metrics = result["aggregate"]["metrics"]
    assert metrics["edgeMismatch"] == 3 and metrics["edgeComparisons"] == 10 and metrics["edgeMismatchRate"] == .3
    assert metrics["safeWidth"] == 3 and metrics["safeHeight"] == 4 and metrics["glyphComponents"] == 3
    assert [x["stateId"] for x in metrics["views"]] == ["a", "b"]
    assert "first, second" in result["text"] and '"edgeMismatch":3' in result["text"]


def test_d3_review_renderer_aggregates_each_unique_source_frame_once():
    result = run(r"""
global.ImageData=class{constructor(data,width,height){this.data=data;this.width=width;this.height=height}};
const node=tag=>({tag,className:'',dataset:{},textContent:'',children:[],appendChild(x){this.children.push(x)},replaceChildren(){this.children=[]},getContext(){return {putImageData(){},setLineDash(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},strokeRect(){},fillRect(){}}}});global.document={createElement:node};
const render=model=>renderUiPreviewModel(model,contract(),node('stage'),node('summary')).metrics;
const make=(frame,index)=>({width:1,height:1,data:new Uint8ClampedArray(4),qa:{status:'PASS',reasons:[],metrics:{stateId:`s${index}`,stateIndex:index,sourceFrame:frame,edgeMismatch:2+frame,edgeComparisons:4+frame,safeWidth:9-index,safeHeight:8-index,glyphComponents:1+frame,bakedTextHeuristic:false}}});
const model=views=>({qa:{status:'PASS',reasons:[]},views,stateLabels:views.map((_,i)=>({id:`s${i}`,label:'base reused'})),integerScale:{scale:1,warning:false,reason:'integer-scale'},assembly:null,guides:false});
const productionReused=model=>render(model);const reusedModel=buildUiPreviewModel(image(),contract(),'state-comparison'),distinctModel=buildUiPreviewModel(image(21,6,true),contract(),'state-comparison');
console.log(JSON.stringify({reused:render(model([make(0,0),make(0,1),make(0,2)])),distinct:render(model([make(0,0),make(1,1),make(2,2)])),production:{reused:productionReused(reusedModel),reusedQa:reusedModel.qa.metrics,distinct:render(distinctModel),distinctQa:distinctModel.qa.metrics}}));
""")
    reused, distinct = result["reused"], result["distinct"]
    assert (reused["edgeMismatch"], reused["edgeComparisons"], reused["glyphComponents"]) == (2, 4, 1)
    assert (reused["safeWidth"], reused["safeHeight"]) == (7, 6)
    assert [x["sourceFrame"] for x in reused["uniqueMetricRecords"]] == [0]
    assert (distinct["edgeMismatch"], distinct["edgeComparisons"], distinct["glyphComponents"]) == (9, 15, 6)
    assert [x["sourceFrame"] for x in distinct["uniqueMetricRecords"]] == [0, 1, 2]
    production = result["production"]
    for layout in ("reused", "distinct"):
        assert production[layout]["edgeMismatch"] == production[f"{layout}Qa"]["edgeMismatch"]
        assert production[layout]["edgeComparisons"] == production[f"{layout}Qa"]["edgeComparisons"]
        assert production[layout]["glyphComponents"] == production[f"{layout}Qa"]["glyphComponents"]
    assert len(production["reused"]["views"]) == 3
    assert [x["sourceFrame"] for x in production["reused"]["uniqueMetricRecords"]] == [0]
    assert [x["sourceFrame"] for x in production["distinct"]["uniqueMetricRecords"]] == [0, 1, 2]


def test_d3_baked_text_queue_is_typed_bounded_and_budgeted_before_pixel_access():
    result = run(r"""const w=512,h=256,data=new Uint8ClampedArray(w*h*4);for(let i=0;i<data.length;i+=4){data[i]=255;data[i+1]=255;data[i+2]=255;data[i+3]=255}const c=contract({source_size:{width:w,height:h},states:['normal'],content_safe_area:{top:0,right:0,bottom:0,left:0}}),a=analyzeUiComponentImageData({width:w,height:h,data},c),b=validateUiNineSliceBudget(w,h,c,w,h);let reads=0,error='';try{analyzeUiComponentImageData({width:4096,height:3277,get data(){reads++;return data}},contract({source_size:{width:4096,height:3277},states:['normal']}))}catch(e){error=e.message}console.log(JSON.stringify({a:a.metrics,b,reads,error}));""")
    assert result["a"]["glyphComponents"] == 0
    assert result["a"]["analysisAuxiliaryBytes"] == 512 * 256 * 5
    assert result["b"]["analysisAuxiliaryBytes"] == 512 * 256 * 5
    assert result["reads"] == 0 and "auxiliary bytes exceed" in result["error"]
    analysis = fn("analyzeUiComponentImageData")
    assert "new Uint32Array" in analysis and not re.search(r"(?:q|queue)\s*=\s*\[\s*\[", analysis)


def test_d3_public_helpers_reject_malformed_contracts_at_their_boundary():
    result = run(r"""const bad=[{source_size:{width:'7',height:6}},{slice_margins:{top:-1,right:2,bottom:2,left:1}},{states:['ok','']},{states:['x','x']},{sizing_mode:'mystery'},{edge_mode:'wrap'},{center_mode:'wrap'},{padding:{top:NaN,right:0,bottom:0,left:0}},{content_safe_area:{top:0,right:'0',bottom:0,left:0}}],calls=[c=>validateUiNineSliceBudget(7,6,c,7,6),c=>analyzeUiComponentImageData(image(),c),c=>renderUiNineSliceImageData(image(),c,7,6),c=>buildUiPreviewModel(image(),c,'source')];let out=[];for(const partial of bad){const c=Object.assign(contract(),partial);out.push(calls.map(call=>{try{call(c);return 'accepted'}catch(e){return e.message}}))}let modes=[];for(const mode of ['bogus',NaN])try{buildUiPreviewModel(image(),contract(),mode);modes.push('accepted')}catch(e){modes.push(e.message)}console.log(JSON.stringify({out,modes}));""")
    assert all(all(message != "accepted" and "UI contract:" in message for message in row) for row in result["out"])
    assert all("UI preview mode" in message for message in result["modes"])


def test_d3_empty_states_normalize_to_one_base_state_across_public_helpers_and_renderer():
    result = run(r"""
const empty=contract({states:[]}), normalized=normalizeUiPreviewContract(empty);
const budget=validateUiNineSliceBudget(7,6,empty,7,6);
const analysis=analyzeUiComponentImageData(image(),empty);
const rendered=renderUiNineSliceImageData(image(),empty,7,6);
const model=buildUiPreviewModel(image(),empty,'state-comparison');
global.ImageData=class{constructor(data,width,height){this.data=data;this.width=width;this.height=height}};
const node=tag=>({tag,className:'',dataset:{},textContent:'',children:[],appendChild(x){this.children.push(x)},replaceChildren(){this.children=[]},getContext(){return {putImageData(){},setLineDash(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},strokeRect(){},fillRect(){},fillText(){}}}});
global.document={createElement:node};const stage=node('stage'),summary=node('summary');
const aggregate=renderUiPreviewModel(model,empty,stage,summary);
const invalid=[undefined,null,'base',[''],['base','base']].map(states=>{const c=contract();if(states===undefined)delete c.states;else c.states=states;try{normalizeUiPreviewContract(c);return 'accepted'}catch(e){return e.message}});
console.log(JSON.stringify({states:normalized.states,budget,analysis:{layout:analysis.stateLayout,count:analysis.stateCount,status:analysis.status},rendered:{status:rendered.qa.status},model:{labels:model.stateLabels,views:model.views.length,qa:model.qa.status,viewQa:model.views[0].qa.status},aggregate:{status:aggregate.status,summary:summary.dataset.status},invalid}));
""")
    assert result["states"] == ["base"]
    assert result["budget"]["sourcePixels"] == 42
    assert result["analysis"] == {"layout": "base-reused", "count": 1, "status": "PASS"}
    assert result["rendered"] == {"status": "PASS"}
    assert result["model"]["views"] == 1 and result["model"]["qa"] == "PASS" and result["model"]["viewQa"] == "PASS"
    assert result["model"]["labels"] == [{"id": "base", "index": 0, "sourceFrame": 0, "label": "base reused"}]
    assert result["aggregate"] == {"status": "PASS", "summary": "PASS"}
    assert all(message != "accepted" and "UI contract:" in message for message in result["invalid"])


def test_d3_browser_handler_canonicalizes_empty_ui_states_before_preflight_and_render():
    budget_match = re.search(r"const UI_NINE_SLICE_BUDGETS = Object\.freeze\(\{[^;]+;", JS, re.S)
    assert budget_match
    controls = r"""
const elements={
  uiStates:{value:'[]'},uiSourceWidth:{value:'7'},uiSourceHeight:{value:'6'},
  uiPreviewMode:{value:'state-comparison'},uiNineSlicePreviewStage:{},uiNineSliceQaSummary:{}
};
const $=id=>elements[id]||null,controlValue=(id,fallback='')=>$(id)?.value??fallback;
const source={width:7,height:6},canvas={getActiveObject:()=>({_element:source})};
let rendered=null,historyCalls=0,mutationCalls=0;
const saveHistory=()=>historyCalls++,mutate=()=>mutationCalls++;
const imageData={width:7,height:6,data:new Uint8ClampedArray(7*6*4)};
const document={createElement:()=>({width:0,height:0,getContext:()=>({drawImage(){},getImageData:()=>imageData})})};
function renderUiPreviewModel(model,contract){rendered={states:contract.states.slice(),labels:model.stateLabels.map(x=>x.id),views:model.views.length,budgetViewCount:model.budget.viewCount};}
"""
    names = [name for name in FUNCTIONS if name != "renderUiPreviewModel"]
    source = "\n".join([
        budget_match.group(), controls, fn("buildUiContract"),
        *(fn(name) for name in names), fn("buildUiNineSlicePreview"),
        "const model=buildUiNineSlicePreview();console.log(JSON.stringify({rendered,modelStates:model.stateLabels.map(x=>x.id),historyCalls,mutationCalls}));",
    ])
    proc = subprocess.run(["node", "-e", source], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result == {
        "rendered": {"states": ["base"], "labels": ["base"], "views": 1, "budgetViewCount": 1},
        "modelStates": ["base"], "historyCalls": 0, "mutationCalls": 0,
    }


def test_d3_multistate_preflight_counts_unique_analysis_and_all_views_before_allocation():
    result = run(r"""
const modest=contract({states:Array.from({length:12},(_,i)=>`s${i}`)});
const model=buildUiPreviewModel(image(),modest,'state-comparison');
const huge=contract({states:Array.from({length:50000},(_,i)=>`s${i}`)});
let allocations=0,error='';const original=renderUiNineSliceImageData;
renderUiNineSliceImageData=(...args)=>{allocations++;return original(...args)};
try{buildUiPreviewModel(image(),huge,'state-comparison')}catch(e){error=e.message}
console.log(JSON.stringify({budget:model.budget,states:model.views.map(v=>v.qa.metrics.stateId),allocations,error}));
""")
    assert result["budget"]["uniqueAnalysisCount"] == 1
    assert result["budget"]["viewCount"] == 12
    assert result["budget"]["viewPixels"] == 12 * 14 * 12
    assert result["budget"]["rgbaBytes"] == 12 * 14 * 12 * 4
    assert result["budget"]["canvasBackingBytes"] == 12 * 14 * 12 * 4
    assert result["states"] == [f"s{i}" for i in range(12)]
    assert result["allocations"] == 0
    assert result["error"] == "UI preview budget: output/backing bytes exceed 67108864"


def test_d3_review_renderer_placeholders_padding_and_integer_summary():
    render = fn("renderUiPreviewModel")
    assert all(token in render for token in ("icon", "text", "content", "padding", "integerScale", "noninteger-target"))


def test_assembly_renderer_pixels_are_distinct_and_confined_to_tiny_safe_area():
    renderer = fn("renderUiPreviewModel")
    script = r"""
const pixels=new Map(), color=()=>String(ctx.fillStyle), paint=(x,y,w,h,c)=>{for(let py=Math.floor(y);py<Math.ceil(y+h);py++)for(let px=Math.floor(x);px<Math.ceil(x+w);px++)pixels.set(`${px},${py}`,c)};
const ctx={fillStyle:'',putImageData(){},fillRect(x,y,w,h){paint(x,y,w,h,color())},fillText(s,x,y){paint(x,y-9,s.length*6,12,color())}};
const canvas={width:0,height:0,getContext:()=>ctx}, document={createElement:t=>t==='canvas'?canvas:{className:'',textContent:'',appendChild(){}}};
const ImageData=function(){};
const stage={replaceChildren(){},appendChild(){}},summary={dataset:{},textContent:''};
const safeArea={left:2,top:1,right:7,bottom:4};
const model={qa:{status:'PASS',reasons:[],metrics:{}},views:[{width:9,height:6,data:new Uint8ClampedArray(216),qa:{status:'PASS',reasons:[],metrics:{}}}],stateLabels:[],guides:false,assembly:{safeArea,possible:true,temporary:true,placeholders:[{type:'icon',x:2,y:1,width:5,height:1},{type:'text',x:2,y:2,width:5,height:1},{type:'content',x:2,y:3,width:5,height:1}]},integerScale:{scale:1,warning:false,reason:'integer-scale'}};
renderUiPreviewModel(model,{source_size:{width:9,height:6},slice_margins:{top:1,right:1,bottom:1,left:1},content_safe_area:{top:0,right:0,bottom:0,left:0},padding:{top:0,right:0,bottom:0,left:0},states:['normal'],sizing_mode:'nine-slice',edge_mode:'stretch',center_mode:'stretch'},stage,summary);
const placeholderColors=[...new Set([...pixels.values()].filter(c=>c!=='rgba(20,20,30,.65)'))];
const escaped=[...pixels].filter(([key,c])=>c!=='rgba(20,20,30,.65)').map(([key])=>key.split(',').map(Number)).filter(([x,y])=>x<safeArea.left||x>=safeArea.right||y<safeArea.top||y>=safeArea.bottom);
console.log(JSON.stringify({placeholderColors,escaped,count:[...pixels].filter(([,c])=>c!=='rgba(20,20,30,.65)').length}));
"""
    budget_match = re.search(r"const UI_NINE_SLICE_BUDGETS = Object\.freeze\(\{[^;]+;", JS, re.S)
    assert budget_match
    budget = budget_match.group()
    proc = subprocess.run(["node", "-e", budget + "\n" + fn("normalizeUiPreviewContract") + "\n" + renderer + "\n" + script], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert len(result["placeholderColors"]) == 3
    assert result["count"] > 0
    assert result["escaped"] == []


def test_fixed_state_preview_rejects_exact_cumulative_allocation_before_render():
    result = run(r"""const states=Array.from({length:13},(_,i)=>`s${i}`),c=contract({source_size:{width:1024,height:1024},slice_margins:{top:0,right:0,bottom:0,left:0},content_safe_area:{top:0,right:0,bottom:0,left:0},states,sizing_mode:'fixed'}),im={width:1024,height:1024};let reads=0,renders=0;Object.defineProperty(im,'data',{get(){reads++;throw Error('pixel read')}});const original=renderUiNineSliceImageData;renderUiNineSliceImageData=(...args)=>{renders++;return original(...args)};let error='';try{buildUiPreviewModel(im,c,'state-comparison',{targetW:1,targetH:1})}catch(e){error=e.message}console.log(JSON.stringify({error,reads,renders}));""")
    assert result == {"error": "UI preview budget: output/backing bytes exceed 67108864", "reads": 0, "renders": 0}


def test_normal_fixed_preview_budget_is_exactly_what_views_allocate():
    result = run(r"""const c=contract({sizing_mode:'fixed'}),m=buildUiPreviewModel(image(),c,'state-comparison',{targetW:3,targetH:3});console.log(JSON.stringify({dims:m.views.map(v=>[v.width,v.height]),viewPixels:m.budget.viewPixels,rgba:m.budget.rgbaBytes,actual:m.views.reduce((n,v)=>n+v.data.length,0)}));""")
    assert result == {"dims": [[7, 6]] * 3, "viewPixels": 126, "rgba": 504, "actual": 504}
