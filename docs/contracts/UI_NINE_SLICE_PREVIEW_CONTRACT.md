# UI Nine-Slice Preview and QA Contract (D3)

D3 is a deterministic, read-only preview. It does not alter the Fabric canvas,
source RGBA, project history, or provide export/download behavior. Assembly text,
icon, and content are temporary preview overlays only.

## Source and state interpretation

Let the declared frame be `source_size.width × source_size.height` and `N` be the
number of declared states (an empty list is treated as one base state).

* An image exactly one frame is `base-reused`: it is one real base frame, and
  every declared state is explicitly labelled **base reused**. It is not reported
  as distinct state artwork.
* `source_width*N × source_height` is a horizontal strip.
* `source_width × source_height*N` is a vertical strip.
* Every other dimension is `state-size-drift` and **FAIL**.

Frames are indexed in row-major order. Every operation copies all four RGBA
channels; alpha `1` is data, not transparency.

## Bounds and preflight

Before pixel access, typed-array allocation, canvas allocation, or
`getImageData`, source and target dimensions must be positive safe integers no
larger than 16,384. Source and target are each limited to 16,777,216 pixels and
estimated work to 67,108,864 pixels. Arithmetic overflow and targets smaller
than the fixed left+right or top+bottom margins are rejected.

## Rendering and modes

`source`, `guides`, `small`, `medium`, `large`, `assembly`,
`state-comparison`, and `integer-scale` are deterministic. Fixed sizing copies
one source frame without claiming nine-slice behavior. Nine-slice divides the
frame into row-major 3×3 regions. Corners are copied byte-for-byte. Edges and
center independently use `stretch` (nearest-neighbour) or `tile` (origin-locked,
deterministically clipped). Guides draw slice lines plus content-safe and
padding bounds after rendering. Integer scale reports its integer factor and a
`noninteger-target` warning when an explicitly requested target is not divisible
by the source dimensions.

## QA

Statuses have precedence **FAIL**, **WARN**, **PASS**.

* `stretched-corners` (**FAIL**): every RGBA byte in all four output corner
  rectangles is compared with its exact corresponding source byte.
* `non-seamless-tiled-edge` (**WARN**): for tile edge mode, opposite endpoint
  pixels of top/bottom horizontal strips and left/right vertical strips are
  compared. Metrics include comparisons, mismatches, and mismatch rate.
* `safe-area-violation` (**FAIL**): content-safe margins plus padding leave less
  than one pixel in either axis. Assembly placeholders use only that computed
  target rectangle.
* `state-size-drift` (**FAIL**): dimensions match none of the exact layouts above.
* `baked-text-advisory` (**WARN**, heuristic): inside the content area, pixels
  with alpha > 0 and luminance below 48 or above 207 form deterministic
  4-connected components. Components of 2..64 pixels, minimum axis <= 3 and
  maximum axis >= 3 are glyph-like; two or more trigger the advisory. This does
  not change the contract invariant `text_free: true`.
* Integer-scale QA reports the scale and optional `noninteger-target` warning.

The pure debug API exposes `validateUiNineSliceBudget`,
`analyzeUiComponentImageData`, `renderUiNineSliceImageData`, and
`buildUiPreviewModel` through `window.__assetStudioDebug`.
