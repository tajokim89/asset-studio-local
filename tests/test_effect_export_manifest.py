"""B5 effect-only ZIP export and deterministic browser round-trip acceptance tests."""

from __future__ import annotations

import base64
import io
import json
import subprocess
import zipfile
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
JS_PATH = ROOT / "src" / "main.js"
HTML_PATH = ROOT / "index.html"


def _production_export_source() -> str:
    source = JS_PATH.read_text(encoding="utf-8")
    start = source.index("function sliceEffectImageData(")
    end = source.index("\nfunction effectGridContractFromControls", start)
    zip_start = source.index("let crc32Table")
    zip_end = source.index("\nfunction exportFull", zip_start)
    return source[start:end] + "\n" + source[zip_start:zip_end]


def _run_export(mode: str, *, gutter_alpha: bool = False) -> dict:
    source = _production_export_source()
    script = f"""
{source}
const width = 11, height = 9;
const data = new Uint8ClampedArray(width * height * 4);
const pixel = (x, y, rgba) => data.set(rgba, (y * width + x) * 4);
// Four declared frames. Include alpha 1 and 20 plus tiny detached particles.
pixel(0, 0, [1, 2, 3, 1]); pixel(3, 2, [4, 5, 6, 255]);
pixel(6, 1, [7, 8, 9, 20]); pixel(10, 3, [10, 11, 12, 200]);
pixel(2, 5, [13, 14, 15, 255]); pixel(4, 8, [16, 17, 18, 2]);
pixel(7, 6, [19, 20, 21, 255]); pixel(9, 8, [22, 23, 24, 3]);
if ({str(gutter_alpha).lower()}) pixel(5, 2, [99, 88, 77, 4]);
const imageData = {{ width, height, data }};
const contract = {{ rows: 2, columns: 2, cell: {{ width: 5, height: 4 }}, gap: 1,
  frameCount: 4, trimPadding: 1, pivot: {{ x: .25, y: .75 }} }};
(async () => {{
  try {{
    const first = buildEffectExportPackage(imageData, contract, {json.dumps(mode)}, {{
      effectCategory: 'Particle', loop: 'ping-pong', fps: 20
    }});
    const second = buildEffectExportPackage(imageData, contract, {json.dumps(mode)}, {{
      effectCategory: 'Particle', loop: 'ping-pong', fps: 20
    }});
    const firstBytes = new Uint8Array(await first.zipBlob.arrayBuffer());
    const secondBytes = new Uint8Array(await second.zipBlob.arrayBuffer());
    const roundTrip = await reconstructEffectExportZip(first.zipBlob);
    process.stdout.write(JSON.stringify({{
      manifest: first.manifest,
      names: first.files.map(file => file.name),
      zip_name: first.zipName,
      deterministic: Buffer.from(firstBytes).equals(Buffer.from(secondBytes)),
      zip_base64: Buffer.from(firstBytes).toString('base64'),
      reconstructed: roundTrip.frames.map(frame => Array.from(frame.data)),
      original: sliceEffectImageData(imageData, contract, 'full-cell').frames.map(frame => Array.from(frame.pixels)),
    }}));
  }} catch (error) {{
    process.stdout.write(JSON.stringify({{ error: error.message }}));
  }}
}})();
"""
    completed = subprocess.run(["node", "-e", script], text=True, capture_output=True, check=True)
    return json.loads(completed.stdout)


def _independent_python_round_trip(result: dict) -> tuple[dict, list[bytes], list[str]]:
    """Validate browser output with stdlib ZIP + Pillow, not production JS readers."""
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(result["zip_base64"]))) as archive:
        names = archive.namelist()
        assert names == ["manifest.json", *[f"frame-{i:03}.png" for i in range(4)]]
        assert archive.testzip() is None
        manifest = json.loads(archive.read("manifest.json"))
        source = manifest["source_size"]
        restored: list[bytes] = []
        for frame in manifest["frames"]:
            with Image.open(io.BytesIO(archive.read(frame["file"]))) as image:
                image.load()
                assert image.mode == "RGBA"
                rect = frame["trim_rect"]
                assert image.size == (rect["width"], rect["height"])
                common = Image.new("RGBA", (source["width"], source["height"]), (0, 0, 0, 0))
                common.paste(image, (rect["x"], rect["y"]))
                restored.append(common.tobytes())
    return manifest, restored, names


def _expected_declared_cells() -> list[bytes]:
    """Build the four declared 5x4 cells without calling any production JS."""
    cells = [bytearray(5 * 4 * 4) for _ in range(4)]
    pixels = [
        (0, 0, 0, (1, 2, 3, 1)), (0, 3, 2, (4, 5, 6, 255)),
        (1, 0, 1, (7, 8, 9, 20)), (1, 4, 3, (10, 11, 12, 200)),
        (2, 2, 0, (13, 14, 15, 255)), (2, 4, 3, (16, 17, 18, 2)),
        (3, 1, 1, (19, 20, 21, 255)), (3, 3, 3, (22, 23, 24, 3)),
    ]
    for frame, x, y, rgba in pixels:
        offset = (y * 5 + x) * 4
        cells[frame][offset:offset + 4] = bytes(rgba)
    return [bytes(cell) for cell in cells]


def test_full_cell_manifest_zip_is_deterministic_and_complete():
    result = _run_export("full-cell")
    assert "error" not in result
    manifest = result["manifest"]
    assert manifest["schema_version"] == "asset-studio.effect-sequence/v1"
    assert manifest["kind"] == "effect_sequence"
    assert manifest["effect_category"] == "Particle"
    assert manifest["frame_count"] == 4
    assert manifest["frame_order"] == "row-major"
    assert manifest["source_size"] == {"width": 5, "height": 4}
    assert manifest["logical_frame_size"] == {"width": 5, "height": 4}
    assert (manifest["rows"], manifest["columns"], manifest["cell"], manifest["gap"], manifest["padding"]) == (
        2, 2, {"width": 5, "height": 4}, 1, 1
    )
    assert (manifest["loop"], manifest["fps"], manifest["duration_ms"]) == ("ping-pong", 20, 50)
    assert manifest["pivot"] == {
        "x": 0.25, "y": 0.75,
        "coordinate_convention": "source-normalized-top-left",
    }
    assert manifest["trim_mode"] == "full-cell"
    assert [frame["order"] for frame in manifest["frames"]] == [0, 1, 2, 3]
    assert [frame["file"] for frame in manifest["frames"]] == [f"frame-{i:03}.png" for i in range(4)]
    assert all(frame["duration_ms"] == 50 for frame in manifest["frames"])
    assert all(frame["trim_rect"] == {"x": 0, "y": 0, "width": 5, "height": 4} for frame in manifest["frames"])
    assert result["names"] == ["manifest.json", *[f"frame-{i:03}.png" for i in range(4)]]
    assert result["zip_name"] == "effect-sequence-full-cell.zip"
    assert result["deterministic"] is True
    parsed_manifest, restored, names = _independent_python_round_trip(result)
    assert parsed_manifest == manifest
    assert names == result["names"]
    assert restored == _expected_declared_cells()


def test_trim_metadata_zip_round_trip_preserves_every_rgba_pixel():
    result = _run_export("trim")
    assert "error" not in result
    manifest = result["manifest"]
    assert manifest["trim_mode"] == "trim"
    assert [frame["trim_rect"] for frame in manifest["frames"]] == [
        {"x": 0, "y": 0, "width": 5, "height": 4},
        {"x": 0, "y": 0, "width": 5, "height": 4},
        {"x": 1, "y": 0, "width": 4, "height": 4},
        {"x": 0, "y": 0, "width": 5, "height": 4},
    ]
    assert result["names"] == ["manifest.json", "frame-000.png", "frame-001.png", "frame-002.png", "frame-003.png"]
    assert result["zip_name"] == "effect-sequence-trim-metadata.zip"
    assert result["reconstructed"] == result["original"]
    assert any(frame[index] in range(1, 21) for frame in result["reconstructed"] for index in range(3, len(frame), 4))
    parsed_manifest, restored, names = _independent_python_round_trip(result)
    assert parsed_manifest == manifest
    assert names == result["names"]
    assert restored == _expected_declared_cells()
    assert any(pixel in range(1, 21) for frame in restored for pixel in frame[3::4])


def test_full_cell_zip_round_trip_is_pixel_equivalent_to_declared_grid_cells():
    result = _run_export("full-cell")
    assert result["reconstructed"] == result["original"]


def test_invalid_b4_gutter_validation_blocks_export_with_clear_error():
    result = _run_export("trim", gutter_alpha=True)
    assert "error" in result
    assert "gutter" in result["error"].lower()
    assert "export" in result["error"].lower()


def test_effect_export_controls_and_real_download_path_are_wired():
    html = HTML_PATH.read_text(encoding="utf-8")
    js = JS_PATH.read_text(encoding="utf-8")
    assert 'id="exportEffectFullCellZip"' in html
    assert 'id="exportEffectTrimZip"' in html
    assert "exportEffectSequenceZip('full-cell')" in js
    assert "exportEffectSequenceZip('trim')" in js
    assert "downloadBlob(packageResult.zipBlob, packageResult.zipName)" in js
    assert "syncEffectExportControlsState" in js
    assert "button.disabled" in js
    export_region = js[js.index("async function exportEffectSequenceZip("):js.index("\nfunction playEffectSequencePreview")]
    assert "finally" in export_region
    assert "syncEffectExportControlsState();" in export_region


def test_package_builder_is_effect_only_and_has_no_network_or_component_frames():
    source = _production_export_source()
    package_region = source[source.index("function buildEffectExportPackage("):source.index("let crc32Table")]
    lowered = package_region.lower()
    assert "sliceeffectimagedata" in lowered
    assert "spriteslices" not in lowered
    assert "connected" not in lowered
    assert "actor" not in lowered
    assert "fetch(" not in lowered and "provider" not in lowered and "network" not in lowered


def test_export_budget_rejects_huge_ui_valid_contract_before_pixel_access_or_copy():
    source = _production_export_source()
    script = f"""
{source}
let touched = false;
const fakeData = new Proxy({{ length: 0 }}, {{ get() {{ touched = true; throw new Error('pixel data touched'); }} }});
try {{
  buildEffectExportPackage(
    {{ width: 8192, height: 4096, data: fakeData }},
    {{ rows: 1, columns: 2, cell: {{ width: 4096, height: 4096 }}, gap: 0, frameCount: 2,
       trimPadding: 1, pivot: {{ x: .5, y: .5 }} }}, 'full-cell'
  );
  process.stdout.write(JSON.stringify({{ accepted: true, touched }}));
}} catch (error) {{ process.stdout.write(JSON.stringify({{ error: error.message, touched }})); }}
"""
    completed = subprocess.run(
        ["node", "-e", script], text=True, capture_output=True, check=True, timeout=5
    )
    result = json.loads(completed.stdout)
    assert result["touched"] is False
    assert "export too large" in result["error"].lower()
    assert "requested" in result["error"].lower()
    assert "allowed" in result["error"].lower()


@pytest.mark.parametrize(
    "mutation, expected",
    [
        ("png[24] = 2", "bit depth"),
        ("png[25] = 2", "color type"),
        ("zip[18] ^= 1", "size"),
        ("zip[14] ^= 1", "crc"),
    ],
)
def test_debug_round_trip_parser_rejects_malformed_generated_data(mutation: str, expected: str):
    source = _production_export_source()
    script = f"""
{source}
const rgba = new Uint8ClampedArray([1, 2, 3, 4]);
let png = encodeEffectFramePng(1, 1, rgba);
let zip = new Uint8Array(await buildEffectExportPackage(
  {{ width: 1, height: 1, data: rgba }},
  {{ rows: 1, columns: 1, cell: {{ width: 1, height: 1 }}, frameCount: 1, pivot: {{ x: .5, y: .5 }} }},
  'full-cell'
).zipBlob.arrayBuffer());
{mutation};
try {{
  if ({json.dumps(mutation.startswith('png'))}) decodeEffectFramePng(png);
  else parseEffectStoredZip(zip);
  process.stdout.write(JSON.stringify({{ accepted: true }}));
}} catch (error) {{ process.stdout.write(JSON.stringify({{ error: error.message }})); }}
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script], text=True, capture_output=True, check=True
    )
    result = json.loads(completed.stdout)
    assert expected in result["error"].lower()
