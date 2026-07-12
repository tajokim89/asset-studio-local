from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from asset_studio.evaluation import QualityRubricValidationError, validate_quality_rubric
from tests.test_golden_job_fixtures import FIXTURE_DIR, load_fixture


ROOT = Path(__file__).resolve().parents[1]
RUBRIC_PATH = ROOT / "contracts" / "quality-rubric-v1.json"


def load_rubric() -> dict:
    return json.loads(RUBRIC_PATH.read_text(encoding="utf-8"))


def index_by_id(items: list[dict]) -> dict[str, dict]:
    return {item["id"]: item for item in items}


class QualityRubricTests(unittest.TestCase):
    def test_rubric_round_trips_and_fail_closed_policy_is_explicit(self):
        rubric = load_rubric()
        original = copy.deepcopy(rubric)

        validated = validate_quality_rubric(rubric)

        self.assertEqual(validated, original)
        self.assertIsNot(validated, rubric)
        self.assertEqual(rubric["rubric_id"], "quality-rubric-v1")
        self.assertEqual(rubric["decision_policy"]["missing_required_result"], "fail")
        self.assertEqual(rubric["decision_policy"]["any_required_failure"], "fail")
        self.assertTrue(rubric["decision_policy"]["local_failure_blocks_visual_review"])
        self.assertTrue(rubric["decision_policy"]["user_approval_required"])

    def test_every_golden_job_requirement_resolves_to_the_versioned_rubric(self):
        rubric = load_rubric()
        local = index_by_id(rubric["local_checks"])
        visual = index_by_id(rubric["visual_checks"])
        metrics = index_by_id(rubric["metrics"])

        fixture_paths = sorted(FIXTURE_DIR.glob("*.json"))
        self.assertEqual(len(fixture_paths), 6)
        for path in fixture_paths:
            job = load_fixture(path.name)
            with self.subTest(job=job["job_id"]):
                self.assertEqual(job["quality_rubric_version"], rubric["rubric_id"])
                self.assertLessEqual(set(job["required_local_checks"]), set(local))
                self.assertLessEqual(set(job["required_visual_checks"]), set(visual))
                self.assertLessEqual(set(job["required_metrics"]), set(metrics))
                self.assertTrue(
                    all(job["family"] in local[item]["families"] for item in job["required_local_checks"])
                )
                self.assertTrue(
                    all(job["family"] in visual[item]["families"] for item in job["required_visual_checks"])
                )

    def test_sprite_quality_and_edit_cost_have_actionable_thresholds(self):
        rubric = load_rubric()
        local = index_by_id(rubric["local_checks"])
        visual = index_by_id(rubric["visual_checks"])
        metrics = index_by_id(rubric["metrics"])

        self.assertLessEqual(local["pivot-drift"]["parameters"]["max_pixels"], 1)
        for check_id in ("identity-consistency", "action-readability", "loop-naturalness"):
            self.assertGreaterEqual(visual[check_id]["minimum_score"], 4)
        self.assertEqual(metrics["manual-edit-seconds"]["unit"], "seconds")
        self.assertEqual(metrics["manual-edit-seconds"]["direction"], "lower_is_better")
        self.assertEqual(metrics["regenerated-frames"]["direction"], "lower_is_better")

    def test_rubric_rejects_policy_and_threshold_false_passes(self):
        cases = {}
        cases["missing result ignored"] = load_rubric()
        cases["missing result ignored"]["decision_policy"]["missing_required_result"] = "ignore"

        cases["detailed failure ignored"] = load_rubric()
        cases["detailed failure ignored"]["decision_policy"]["any_required_failure"] = "pass"

        cases["visual review runs after local failure"] = load_rubric()
        cases["visual review runs after local failure"]["decision_policy"][
            "local_failure_blocks_visual_review"
        ] = False

        cases["weak identity threshold"] = load_rubric()
        for check in cases["weak identity threshold"]["visual_checks"]:
            if check["id"] == "identity-consistency":
                check["minimum_score"] = 3

        cases["manual edits rewarded"] = load_rubric()
        for metric in cases["manual edits rewarded"]["metrics"]:
            if metric["id"] == "manual-edit-seconds":
                metric["direction"] = "higher_is_better"

        for label, rubric in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(QualityRubricValidationError):
                    validate_quality_rubric(rubric)


if __name__ == "__main__":
    unittest.main()
