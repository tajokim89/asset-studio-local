"""C3 deterministic tile-preview and map-use QA regression contracts.

The runtime tests extract and execute the production functions from ``src/main.js``
in Node.  Synthetic ImageData objects are deterministic and require no browser,
network, generation provider, or download.
"""
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = ROOT / "src/main.js"
HTML_PATH = ROOT / "index.html"
CONTRACT_PATH = ROOT / "docs/contracts/TILE_PREVIEW_QA_CONTRACT.md"
CSS_PATH = ROOT / "styles/app.css"
JS = MAIN_PATH.read_text(encoding="utf-8")
HTML = HTML_PATH.read_text(encoding="utf-8")
CONTRACT = CONTRACT_PATH.read_text(encoding="utf-8")
CSS = CSS_PATH.read_text(encoding="utf-8")
MODES = ["source", "repeat-3x3", "random-repeat", "terrain-brush", "rule-coverage", "overlay", "variant-distribution"]


def _function_source(name):
    match = re.search(rf"\bfunction\s+{name}\s*\([^)]*\)\s*\{{", JS)
    assert match, f"missing production function {name}"
    opening, depth, quote, escaped = match.end() - 1, 0, None, False
    for pos in range(opening, len(JS)):
        char = JS[pos]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`": quote = char
        elif char == "{": depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0: return JS[match.start():pos + 1]
    raise AssertionError(f"unclosed production function {name}")


@pytest.fixture(scope="module")
def runtime():
    budget = re.search(r"const TILE_PREVIEW_BUDGETS = Object\.freeze\(\{[^;]+;", JS, re.S)
    assert budget, "missing frozen tile preview budgets"
    functions = budget.group(0) + "\n" + "\n".join(_function_source(n) for n in ("validateTilePreviewBudget", "analyzeTileAtlasImageData", "buildTilePreviewModel", "fitTilePreview"))
    script = f"""
{functions}
const image=(w,h,fill=[0,0,0,0])=>{{const data=new Uint8ClampedArray(w*h*4);for(let i=0;i<w*h;i++)data.set(fill,i*4);return {{width:w,height:h,data}};}};
const put=(im,x,y,p)=>im.data.set(p,(y*im.width+x)*4);
const base={{tile_size:{{width:2,height:2}},rows:1,columns:1,margin:0,spacing:0,seamless:false,terrain_types:[],transitions:[],inner_corners:false,outer_corners:false,variants:[],metadata:{{}}}};
const exact=image(7,4); // margin 1, two 2x2 cells, one-pixel gutter
for(let y=1;y<3;y++)for(let x=1;x<3;x++)put(exact,x,y,[10+x,y,30,255]);
for(let y=1;y<3;y++)for(let x=4;x<6;x++)put(exact,x,y,[40+x,y,60,255]);
put(exact,3,1,[9,8,7,1]);
const exactContract={{...base,rows:1,columns:2,margin:1,spacing:1}};
const seamless=image(2,2); [[1,2,3,255],[9,2,3,255],[4,5,6,255],[8,5,6,255]].forEach((p,i)=>seamless.data.set(p,i*4));
const duplicate=image(4,2,[3,4,5,255]);
const corner=image(2,2); [[1,1,1,255],[2,2,2,255],[3,3,3,255],[4,4,4,255]].forEach((p,i)=>corner.data.set(p,i*4));
const rich={{...base,rows:1,columns:2,terrain_types:['grass'],transitions:['shore'],topology:'edge',inner_corners:true,outer_corners:true,metadata:{{collision:{{indices:[0,2]}},occlusion:{{tiles:[-1]}},navigation:{{tile_indices:[1,1.5]}}}},variants:[{{id:'zero',weight:0}},{{id:'neg',weight:-3}},{{id:'good',weight:2}},{{id:'more',weight:6}}]}};
const allNonpositive={{...rich,metadata:{{collision:{{}}}},variants:[{{id:'a',weight:0}},{{id:'b',weight:-2}},{{id:'c',weight:'bad'}}]}};
const before=JSON.stringify({{rich,allNonpositive}});
const models=Object.fromEntries({json.dumps(MODES)}.map(m=>[m,buildTilePreviewModel(exact,rich,m)]));
const result={{
 exact:analyzeTileAtlasImageData(exact,exactContract),
 seam:analyzeTileAtlasImageData(seamless,{{...base,seamless:true}}),
 duplicate:analyzeTileAtlasImageData(duplicate,{{...base,columns:2}}),
 corner:analyzeTileAtlasImageData(corner,{{...base,inner_corners:true}}),
 rich:analyzeTileAtlasImageData(exact,rich),
 truncated:analyzeTileAtlasImageData(image(3,2,[0,0,0,0]),{{...base,columns:2,terrain_types:['a']}}),
 variants:analyzeTileAtlasImageData(exact,rich).variants,
 fallback:analyzeTileAtlasImageData(exact,allNonpositive).variants,
 fallbackModel:buildTilePreviewModel(exact,allNonpositive,'variant-distribution'),
 mutation:before===JSON.stringify({{rich,allNonpositive}}), models,
 randomAgain:buildTilePreviewModel(exact,rich,'random-repeat'),
 brushAgain:buildTilePreviewModel(exact,rich,'terrain-brush'),
 fits:[fitTilePreview(96,64,320,180),fitTilePreview(640,360,320,180),fitTilePreview(101,50,307,180)]
}};
process.stdout.write(JSON.stringify(result));
"""
    proc = subprocess.run(["node", "-e", script], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_budget_guard_rejects_unsafe_overflow_and_excessive_work_before_scan():
    budget = re.search(r"const TILE_PREVIEW_BUDGETS = Object\.freeze\(\{[^;]+;", JS, re.S).group(0)
    functions = "\n".join(_function_source(n) for n in ("validateTilePreviewBudget", "analyzeTileAtlasImageData"))
    script = f"""{budget}\n{functions}
const base={{tile_size:{{width:8,height:8}},rows:1,columns:1,margin:0,spacing:0}};
const cases=[()=>validateTilePreviewBudget(Infinity,1,base),()=>validateTilePreviewBudget(8,8,{{...base,rows:Number.MAX_SAFE_INTEGER,columns:2}}),()=>validateTilePreviewBudget(8,8,{{...base,rows:64,columns:65}}),()=>validateTilePreviewBudget(8,8,{{...base,tile_size:{{width:4096,height:4096}},rows:8,columns:8}}),()=>validateTilePreviewBudget(5000,5000,base)];
let reads=0;const hostile={{width:5000,height:5000,get data(){{reads++;throw Error('scan happened')}}}};let analysis='';try{{analyzeTileAtlasImageData(hostile,base)}}catch(e){{analysis=e.message}}
const errors=cases.map(fn=>{{try{{fn();return ''}}catch(e){{return e.message}}}});process.stdout.write(JSON.stringify({{errors,reads,analysis,ok:validateTilePreviewBudget(128,128,{{...base,rows:4,columns:4}},'random-repeat')}}));"""
    proc = subprocess.run(["node", "-e", script], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert all(message.startswith("tile preview budget:") for message in result["errors"])
    assert result["reads"] == 0 and result["analysis"].startswith("tile preview budget:")
    assert result["ok"]["cellCount"] == 16


def test_browser_preflight_precedes_canvas_allocation_and_pixel_readback():
    source = _function_source("buildTileAtlasPreview")
    guard = source.index("validateTilePreviewBudget(sw,sh,contract,mode)")
    assert guard < source.index("document.createElement('canvas')") < source.index("getImageData")


def test_declared_grid_exact_slicing_and_low_alpha_significance(runtime):
    qa = runtime["exact"]
    assert qa["footprint"] == {"width": 7, "height": 4}
    assert [(c["index"], c["x"], c["y"], c["width"], c["height"]) for c in qa["cells"]] == [(0, 1, 1, 2, 2), (1, 4, 1, 2, 2)]
    assert qa["metrics"]["outOfGrid"] == 1  # alpha=1 gutter pixel is significant
    assert qa["reasons"] == ["out-of-grid"] and qa["status"] == "WARN"


def test_all_seven_preview_models_have_exact_ids_dimensions_and_semantics(runtime):
    m = runtime["models"]
    assert list(m) == MODES and all(m[k]["mode"] == k for k in MODES)
    assert (m["source"]["width"], m["source"]["height"], m["source"]["sequence"]) == (7, 4, [0, 1])
    assert (m["repeat-3x3"]["columns"], m["repeat-3x3"]["rows"], m["repeat-3x3"]["sequence"]) == (3, 3, [0] * 9)
    for mode in ("random-repeat", "terrain-brush"):
        assert (m[mode]["columns"], m[mode]["rows"], len(m[mode]["sequence"])) == (12, 8, 96)
        assert (m[mode]["width"], m[mode]["height"]) == (24, 16)
    assert m["rule-coverage"]["sequence"] == [0, 1]
    assert m["rule-coverage"]["overlays"] == ["grass", "shore", "edge", "inner-corner", "outer-corner"]
    assert m["overlay"]["overlays"] == ["collision", "occlusion", "navigation"]
    assert [v["id"] for v in m["variant-distribution"]["overlays"]] == ["zero", "neg", "good", "more"]


def test_preview_models_are_distinct_and_repeated_calls_byte_identical(runtime):
    m = runtime["models"]
    assert m["random-repeat"] == runtime["randomAgain"]
    assert m["terrain-brush"] == runtime["brushAgain"]
    signatures = {(v["mode"], v["width"], v["height"], json.dumps(v["sequence"]), json.dumps(v["overlays"], sort_keys=True)) for v in m.values()}
    assert len(signatures) == 7
    assert m["random-repeat"]["sequence"] != m["terrain-brush"]["sequence"]


def test_preview_fit_uses_integer_upscale_fractional_downscale_and_centering(runtime):
    upscale, downscale, bounded = runtime["fits"]
    assert upscale == {"x": 64, "y": 26, "width": 192, "height": 128, "scale": 2}
    assert downscale == {"x": 0, "y": 0, "width": 320, "height": 180, "scale": .5}
    assert bounded == {"x": 2, "y": 15, "width": 303, "height": 150, "scale": 3}
    viewport_widths = (320, 320, 307)
    assert all(f["x"] >= 0 and f["y"] >= 0 and f["width"] <= viewport_widths[i] and f["height"] <= 180 for i, f in enumerate(runtime["fits"]))


def test_preview_renderer_is_crisp_centered_and_qa_summary_wraps():
    preview = _function_source("buildTileAtlasPreview")
    assert "fitTilePreview(model.width,model.height,viewportWidth,viewportHeight)" in preview
    assert "ctx.imageSmoothingEnabled=false" in preview and "ctx.clearRect(0,0,out.width,out.height)" in preview
    assert "ctx.drawImage(preview,fit.x,fit.y,fit.width,fit.height)" in preview
    match = re.search(r"\.tile-qa-summary\s*\{([^}]*)\}", CSS)
    assert match
    rule = match.group(1).replace(" ", "")
    for declaration in ("white-space:pre-wrap", "overflow-wrap:anywhere", "max-width:100%", "overflow-x:hidden", "line-height:1.45"):
        assert declaration in rule


def test_qa_seams_corners_duplicates_and_reason_tokens(runtime):
    seam = runtime["seam"]
    assert seam["metrics"]["seamComparisons"] == 4
    assert seam["metrics"]["seamMismatch"] == 4 and seam["metrics"]["seamMismatchRate"] == 1
    assert seam["status"] == "WARN" and "seam-mismatch" in seam["reasons"]
    corner = runtime["corner"]
    assert corner["metrics"]["badCorners"] == 1 and corner["reasons"] == ["bad-corner"]
    dup = runtime["duplicate"]
    assert dup["metrics"]["duplicateCount"] == 1 and dup["metrics"]["duplicateRatio"] == .5
    assert dup["reasons"] == ["repeated-pattern"]


def test_qa_missing_rule_metadata_mismatch_truncation_and_status_precedence(runtime):
    rich = runtime["rich"]
    assert rich["metrics"]["missingRule"] == 3 and "missing-rule" in rich["reasons"]
    assert rich["metrics"]["metadataMismatchCount"] == 3
    assert rich["metadataMismatch"] == ["metadata.collision.indices[1]", "metadata.occlusion.tiles[0]", "metadata.navigation.tile_indices[1]"]
    assert rich["status"] == "FAIL" and "metadata-mismatch" in rich["reasons"]
    trunc = runtime["truncated"]
    assert trunc["footprint"]["width"] == 4 and trunc["metrics"]["missingRule"] == 1
    assert trunc["status"] == "FAIL" and trunc["reasons"][:2] == ["declared-grid-truncated", "missing-rule"]
    assert runtime["exact"]["status"] == "WARN"
    clean = {**runtime["seam"]}
    assert {"PASS", "WARN", "FAIL"} <= {"PASS", runtime["exact"]["status"], rich["status"]}


def test_variant_positive_only_normalization_uniform_fallback_and_no_mutation(runtime):
    assert [v["weight"] for v in runtime["variants"]] == [0, -3, 2, 6]
    assert [v["normalized"] for v in runtime["variants"]] == [0, 0, .25, .75]
    assert [v["normalized"] for v in runtime["fallback"]] == pytest.approx([1/3] * 3)
    assert runtime["mutation"] is True
    fallback_bars = runtime["fallbackModel"]["distributionBars"]
    assert [b["percent"] for b in fallback_bars] == ["33.3%"] * 3
    assert [b["widthRatio"] for b in fallback_bars] == pytest.approx([1/3] * 3)
    bars = runtime["models"]["variant-distribution"]["distributionBars"]
    assert [(b["id"], b["normalized"], b["percent"], b["widthRatio"]) for b in bars] == [
        ("zero", 0, "0.0%", 0), ("neg", 0, "0.0%", 0),
        ("good", .25, "25.0%", .25), ("more", .75, "75.0%", .75),
    ]


def test_static_ui_is_accessible_tile_only_and_wired_to_selected_image_path():
    assert re.search(r'<div id="tilePreviewPanel" class="panel tile-preview-panel hidden" aria-label="타일 맵 사용 미리보기">', HTML)
    assert '<label for="tilePreviewMode">' in HTML
    for mode in MODES: assert f'value="{mode}"' in HTML
    assert all(f'id="{control}"' in HTML for control in ("buildTilePreview", "tilePreviewCanvas", "tileQaSummary"))
    assert "$('tilePreviewPanel')?.classList.toggle('hidden', family !== 'tile')" in JS
    preview = _function_source("buildTileAtlasPreview")
    assert "canvas.getActiveObject()" in preview and "object?._element" in preview and "ix.drawImage(source" in preview
    assert "buildTilePreviewModel(imageData,contract" in preview


def test_preview_runtime_is_read_only_and_has_no_foreign_workflow_or_export():
    source = _function_source("analyzeTileAtlasImageData") + _function_source("buildTilePreviewModel") + _function_source("buildTileAtlasPreview")
    forbidden = ("saveHistory", "history.", "detectSprite", "detectComponent", "actor", "effect", "cleanup", "download", "export", "toDataURL", "toBlob")
    assert not [token for token in forbidden if token.lower() in source.lower()]


def test_contract_document_and_implementation_tokens_agree_exactly():
    for phrase in ("rows × columns", "alpha `> 0`", "duplicate ratio `>= 0.5`", "xorshift32", "all-nonpositive list is uniform", "**FAIL**", "**WARN**", "**PASS**"):
        assert phrase in CONTRACT
    production = _function_source("analyzeTileAtlasImageData") + _function_source("buildTilePreviewModel")
    assert set(re.findall(r"reasons\.push\('([^']+)'\)", production)) == {"declared-grid-truncated", "seam-mismatch", "missing-rule", "bad-corner", "repeated-pattern", "out-of-grid", "metadata-mismatch"}
    assert set(re.findall(r"mode==='([^']+)'", production)) | {"source"} == set(MODES)
