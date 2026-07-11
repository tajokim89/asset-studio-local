# Tile preview and map-use QA (C3)

C3 is read-only and has no export/download behavior. It slices only `rows × columns` cells at `margin + index × (tile_size + spacing)` from the selected atlas. The expected footprint includes both outer margins. Transparent and low-alpha pixels remain exact input data.

## Preview semantics

Source preserves the atlas. 3×3 repeats cell zero. Broad random is a seeded 12×8 placement; terrain brush is a deterministic diagonal/cyclic 12×8 placement. Rule coverage lays declared cells out and labels the implementation-neutral declarations (`terrain_types`, transitions, topology and corner flags); these are declarations, not a 47-tile/blob engine rule. Overlay displays collision, occlusion and navigation declarations without creating geometry. Variant distribution displays normalized weights without mutating metadata: finite positive weights participate, signed zero/nonpositive values display as declared but sample as zero, and an all-nonpositive list is uniform.

The seed is an FNV-1a fold of exact tile hashes followed by xorshift32. Models and repeated renders are identical for identical pixels/contracts.

Variant distribution uses one labeled proportional horizontal bar per variant. Each label is `id + percentage` (one decimal place), and bar width is exactly the model's normalized value. Nonpositive entries therefore show `0.0%` with an empty bar. When all entries are nonpositive, the existing uniform fallback is visible as equal percentages and equal bars.

## Preview safety budgets

Preview validation is read-only and does not clamp or mutate the stored contract. Before source-canvas allocation, pixel readback, or scanning, dimensions and contract geometry must be finite nonnegative safe integers (image/tile/grid dimensions are also positive), and all footprint/work arithmetic must remain safe. The centralized frozen limits are: maximum dimension **16,384**, source pixels **16,777,216**, analyzed tile-pixel work **16,777,216**, declared cells **4,096**, and visible/offscreen preview pixels **4,194,304**. Direct analysis and model callers enforce the same applicable preflight. Rejections begin with `tile preview budget:`.

Grid membership during the alpha scan is O(1) per source pixel: subtract margin, divide by tile-plus-spacing pitch, bounds-check row/column, then check the intra-pitch offsets. This preserves exact gutter, margin, outside-footprint, and alpha `> 0` behavior.

## QA

* **seam mismatch:** exact RGBA comparison of each tile's left/right and top/bottom edge pixels; rate is mismatches/comparisons.
* **missing rule:** declaration count beyond available cells, plus declarations made impossible by a truncated footprint. No engine-specific tile count is assumed.
* **bad corner:** when either corner flag is declared, each corner RGBA must equal both immediately adjacent edge endpoint pixels (degenerate 1-pixel dimensions compare themselves).
* **repeated pattern:** exact FNV tile hashes; warning at duplicate ratio `>= 0.5` for more than one tile.
* **out of grid:** every alpha `> 0` pixel in margins, spacing/gutters, or outside declared cells. Low alpha is not dropped.
* **metadata mismatch:** recursively validates arrays under known `indices`, `tiles`, or `tile_indices` keys as integer indices in `[0, rows×columns)`.

Truncated grids and metadata mismatch are **FAIL**; any other reason is **WARN**; no reason is **PASS**. Metrics and reason tokens are stable and deterministic.
