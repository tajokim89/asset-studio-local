from __future__ import annotations

import io
import json
import unittest
from typing import Optional

from PIL import Image

from asset_studio.actor_assembler import (
    ActorAssemblyError,
    assemble_actor_canvas_frames,
    assemble_actor_frames,
    assemble_actor_head_locked_frames,
)


def _png(
    size: tuple[int, int],
    bbox: Optional[tuple[int, int, int, int]],
    color: tuple[int, int, int, int] = (80, 120, 160, 255),
) -> bytes:
    image = Image.new("RGBA", size, (7, 255, 9, 0))
    if bbox is not None:
        left, top, right, bottom = bbox
        for y in range(top, bottom):
            for x in range(left, right):
                image.putpixel((x, y), color)
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=9)
    return output.getvalue()


def _image(raw: bytes) -> Image.Image:
    with Image.open(io.BytesIO(raw)) as source:
        source.load()
        return source.convert("RGBA")


def _actor_png(
    *,
    head: tuple[int, int],
    ground_y: int,
    equipment_x: int,
) -> bytes:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    head_x, head_y = head
    for y in range(head_y, head_y + 6):
        for x in range(head_x - 3, head_x + 4):
            image.putpixel((x, y), (230, 190, 140, 255))
    for y in range(head_y + 6, ground_y - 3):
        for x in range(head_x - 5, head_x + 6):
            image.putpixel((x, y), (80, 120, 160, 255))
    for y in range(ground_y - 3, ground_y + 1):
        for x in range(head_x - 6, head_x + 7):
            image.putpixel((x, y), (60, 70, 90, 255))
    for y in range(max(2, head_y - 2), head_y + 18):
        image.putpixel((equipment_x, y), (210, 210, 220, 255))
        image.putpixel((equipment_x + 1, y), (210, 210, 220, 255))
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=9)
    return output.getvalue()


def _pixels(image: Image.Image):
    flattened = getattr(image, "get_flattened_data", None)
    return flattened() if callable(flattened) else tuple(image.getdata())


class ActorAssemblerTests(unittest.TestCase):
    def test_default_cell_is_512_with_sixteen_pixel_padding(self):
        result = assemble_actor_frames((_png((8, 8), (2, 2, 6, 6)),))

        self.assertEqual([512, 512], result["geometry"]["cell_size"])
        self.assertEqual(16, result["geometry"]["padding"])
        self.assertEqual([256, 495], result["geometry"]["root_pixel"])
        self.assertEqual((512, 512), _image(result["sheet_png"]).size)

    def test_disparate_frames_use_one_scale_and_fixed_bottom_center_root(self):
        frames = (
            _png((12, 11), (2, 2, 8, 9), (190, 30, 40, 255)),
            _png((20, 16), (5, 3, 15, 13), (30, 80, 210, 255)),
        )

        result = assemble_actor_frames(
            frames,
            cell_size=32,
            padding=4,
        )

        self.assertEqual(len(result["normalized_frame_pngs"]), 2)
        normalized = [_image(raw) for raw in result["normalized_frame_pngs"]]
        self.assertEqual([(32, 32), (32, 32)], [image.size for image in normalized])
        self.assertEqual((64, 32), _image(result["sheet_png"]).size)

        geometry = result["geometry"]
        self.assertEqual("asset-studio.actor-assembly/v1", geometry["schema_version"])
        self.assertEqual("horizontal", geometry["layout"])
        self.assertEqual([32, 32], geometry["cell_size"])
        self.assertEqual([64, 32], geometry["sheet_size"])
        self.assertEqual([16, 27], geometry["root_pixel"])
        self.assertEqual(
            {"numerator": 12, "denominator": 5, "value": 2.4},
            geometry["common_scale"],
        )
        self.assertEqual(
            [[2, 2, 8, 9], [5, 3, 15, 13]],
            [frame["source_alpha_bbox"] for frame in geometry["frames"]],
        )
        self.assertEqual(
            [[9, 11, 23, 28], [4, 4, 28, 28]],
            [frame["normalized_alpha_bbox"] for frame in geometry["frames"]],
        )
        self.assertEqual(
            [[14, 17], [24, 24]],
            [frame["placed_size"] for frame in geometry["frames"]],
        )
        self.assertTrue(
            all(frame["root_pixel"] == [16, 27] for frame in geometry["frames"])
        )
        self.assertIn(
            '"schema_version": "asset-studio.actor-assembly/v1"',
            json.dumps(geometry, sort_keys=True),
        )

    def test_sheet_cells_match_normalized_frames_and_preserve_order(self):
        result = assemble_actor_frames(
            (
                _png((8, 8), (2, 2, 6, 6), (255, 0, 0, 255)),
                _png((8, 8), (2, 2, 6, 6), (0, 0, 255, 255)),
            ),
            cell_size=16,
            padding=2,
        )

        sheet = _image(result["sheet_png"])
        expected = [_image(raw) for raw in result["normalized_frame_pngs"]]

        self.assertEqual(
            expected[0].tobytes(),
            sheet.crop((0, 0, 16, 16)).tobytes(),
        )
        self.assertEqual(
            expected[1].tobytes(),
            sheet.crop((16, 0, 32, 16)).tobytes(),
        )
        self.assertEqual((255, 0, 0, 255), sheet.getpixel((8, 8)))
        self.assertEqual((0, 0, 255, 255), sheet.getpixel((24, 8)))

    def test_outputs_are_deterministic_nearest_neighbor_and_zero_hidden_rgb(self):
        source = _png((10, 10), (2, 2, 8, 8), (19, 73, 201, 255))

        first = assemble_actor_frames((source,), cell_size=31, padding=3)
        second = assemble_actor_frames((source,), cell_size=31, padding=3)

        self.assertEqual(first, second)
        for raw in (*first["normalized_frame_pngs"], first["sheet_png"]):
            image = _image(raw)
            pixels = _pixels(image)
            opaque_colors = {pixel[:3] for pixel in pixels if pixel[3] > 0}
            self.assertEqual({(19, 73, 201)}, opaque_colors)
            self.assertTrue(
                all(pixel == (0, 0, 0, 0) for pixel in pixels if pixel[3] == 0)
            )

    def test_empty_frame_fails_closed(self):
        with self.assertRaisesRegex(ActorAssemblyError, "frame 1.*empty"):
            assemble_actor_frames(
                (
                    _png((8, 8), (2, 2, 6, 6)),
                    _png((8, 8), None),
                ),
                cell_size=16,
                padding=2,
            )

    def test_source_alpha_touching_any_edge_fails_closed(self):
        touching = (
            (0, 2, 5, 6),
            (2, 0, 6, 5),
            (3, 2, 8, 6),
            (2, 3, 6, 8),
        )

        for bbox in touching:
            with self.subTest(bbox=bbox):
                with self.assertRaisesRegex(ActorAssemblyError, "touches source edge"):
                    assemble_actor_frames(
                        (_png((8, 8), bbox),),
                        cell_size=16,
                        padding=2,
                    )

    def test_excessive_downscale_fails_but_explicit_threshold_can_allow_it(self):
        source = _png((102, 102), (1, 1, 101, 101))

        with self.assertRaisesRegex(ActorAssemblyError, "common scale.*minimum"):
            assemble_actor_frames((source,), cell_size=32, padding=4)

        result = assemble_actor_frames(
            (source,),
            cell_size=32,
            padding=4,
            min_scale=0.20,
        )
        self.assertEqual(
            {"numerator": 6, "denominator": 25, "value": 0.24},
            result["geometry"]["common_scale"],
        )

    def test_invalid_inputs_fail_before_allocating_output(self):
        cases = (
            ((), {}, "at least one"),
            ((b"not a png",), {}, "valid PNG"),
            ((_png((8, 8), (2, 2, 6, 6)),), {"cell_size": 0}, "cell_size"),
            (
                (_png((8, 8), (2, 2, 6, 6)),),
                {"cell_size": 16, "padding": 8},
                "padding",
            ),
            (
                (_png((8, 8), (2, 2, 6, 6)),),
                {"min_scale": True},
                "min_scale",
            ),
        )

        for frames, options, message in cases:
            with self.subTest(options=options, message=message):
                with self.assertRaisesRegex((ActorAssemblyError, TypeError), message):
                    assemble_actor_frames(frames, **options)

    def test_canvas_alignment_preserves_horizontal_drift_without_recentering(self):
        result = assemble_actor_canvas_frames(
            (
                _png((12, 10), (2, 2, 6, 8), (190, 30, 40, 255)),
                _png((12, 10), (4, 2, 8, 8), (190, 30, 40, 255)),
            ),
            cell_size=32,
            padding=4,
        )

        geometry = result["geometry"]
        first, second = geometry["frames"]
        self.assertEqual("preserve-source-canvas", geometry["alignment"])
        self.assertTrue(geometry["drift_preserved"])
        self.assertEqual([12, 10], geometry["source_size"])
        self.assertEqual(
            {
                "scale": {"numerator": 2, "denominator": 1, "value": 2.0},
                "resized_source_size": [24, 20],
                "offset": [4, 8],
                "resampling": "nearest-neighbor",
            },
            geometry["common_transform"],
        )
        self.assertEqual([8, 12, 16, 24], first["normalized_alpha_bbox"])
        self.assertEqual([12, 12, 20, 24], second["normalized_alpha_bbox"])
        self.assertEqual([12.0, 23], first["root_proxy"])
        self.assertEqual([16.0, 23], second["root_proxy"])
        self.assertEqual(
            4,
            second["normalized_alpha_bbox"][0]
            - first["normalized_alpha_bbox"][0],
        )
        self.assertEqual(4.0, second["root_proxy"][0] - first["root_proxy"][0])
        self.assertNotEqual(
            first["normalized_alpha_bbox"], second["normalized_alpha_bbox"]
        )

    def test_canvas_alignment_requires_identical_source_canvas_sizes(self):
        with self.assertRaisesRegex(ActorAssemblyError, "source canvas size mismatch"):
            assemble_actor_canvas_frames(
                (
                    _png((12, 10), (2, 2, 6, 8)),
                    _png((13, 10), (2, 2, 6, 8)),
                ),
                cell_size=32,
                padding=4,
            )

    def test_canvas_alignment_keeps_empty_and_edge_touch_fail_closed(self):
        cases = (
            ((_png((8, 8), None),), "empty"),
            ((_png((8, 8), (0, 2, 5, 6)),), "touches source edge"),
        )

        for frames, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ActorAssemblyError, message):
                    assemble_actor_canvas_frames(
                        frames,
                        cell_size=16,
                        padding=2,
                    )

    def test_canvas_alignment_is_deterministic_and_zeroes_transparent_rgb(self):
        frames = (
            _png((10, 10), (2, 2, 8, 8), (19, 73, 201, 255)),
            _png((10, 10), (3, 2, 9, 8), (19, 73, 201, 255)),
        )

        first = assemble_actor_canvas_frames(frames, cell_size=31, padding=3)
        second = assemble_actor_canvas_frames(frames, cell_size=31, padding=3)

        self.assertEqual(first, second)
        for raw in (*first["normalized_frame_pngs"], first["sheet_png"]):
            pixels = _pixels(_image(raw))
            self.assertTrue(
                all(pixel == (0, 0, 0, 0) for pixel in pixels if pixel[3] == 0)
            )

    def test_walk_alignment_locks_head_and_ground_while_ignoring_side_equipment(self):
        result = assemble_actor_head_locked_frames(
            (
                _actor_png(head=(32, 8), ground_y=54, equipment_x=7),
                _actor_png(head=(35, 12), ground_y=50, equipment_x=52),
            ),
            cell_size=64,
            padding=4,
        )

        geometry = result["geometry"]
        self.assertEqual("head-and-ground-lock", geometry["alignment"])
        self.assertFalse(geometry["drift_preserved"])
        self.assertEqual("dense-central-alpha-v1", geometry["head_lock"]["detector"])
        target_head = geometry["head_lock"]["target_normalized_head_anchor"]
        target_ground = geometry["head_lock"]["target_normalized_ground_y"]
        self.assertTrue(all(
            abs(frame["normalized_head_anchor"][0] - target_head[0]) <= 2
            and abs(frame["normalized_head_anchor"][1] - target_head[1]) <= 2
            and abs(frame["normalized_ground_y"] - target_ground) <= 2
            for frame in geometry["frames"]
        ))
        self.assertNotEqual(
            geometry["frames"][0]["head_root_normalization"]["scale"],
            geometry["frames"][1]["head_root_normalization"]["scale"],
        )


if __name__ == "__main__":
    unittest.main()
