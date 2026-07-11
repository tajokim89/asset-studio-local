# Tile export contract (C4)

`asset-studio.tile-package/v1` is a deterministic, tile-family-only, ZIP/STORE
package. Entries are ordered: `manifest.json`, `atlas.png`, row-major
`tiles/tile-NNNN.png`, `terrain-mapping.json`, `engine-metadata.json`, followed
by optional `tileset.tsx` and `map.tmx`.

The manifest is canonical JSON and declares family/type, authoritative C2
contract, atlas dimensions, exact margin/spacing geometry, every cell rectangle,
and a CRC32/SHA-256/byte-size inventory for every non-manifest entry. PNG files
are 8-bit RGBA. `atlas.png` preserves every source RGBA pixel, including gutter,
margin, outside-footprint, and alpha 1 pixels; cell files preserve declared
rectangles. The atlas and cell-preservation checks are deliberately separate.

Terrain mapping preserves topology, corners, transitions, terrain types, and
variants without manufacturing engine rule counts. Engine metadata preserves
collision, occlusion, navigation, and custom JSON and records recursive tile
index validation. Square grids additionally receive deterministic Tiled TSX/TMX
compatibility XML; unsupported shapes omit both and add a warning.

Import rejects unsafe paths, duplicate names, malformed/bounded ZIP or PNG,
CRC/checksum/inventory/schema/family/geometry/XML inconsistencies. It rebuilds
the declared placement model from cell PNGs and compares all cell RGBA while
checking the original atlas independently. Import is verification-only and must
not mutate canvas or history. Limits are checked before source pixel access or
archive allocation: 4096 files/cells, 16 Mi source pixels, 64 Mi payload, and
192 Mi estimated working memory. The tile atlas decoder explicitly accepts the
full 16 Mi-pixel export boundary; the shared effect-frame decoder retains its
independent default limit of 8 Mi pixels. ZIP import requires a zero-comment
EOCD exactly at end-of-file and a complete, single-disk, non-ZIP64 central
directory whose names, flags, STORE method, CRCs, sizes, and local offsets match
one-to-one with non-overlapping local entries.