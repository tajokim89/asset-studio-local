"""B3 RED tests for deterministic, declared-grid effect sequence slicing.

The non-production B4 helper boundary and its flexible semantic schema are
ratified in ``docs/contracts/EFFECT_SEQUENCE_SLICING_CONTRACT.md``.

Missing production behavior is reported as deliberate assertion failures, not
collection/import/fixture errors. Fixture self-tests remain green independently.
"""

from __future__ import annotations

from collections import deque
from io import BytesIO
from pathlib import Path
import json
import subprocess
import sys
from typing import Any

import pytest
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

import server  # noqa: E402
from helpers.effect_fixture_factory import (  # noqa: E402
    EffectFixture,
    all_fixtures,
    boundary_intrusion,
    connected_by_trail,
    core_with_detached_sparks,
    explosion_grow_shrink,
    faint_alpha_glow,
    tiny_spark,
    transparent_empty_frame,
    trimmed_common_envelope,
)


def _component_count(image: Image.Image) -> int:
    """Test-only diagnostic proving components do not encode logical frames."""
    alpha = image.getchannel("A")
    occupied = {(x, y) for y in range(image.height) for x in range(image.width) if alpha.getpixel((x, y))}
    count = 0
    while occupied:
        count += 1
        queue = deque([occupied.pop()])
        while queue:
            x, y = queue.popleft()
            for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if point in occupied:
                    occupied.remove(point)
                    queue.append(point)
    return count


def _rgba(png_bytes: Any, context: str) -> Image.Image:
    assert isinstance(png_bytes, (bytes, bytearray)), f"{context} must be PNG bytes"
    try:
        image = Image.open(BytesIO(bytes(png_bytes)))
        image.load()
    except Exception as exc:  # Pillow exception types vary by release.
        pytest.fail(f"{context} is not a decodable PNG: {exc}", pytrace=False)
    return image.convert("RGBA")


def _assert_pixels_equal(actual: Image.Image, expected: Image.Image, tolerance: int) -> None:
    assert actual.size == expected.size
    difference = ImageChops.difference(actual, expected)
    extrema = difference.getextrema()
    assert isinstance(extrema, tuple) and all(isinstance(item, tuple) for item in extrema)
    maximum = max(int(item[1]) for item in extrema)
    assert maximum <= tolerance, f"RGBA reconstruction differs by {maximum}; tolerance={tolerance}"


def _field(mapping: dict[str, Any], *aliases: str, context: str = "field") -> Any:
    """Read one documented spelling without requiring unrelated response keys."""
    present = [name for name in aliases if name in mapping]
    assert present, f"{context} must provide one of {aliases!r}"
    value = mapping[present[0]]
    assert all(mapping[name] == value for name in present[1:]), f"conflicting aliases for {context}"
    return value


def _frames(result: dict[str, Any]) -> list[dict[str, Any]]:
    frames = _field(result, "frames", context="result frames")
    assert isinstance(frames, list), "result.frames must be a list"
    return frames


def _trim_rect(frame: dict[str, Any]) -> dict[str, int]:
    rect = _field(frame, "trimRect", "trim_rect", context="frame trim rect")
    assert isinstance(rect, dict)
    return rect


def _png_bytes(frame: dict[str, Any]) -> bytes | bytearray:
    return _field(frame, "pngBytes", "png_bytes", context="frame PNG bytes")


def _metric(metrics: dict[str, Any], *aliases: str) -> int:
    value = _field(metrics, *aliases, context="boundary metric")
    assert isinstance(value, int) and not isinstance(value, bool)
    return value


def _reconstruct_trimmed(frame: dict[str, Any], context: str) -> Image.Image:
    source_size = _field(frame, "sourceSize", "source_size", context="frame source size")
    rect = _trim_rect(frame)
    trimmed = _rgba(_png_bytes(frame), context)
    assert trimmed.size == (rect["width"], rect["height"])
    reconstructed = Image.new(
        "RGBA", (source_size["width"], source_size["height"]), (0, 0, 0, 0)
    )
    reconstructed.paste(trimmed, (rect["x"], rect["y"]))
    return reconstructed


def _production_slicer():
    slicer = getattr(server, "slice_effect_sequence", None)
    assert callable(slicer), (
        "B3 RED: implement public server.slice_effect_sequence(png_bytes, grid_contract, *, mode) "
        "with the effect-slices/v1 result documented in docs/contracts/EFFECT_SEQUENCE_SLICING_CONTRACT.md"
    )
    return slicer


def _slice(fixture: EffectFixture, mode: str) -> dict[str, Any]:
    result = _production_slicer()(fixture.png_bytes(), fixture.grid.as_dict(), mode=mode)
    assert isinstance(result, dict), "slice_effect_sequence must return a dict"
    assert _field(result, "schemaVersion", "schema_version", context="result schema") == "effect-slices/v1"
    assert result.get("mode") == mode
    validation = result.get("validation")
    assert isinstance(validation, dict), "result.validation must be structured"
    assert isinstance(validation.get("metrics"), dict), "validation.metrics must be a dict"
    return result


def _assert_common_frame_metadata(frame: dict[str, Any], fixture: EffectFixture, order: int) -> None:
    grid = fixture.grid
    assert frame["order"] == order
    assert _field(frame, "durationMs", "duration_ms", context="frame duration") == grid.duration_ms
    assert _field(frame, "sourceSize", "source_size", context="frame source size") == {
        "width": grid.cell_width,
        "height": grid.cell_height,
    }
    assert frame["pivot"] == {
        "x": grid.pivot[0],
        "y": grid.pivot[1],
        "space": "source-normalized",
    }


# -------------------------- fixture factory (GREEN now) --------------------------


@pytest.mark.parametrize("fixture", all_fixtures(), ids=lambda item: item.name)
def test_fixture_is_deterministic_rgba_with_fixed_grid(fixture):
    assert fixture.image.mode == "RGBA"
    assert fixture.image.size == fixture.grid.sheet_size
    assert fixture.grid.as_dict()["order"] == "row-major"
    assert fixture.grid.as_dict()["trim_padding"] == 1
    assert len(fixture.expected_trim_rects) == fixture.grid.frame_count
    assert fixture.png_bytes() == {item.name: item.png_bytes() for item in all_fixtures()}[fixture.name]


@pytest.mark.parametrize("fixture", all_fixtures(), ids=lambda item: item.name)
def test_connected_components_are_never_the_declared_frame_count(fixture):
    components = _component_count(fixture.image)
    assert components != fixture.grid.frame_count, (
        f"fixture {fixture.name} accidentally permits component-count slicing: "
        f"components == declared frames == {components}"
    )


def test_fixture_preserves_exact_faint_alpha_and_tiny_rgba_values():
    glow = faint_alpha_glow()
    observed = [glow.source_frame(0).getpixel((2 + (alpha - 1) % 5, 2 + (alpha - 1) // 5)) for alpha in range(1, 21)]
    assert observed == [(17, 91, 203, alpha) for alpha in range(1, 21)]

    spark = tiny_spark().source_frame(0)
    assert spark.getpixel((12, 12)) == (255, 244, 171, 255)
    assert spark.getpixel((2, 3)) == (255, 93, 20, 18)
    assert spark.getpixel((21, 20)) == (104, 180, 255, 2)
    bbox = spark.getbbox()
    assert bbox is not None
    assert bbox[2] - bbox[0] < 48


def test_boundary_fixture_separates_gutter_intrusion_from_frame_edge_contact():
    fixture = boundary_intrusion()
    alpha = fixture.image.getchannel("A")
    gutter = [alpha.getpixel((x, y)) for x in range(24, 27) for y in range(24)]
    cell0_edge = [alpha.getpixel((23, y)) for y in range(24)]
    cell1_edge = [alpha.getpixel((27, y)) for y in range(24)]
    assert sum(int(value) > 0 for value in gutter) == 1
    assert sum(int(value) > 0 for value in cell0_edge + cell1_edge) == 18
    assert fixture.expected_metrics == {"gutterAlphaPixels": 1, "frameEdgeAlphaPixels": 18}


def test_fixture_trim_rects_reconstruct_exact_common_envelope():
    fixture = trimmed_common_envelope()
    for order, (x, y, width, height) in enumerate(fixture.expected_trim_rects):
        source = fixture.source_frame(order)
        cropped = source.crop((x, y, x + width, y + height))
        reconstructed = Image.new("RGBA", source.size, (0, 0, 0, 0))
        reconstructed.paste(cropped, (x, y))
        _assert_pixels_equal(reconstructed, source, fixture.tolerance)


def test_fixture_expected_trim_rect_is_alpha_bbox_plus_clamped_safe_padding():
    for fixture in all_fixtures():
        for order, actual in enumerate(fixture.expected_trim_rects):
            source = fixture.source_frame(order)
            bbox = source.getchannel("A").getbbox()
            if bbox is None:
                assert actual == (0, 0, 1, 1)
                continue
            left, top, right, bottom = bbox
            padding = fixture.grid.trim_padding
            padded_left = max(0, left - padding)
            padded_top = max(0, top - padding)
            padded_right = min(source.width, right + padding)
            padded_bottom = min(source.height, bottom + padding)
            assert actual == (
                padded_left,
                padded_top,
                padded_right - padded_left,
                padded_bottom - padded_top,
            )


# ----------------------- production slicing behavior (RED) -----------------------


def test_public_effect_slicer_interface_exists():
    _production_slicer()


@pytest.mark.parametrize(
    "fixture",
    (explosion_grow_shrink(), core_with_detached_sparks(), connected_by_trail()),
    ids=lambda item: item.name,
)
def test_declared_grid_controls_exact_frame_count_and_row_major_order(fixture):
    result = _slice(fixture, "full-cell")
    assert result["validation"]["ok"] is True
    frames = _frames(result)
    assert len(frames) == fixture.grid.frame_count
    assert [frame["order"] for frame in frames] == list(range(fixture.grid.frame_count))
    # This is the central regression guard: count cannot come from image blobs.
    assert len(frames) != _component_count(fixture.image)


def test_full_cell_mode_preserves_common_dimensions_and_exact_pixels():
    fixture = explosion_grow_shrink()
    result = _slice(fixture, "full-cell")
    assert len(_frames(result)) == 6
    for order, frame in enumerate(_frames(result)):
        _assert_common_frame_metadata(frame, fixture, order)
        assert _trim_rect(frame) == {"x": 0, "y": 0, "width": 32, "height": 32}
        actual = _rgba(_png_bytes(frame), f"full-cell frame {order}")
        _assert_pixels_equal(actual, fixture.source_frame(order), fixture.tolerance)


def test_trim_mode_records_padded_common_envelope_metadata_and_reconstructs():
    fixture = trimmed_common_envelope()
    result = _slice(fixture, "trim")
    assert result["validation"]["ok"] is True
    assert len(_frames(result)) == fixture.grid.frame_count
    for order, frame in enumerate(_frames(result)):
        _assert_common_frame_metadata(frame, fixture, order)
        x, y, width, height = fixture.expected_trim_rects[order]
        assert _trim_rect(frame) == {"x": x, "y": y, "width": width, "height": height}
        reconstructed = _reconstruct_trimmed(frame, f"trimmed frame {order}")
        _assert_pixels_equal(reconstructed, fixture.source_frame(order), fixture.tolerance)


@pytest.mark.parametrize(
    "fixture",
    (faint_alpha_glow(), tiny_spark(), core_with_detached_sparks()),
    ids=lambda item: item.name,
)
def test_trim_preserves_alpha_1_through_20_tiny_sparks_and_detached_particles(fixture):
    result = _slice(fixture, "trim")
    assert result["validation"]["ok"] is True
    for order, frame in enumerate(_frames(result)):
        reconstructed = _reconstruct_trimmed(frame, f"trim low-alpha frame {order}")
        _assert_pixels_equal(reconstructed, fixture.source_frame(order), tolerance=0)


@pytest.mark.parametrize(
    "fixture",
    (explosion_grow_shrink(), faint_alpha_glow(), tiny_spark()),
    ids=lambda item: item.name,
)
def test_same_fixture_full_cell_and_trim_production_round_trip_exactly(fixture):
    full_frames = _frames(_slice(fixture, "full-cell"))
    trim_frames = _frames(_slice(fixture, "trim"))
    assert len(full_frames) == len(trim_frames) == fixture.grid.frame_count
    for order, (full_frame, trim_frame) in enumerate(zip(full_frames, trim_frames)):
        assert full_frame["order"] == trim_frame["order"] == order
        full = _rgba(_png_bytes(full_frame), f"full production frame {order}")
        reconstructed = _reconstruct_trimmed(trim_frame, f"trim production frame {order}")
        _assert_pixels_equal(reconstructed, full, tolerance=0)


def test_transparent_frame_uses_safe_rect_and_clamped_padding_reconstructs_exactly():
    fixture = transparent_empty_frame()
    result = _slice(fixture, "trim")
    frames = _frames(result)
    assert _trim_rect(frames[0]) == {"x": 0, "y": 0, "width": 10, "height": 10}
    assert _trim_rect(frames[1]) == {"x": 0, "y": 0, "width": 1, "height": 1}
    for order, frame in enumerate(frames):
        reconstructed = _reconstruct_trimmed(frame, f"safe padded frame {order}")
        _assert_pixels_equal(reconstructed, fixture.source_frame(order), tolerance=0)


def test_one_pixel_boundary_intrusion_fails_with_structured_reason_and_metrics():
    fixture = boundary_intrusion()
    result = _slice(fixture, "full-cell")
    validation = result["validation"]
    assert validation["ok"] is False
    reason = str(validation.get("reason") or "").lower()
    assert any(term in reason for term in ("boundary", "gutter", "cross-cell", "cross_cell")), (
        "boundary failure reason must describe boundary/gutter/cross-cell semantics"
    )
    metrics = validation["metrics"]
    gutter_alpha = _metric(metrics, "gutterAlphaPixels", "gutter_alpha_pixels")
    edge_contact = _metric(
        metrics,
        "frameEdgeAlphaPixels",
        "frame_edge_alpha_pixels",
        "edgeContactPixels",
        "edge_contact_pixels",
    )
    assert gutter_alpha == fixture.expected_metrics["gutterAlphaPixels"]
    assert edge_contact == fixture.expected_metrics["frameEdgeAlphaPixels"]
    assert gutter_alpha > 0
    assert edge_contact > gutter_alpha, (
        "edge contact is diagnostic context; only gutter alpha is the cross-cell failure"
    )


# ----------------------- B4 browser production behavior -----------------------


def _browser_effect_slicer_source() -> str:
    source = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
    start = source.index("function sliceEffectImageData(")
    end = source.index("\n}\n\nfunction effectGridContractFromControls", start) + 2
    return source[start:end]


def test_browser_declared_grid_trim_common_canvas_pivot_and_low_alpha_runtime():
    """Execute the real pure browser helper, including exact trim reconstruction."""
    function_source = _browser_effect_slicer_source()
    script = f"""
{function_source}
const width = 9, height = 4;
const data = new Uint8ClampedArray(width * height * 4);
function pixel(x, y, rgba) {{ data.set(rgba, (y * width + x) * 4); }}
pixel(0, 0, [11, 22, 33, 1]);
pixel(2, 2, [44, 55, 66, 20]);
pixel(6, 1, [77, 88, 99, 255]);
const contract = {{ rows: 1, columns: 2, cell: {{ width: 4, height: 4 }}, gap: 1,
  frameCount: 2, trimPadding: 1, pivot: {{ x: .25, y: .75 }} }};
const result = sliceEffectImageData({{ width, height, data }}, contract, 'trim');
process.stdout.write(JSON.stringify({{
  count: result.frames.length,
  orders: result.frames.map(frame => frame.order),
  sourceSizes: result.frames.map(frame => frame.sourceSize),
  trimRects: result.frames.map(frame => frame.trimRect),
  pivots: result.frames.map(frame => frame.pivotPixels),
  metrics: result.validation.metrics,
  reconstructed: result.frames.map(frame => Array.from(frame.commonPixels)),
}}));
"""
    completed = subprocess.run(["node", "-e", script], text=True, capture_output=True, check=True)
    result = json.loads(completed.stdout)
    assert result["count"] == 2 and result["orders"] == [0, 1]
    assert result["sourceSizes"] == [{"width": 4, "height": 4}] * 2
    assert result["trimRects"] == [
        {"x": 0, "y": 0, "width": 4, "height": 4},
        {"x": 0, "y": 0, "width": 3, "height": 3},
    ]
    assert result["pivots"] == [{"x": 1, "y": 3}] * 2
    assert result["metrics"]["frameCount"] == 2
    assert result["metrics"]["nonEmptyFrameIndices"] == [0, 1]
    assert result["metrics"]["gutterAlphaPixels"] == 0
    assert result["metrics"]["frameEdgeAlphaPixels"] == 1
    assert result["metrics"]["lowAlphaPixels"] == 2
    assert all(len(frame) == 4 * 4 * 4 for frame in result["reconstructed"])
    assert result["reconstructed"][0][3] == 1
    assert result["reconstructed"][0][(2 * 4 + 2) * 4 + 3] == 20
    assert result["reconstructed"][1][(1 * 4 + 1) * 4 + 3] == 255


def test_effect_only_panel_has_distinct_composite_mode_pivot_overlay_and_qa():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
    css = (ROOT / "styles" / "app.css").read_text(encoding="utf-8")
    assert 'id="effectSequencePreviewPanel"' in html
    assert 'value="effect-only"' in html and 'value="actor-composite"' in html
    assert 'id="effectQaSummary"' in html and 'id="effectPreviewStage"' in html
    assert "previewMode === 'actor-composite'" in js
    assert "effectFrameCanvas(frame, previewMode)" in js
    assert "commonPixels" in js and "pivotPixels" in js
    assert "lowAlphaPixels" in js and "gutterAlphaPixels" in js and "frameEdgeAlphaPixels" in js
    assert ".effect-pivot-crosshair" in css
