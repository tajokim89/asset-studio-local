from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    marker = f"function {name}"
    start = JS.index(marker)
    brace = JS.index(") {", start) + 2
    depth = 0
    for index in range(brace, len(JS)):
        if JS[index] == "{":
            depth += 1
        elif JS[index] == "}":
            depth -= 1
            if depth == 0:
                return JS[start:index + 1]
    raise AssertionError(f"unterminated function: {name}")


def test_uploaded_photo_keeps_native_pixel_size_while_default_images_still_fit():
    source = _function_source("fitToCanvasObject") + "\n" + _function_source("addImageUrl")
    script = f"""
const canvas = {{width:1024,height:768}};
const added=[];
const addToCanvas=(img,label)=>added.push({{img,label}});
const setStatus=()=>{{}};
const fabric={{Image:{{fromURL(url,callback){{callback({{
  width:1200,height:900,scaleX:99,scaleY:99,
  set(values){{Object.assign(this,values);}}
}});}}}}}};
{source}
(async()=>{{
  const nativeImage=await addImageUrl('native.png','native',{{preserveOriginalSize:true}});
  const fittedImage=await addImageUrl('generated.png','generated');
  process.stdout.write(JSON.stringify({{
    native:{{width:nativeImage.width,height:nativeImage.height,scaleX:nativeImage.scaleX,scaleY:nativeImage.scaleY,left:nativeImage.left,top:nativeImage.top}},
    fitted:{{scaleX:fittedImage.scaleX,scaleY:fittedImage.scaleY}}
  }}));
}})().catch(error=>{{console.error(error);process.exitCode=1;}});
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    result = json.loads(completed.stdout)
    assert result["native"] == {
        "width": 1200, "height": 900,
        "scaleX": 1, "scaleY": 1,
        "left": 512, "top": 384,
    }
    assert result["fitted"]["scaleX"] < 1
    assert result["fitted"]["scaleY"] < 1


def test_file_upload_uses_native_size_option():
    handle_files = _function_source("handleFiles")
    assert "addImageUrl(dataUrl, file.name, { preserveOriginalSize: true })" in handle_files
