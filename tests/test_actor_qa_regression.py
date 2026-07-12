from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from PIL import Image

from asset_studio.actor_qa import (
    REQUIRED_VISUAL_CHECKS,
    evaluate_actor_qa,
    evaluate_visual_annotations,
    measure_actor_sheet,
    split_horizontal_frames,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "actor" / "black-orc-se-walk-failure.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class ActorQARegressionTests(unittest.TestCase):
    def test_black_orc_walk_splits_into_six_exact_horizontal_cells(self):
        fixture = load_fixture()
        artifact = ROOT / fixture["artifact_ref"]

        self.assertTrue(artifact.is_file())
        self.assertEqual(
            hashlib.sha256(artifact.read_bytes()).hexdigest(), fixture["artifact_sha256"]
        )
        with Image.open(artifact) as image:
            frames = split_horizontal_frames(image, fixture["frame_count"])

        self.assertEqual(len(frames), 6)
        self.assertEqual([frame.size for frame in frames], [(362, 724)] * 6)

    def test_black_orc_walk_records_geometry_without_anatomy_claims(self):
        fixture = load_fixture()
        metrics = measure_actor_sheet(
            ROOT / fixture["artifact_ref"], frame_count=fixture["frame_count"]
        )

        self.assertEqual(metrics["summary"]["nonempty_frames"], 6)
        self.assertEqual(
            [frame["bbox_center"][0] for frame in metrics["frames"]],
            [209.0, 200.0, 183.5, 171.0, 146.5, 141.5],
        )
        self.assertEqual(
            [frame["root_proxy"][1] for frame in metrics["frames"]],
            [544, 544, 544, 544, 540, 542],
        )
        self.assertAlmostEqual(
            metrics["summary"]["root_proxy_drift_pixels"], 67.5296, places=4
        )
        self.assertEqual(metrics["summary"]["baseline_drift_pixels"], 4)
        self.assertGreater(metrics["summary"]["bbox_area_ratio_delta"], 0.30)
        for actual, expected in zip(
            metrics["summary"]["adjacent_alpha_change_ratios"],
            [0.146094, 0.360014, 0.325272, 0.336630, 0.315299],
        ):
            self.assertAlmostEqual(actual, expected, places=5)
        self.assertAlmostEqual(
            metrics["summary"]["loop_alpha_change_ratio"], 0.631546, places=5
        )
        self.assertFalse(
            any("hand" in key or "foot" in key for key in metrics["summary"])
        )

    def test_cleanup_pass_does_not_hide_anatomy_and_continuity_failure(self):
        fixture = load_fixture()
        manifest = json.loads(
            (ROOT / fixture["result_manifest_ref"]).read_text(encoding="utf-8")
        )

        self.assertIs(manifest["walk_response"]["qa"]["cleanup_qa"]["pass"], True)
        result = evaluate_actor_qa(
            ROOT / fixture["artifact_ref"],
            fixture["manual_visual_annotations"],
            frame_count=fixture["frame_count"],
        )

        self.assertIs(result["pass"], False)
        self.assertIs(result["visual_qa"]["pass"], False)
        failed_visual_checks = {
            reason["check"]
            for reason in result["visual_qa"]["reasons"]
            if reason["code"]
            in {"visual-score-below-minimum", "explicit-visual-defect"}
        }
        self.assertLessEqual(
            {"hand_integrity", "foot_integrity", "joint_coherence"},
            failed_visual_checks,
        )
        self.assertIn("temporal_limb_continuity", failed_visual_checks)
        self.assertLessEqual(
            {
                "root-proxy-drift",
                "contact-baseline-drift",
                "bbox-scale-drift",
                "loop-alpha-change",
            },
            {reason["check"] for reason in result["local_qa"]["reasons"]},
        )

    def test_manual_visual_gate_fails_on_low_score_or_explicit_defect(self):
        annotations = {
            check_id: {"score": 5, "defects": []}
            for check_id in REQUIRED_VISUAL_CHECKS
        }
        low_score = copy.deepcopy(annotations)
        low_score["hand_integrity"]["score"] = 3
        explicit_defect = copy.deepcopy(annotations)
        explicit_defect["foot_integrity"]["defects"] = ["Detached ankle in frame 4."]

        self.assertIs(evaluate_visual_annotations(annotations)["pass"], True)
        self.assertIs(evaluate_visual_annotations(low_score)["pass"], False)
        self.assertIs(evaluate_visual_annotations(explicit_defect)["pass"], False)

    def test_manual_visual_gate_fails_closed_when_review_is_missing(self):
        annotations = {
            check_id: {"score": 5, "defects": []}
            for check_id in REQUIRED_VISUAL_CHECKS
        }
        del annotations["joint_coherence"]

        result = evaluate_visual_annotations(annotations)

        self.assertIs(result["pass"], False)
        self.assertLessEqual(
            {("missing-visual-annotation", "joint_coherence")},
            {(reason["code"], reason["check"]) for reason in result["reasons"]},
        )


if __name__ == "__main__":
    unittest.main()
