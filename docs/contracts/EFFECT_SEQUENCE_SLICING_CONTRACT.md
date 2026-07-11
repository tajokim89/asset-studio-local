# Effect Sequence Slicing Contract (B3/B4)

This is a test/development contract, not production code. B4 exposes the
deterministic in-process boundary:

```python
server.slice_effect_sequence(png_bytes, grid_contract, *, mode)
```

`grid_contract` is `effect-grid/v1`: declared row-major `rows`, `columns`,
`cell`, `gap`, `frameCount`, timing, normalized source `pivot`, and
`trim_padding`. `trim_padding` defaults to **1 pixel**; `trimPadding` is the
accepted camel-case alias. It expands every non-zero-alpha bbox on all sides and
clamps it to the source-cell envelope. A fully transparent frame uses the safe
rect `{x: 0, y: 0, width: 1, height: 1}`; its encoded pixel remains transparent.

The result is `effect-slices/v1`, with `mode`, structured `validation`, and
ordered `frames`. Each frame semantically requires `order`, duration, encoded
PNG bytes, source size, trim rect, and a source-normalized pivot. Adapters may
use either spelling in these equivalent pairs:

- `schemaVersion` / `schema_version`
- `sourceSize` / `source_size`
- `trimRect` / `trim_rect`
- `pngBytes` / `png_bytes`
- `durationMs` / `duration_ms`

No other response extras are required. Full-cell mode returns each declared
cell exactly. Trim mode returns the padded crop and metadata that reconstructs
the exact RGBA source cell; alpha values 1 through 255 and detached particles
are significant. Frame order, count, pixels, pivot, and source envelope are
strict.

A non-transparent gutter is a validation failure. Its reason may be any stable
code/text containing boundary, gutter, or cross-cell semantics. Metrics must
numerically report gutter alpha and frame-edge contact; accepted names are
`gutterAlphaPixels`/`gutter_alpha_pixels` and
`frameEdgeAlphaPixels`/`frame_edge_alpha_pixels` or
`edgeContactPixels`/`edge_contact_pixels`.
