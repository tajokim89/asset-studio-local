"""Deterministic, provider-free RGBA fixtures for effect-sequence slicing tests.

This module intentionally contains fixture construction and inspection only.  It
is not a fallback implementation of the production slicer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Mapping

from PIL import Image, ImageDraw

RGBA = tuple[int, int, int, int]


@dataclass(frozen=True)
class GridContract:
    rows: int
    columns: int
    cell_width: int
    cell_height: int
    gap: int
    frame_count: int
    duration_ms: int = 50
    pivot: tuple[float, float] = (0.5, 0.75)
    trim_padding: int = 1

    @property
    def sheet_size(self) -> tuple[int, int]:
        return (
            self.columns * self.cell_width + (self.columns - 1) * self.gap,
            self.rows * self.cell_height + (self.rows - 1) * self.gap,
        )

    def cell_box(self, order: int) -> tuple[int, int, int, int]:
        if not 0 <= order < self.frame_count:
            raise IndexError(order)
        row, column = divmod(order, self.columns)
        x = column * (self.cell_width + self.gap)
        y = row * (self.cell_height + self.gap)
        return (x, y, x + self.cell_width, y + self.cell_height)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": "effect-grid/v1",
            "rows": self.rows,
            "columns": self.columns,
            "cell": {"width": self.cell_width, "height": self.cell_height},
            "gap": self.gap,
            "frameCount": self.frame_count,
            "durationMs": self.duration_ms,
            "trim_padding": self.trim_padding,
            "pivot": {"x": self.pivot[0], "y": self.pivot[1], "space": "source-normalized"},
            "order": "row-major",
        }


@dataclass(frozen=True)
class EffectFixture:
    name: str
    image: Image.Image
    grid: GridContract
    expected_trim_rects: tuple[tuple[int, int, int, int], ...]
    tolerance: int = 0
    expected_valid: bool = True
    expected_reason: str | None = None
    expected_metrics: Mapping[str, int] = field(default_factory=dict)

    def png_bytes(self) -> bytes:
        output = BytesIO()
        self.image.save(output, format="PNG", optimize=False, compress_level=9)
        return output.getvalue()

    def source_frame(self, order: int) -> Image.Image:
        return self.image.crop(self.grid.cell_box(order))


def _sheet(grid: GridContract) -> Image.Image:
    return Image.new("RGBA", grid.sheet_size, (0, 0, 0, 0))


def _put_pixel(image: Image.Image, grid: GridContract, frame: int, xy: tuple[int, int], rgba: RGBA) -> None:
    left, top, _, _ = grid.cell_box(frame)
    image.putpixel((left + xy[0], top + xy[1]), rgba)


def _rectangle(
    image: Image.Image,
    grid: GridContract,
    frame: int,
    box: tuple[int, int, int, int],
    rgba: RGBA,
) -> None:
    left, top, _, _ = grid.cell_box(frame)
    x0, y0, x1, y1 = box
    ImageDraw.Draw(image).rectangle((left + x0, top + y0, left + x1, top + y1), fill=rgba)


def alpha_bbox(frame: Image.Image, padding: int = 0) -> tuple[int, int, int, int]:
    """Return a clamped, padded bbox; empty frames use a valid 1x1 crop."""
    alpha = frame.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return (0, 0, 1, 1)
    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(frame.width, right + padding)
    bottom = min(frame.height, bottom + padding)
    return (left, top, right - left, bottom - top)


def _finish(
    name: str,
    image: Image.Image,
    grid: GridContract,
    **kwargs: Any,
) -> EffectFixture:
    rects = tuple(
        alpha_bbox(image.crop(grid.cell_box(index)), grid.trim_padding)
        for index in range(grid.frame_count)
    )
    return EffectFixture(name, image, grid, rects, **kwargs)


def explosion_grow_shrink() -> EffectFixture:
    grid = GridContract(rows=2, columns=3, cell_width=32, cell_height=32, gap=3, frame_count=6)
    image = _sheet(grid)
    radii = (2, 4, 7, 10, 6, 3)
    for index, radius in enumerate(radii):
        _rectangle(image, grid, index, (16 - radius, 16 - radius, 16 + radius, 16 + radius), (255, 82, 18, 255))
        _rectangle(image, grid, index, (14, 14, 18, 18), (255, 236, 88, 255))
        # Two isolated pixels make connected-component count unsuitable as a frame count.
        _put_pixel(image, grid, index, (3 + index, 4), (255, 151, 32, 190))
        _put_pixel(image, grid, index, (27 - index, 27), (255, 220, 96, 90))
    return _finish("explosion-grow-shrink", image, grid)


def core_with_detached_sparks() -> EffectFixture:
    grid = GridContract(1, 3, 28, 28, 2, 3, duration_ms=40)
    image = _sheet(grid)
    for index in range(3):
        _rectangle(image, grid, index, (9 - index, 9 - index, 18 + index, 18 + index), (87, 184, 255, 255))
        for xy, color in (((2, 4 + index), (255, 255, 255, 255)), ((24, 3), (74, 220, 255, 71)), ((23, 24), (126, 88, 255, 13))):
            _put_pixel(image, grid, index, xy, color)
    return _finish("core-detached-sparks", image, grid)


def faint_alpha_glow() -> EffectFixture:
    grid = GridContract(1, 2, 30, 24, 2, 2, duration_ms=60)
    image = _sheet(grid)
    for frame in range(2):
        _rectangle(image, grid, frame, (10, 8, 19, 17), (45, 130, 255, 220))
        for alpha in range(1, 21):
            _put_pixel(image, grid, frame, (2 + (alpha - 1) % 5, 2 + (alpha - 1) // 5), (17, 91, 203, alpha))
        _put_pixel(image, grid, frame, (27, 21), (200, 230, 255, 7))
    return _finish("alpha-1-through-20-glow", image, grid)


def tiny_spark() -> EffectFixture:
    grid = GridContract(1, 1, 24, 24, 4, 1, pivot=(0.5, 0.5))
    image = _sheet(grid)
    _put_pixel(image, grid, 0, (12, 12), (255, 244, 171, 255))
    _put_pixel(image, grid, 0, (2, 3), (255, 93, 20, 18))
    _put_pixel(image, grid, 0, (21, 20), (104, 180, 255, 2))
    return _finish("tiny-spark-below-48px", image, grid)


def boundary_intrusion() -> EffectFixture:
    grid = GridContract(1, 2, 24, 24, 3, 2)
    image = _sheet(grid)
    _rectangle(image, grid, 0, (16, 8, 23, 16), (255, 90, 20, 255))
    _rectangle(image, grid, 1, (0, 7, 7, 15), (70, 170, 255, 255))
    # Exactly one alpha-bearing gutter pixel intrudes beyond frame 0.
    image.putpixel((24, 12), (255, 90, 20, 41))
    _put_pixel(image, grid, 1, (20, 21), (255, 255, 255, 4))
    return _finish(
        "one-pixel-boundary-intrusion",
        image,
        grid,
        expected_valid=False,
        expected_reason="cross-cell-alpha",
        expected_metrics={"gutterAlphaPixels": 1, "frameEdgeAlphaPixels": 18},
    )


def connected_by_trail() -> EffectFixture:
    grid = GridContract(1, 2, 24, 24, 0, 2)
    image = _sheet(grid)
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 16, 16), fill=(212, 77, 255, 255))
    draw.line((16, 12, 31, 12), fill=(255, 156, 245, 180), width=1)
    draw.rectangle((31, 7, 39, 16), fill=(85, 210, 255, 255))
    return _finish("adjacent-frames-connected-by-trail", image, grid)


def trimmed_common_envelope() -> EffectFixture:
    grid = GridContract(1, 3, 36, 30, 2, 3, duration_ms=75, pivot=(0.25, 0.8))
    image = _sheet(grid)
    boxes = ((3, 7, 13, 20), (11, 3, 29, 24), (20, 10, 31, 27))
    for index, box in enumerate(boxes):
        _rectangle(image, grid, index, box, (120 + index * 30, 70, 240 - index * 20, 255))
    # One detached low-alpha particle ensures component count differs from frame count.
    _put_pixel(image, grid, 1, (2, 27), (250, 240, 255, 9))
    return _finish("trimmed-common-source-pivot", image, grid)


def transparent_empty_frame() -> EffectFixture:
    """A sequence with one real frame and one deliberately transparent frame."""
    grid = GridContract(1, 2, 20, 18, 2, 2, duration_ms=90, pivot=(0.4, 0.6))
    image = _sheet(grid)
    _rectangle(image, grid, 0, (0, 0, 8, 8), (205, 114, 255, 255))
    return _finish("transparent-empty-frame", image, grid)


def all_fixtures() -> tuple[EffectFixture, ...]:
    return (
        explosion_grow_shrink(),
        core_with_detached_sparks(),
        faint_alpha_glow(),
        tiny_spark(),
        boundary_intrusion(),
        connected_by_trail(),
        trimmed_common_envelope(),
        transparent_empty_frame(),
    )
