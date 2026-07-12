from __future__ import annotations

import json
import unittest
from pathlib import Path

from asset_studio.evaluation import EvaluationAggregationError, aggregate_evaluation
from tests.test_golden_job_fixtures import load_fixture
from tests.test_quality_rubric import load_rubric


ROOT = Path(__file__).resolve().parents[1]
PHASE25_PATH = ROOT / "docs" / "history" / "artifacts" / "PHASE_25_ACTION_PRESET_GENERATION_RESULTS.json"


def passing_local_results(job: dict) -> dict:
    return {
        check_id: {"passed": True, "reasons": [], "observations": {}}
        for check_id in job["required_local_checks"]
    }


def passing_visual_results(job: dict, score: int = 4) -> dict:
    return {
        check_id: {"score": score, "reasons": [], "observations": {}}
        for check_id in job["required_visual_checks"]
    }


class EvaluationAggregationTests(unittest.TestCase):
    def test_all_required_detail_results_must_pass(self):
        job = load_fixture("actor-walk.json")
        result = aggregate_evaluation(
            job,
            load_rubric(),
            generation_status="succeeded",
            candidate_present=True,
            local_results=passing_local_results(job),
            visual_results=passing_visual_results(job),
        )

        self.assertEqual(result["local_qa"]["status"], "passed")
        self.assertEqual(result["visual_qa"]["status"], "passed")
        self.assertEqual(result["aggregate"], {"status": "passed", "reasons": []})
        self.assertEqual(
            [check["id"] for check in result["local_qa"]["checks"]],
            job["required_local_checks"],
        )
        self.assertTrue(
            all(check["observations"]["score"] == 4 for check in result["visual_qa"]["checks"])
        )

    def test_local_failure_blocks_visual_review_and_aggregate_pass(self):
        job = load_fixture("actor-walk.json")
        local = passing_local_results(job)
        local["support-foot-alternation"] = {
            "passed": False,
            "reasons": ["left foot remains planted in both contact phases"],
            "observations": {"alternations": 0},
        }

        result = aggregate_evaluation(
            job,
            load_rubric(),
            generation_status="succeeded",
            candidate_present=True,
            local_results=local,
            visual_results=passing_visual_results(job, score=5),
        )

        self.assertEqual(result["local_qa"]["status"], "failed")
        self.assertEqual(result["visual_qa"], {"status": "not_run", "checks": []})
        self.assertEqual(result["aggregate"]["status"], "failed")
        self.assertTrue(any("support-foot-alternation" in reason for reason in result["aggregate"]["reasons"]))

    def test_missing_required_result_and_low_visual_score_fail_closed(self):
        job = load_fixture("static-object.json")
        local = passing_local_results(job)
        del local["border-clearance"]

        missing = aggregate_evaluation(
            job,
            load_rubric(),
            generation_status="succeeded",
            candidate_present=True,
            local_results=local,
            visual_results={},
        )
        self.assertEqual(missing["aggregate"]["status"], "failed")
        failed_check = next(
            check for check in missing["local_qa"]["checks"] if check["id"] == "border-clearance"
        )
        self.assertEqual(failed_check["status"], "failed")
        self.assertIn("missing required result", failed_check["reasons"])

        visual = passing_visual_results(job)
        visual["silhouette-readability"]["score"] = 3
        low_score = aggregate_evaluation(
            job,
            load_rubric(),
            generation_status="succeeded",
            candidate_present=True,
            local_results=passing_local_results(job),
            visual_results=visual,
        )
        self.assertEqual(low_score["visual_qa"]["status"], "failed")
        self.assertEqual(low_score["aggregate"]["status"], "failed")

    def test_phase25_nested_cleanup_failure_cannot_be_hidden_by_success_summary(self):
        archive = json.loads(PHASE25_PATH.read_text(encoding="utf-8"))
        walk6 = next(item for item in archive["items"] if item["action"] == "walk6")
        summary_claims_pass = (
            walk6["success"]
            and walk6["cleanup_pass"]
            and archive["cleanup_passes"] == archive["total"]
        )
        nested_pass = walk6["response"]["qa"]["cleanup_qa"]["pass"]
        self.assertTrue(summary_claims_pass)
        self.assertFalse(nested_pass)

        job = load_fixture("actor-walk.json")
        local = passing_local_results(job)
        local["transparent-background"] = {
            "passed": nested_pass,
            "reasons": ["nested cleanup_qa.pass was false"],
            "observations": {
                "residual_dark_border_pixels": walk6["response"]["qa"]["cleanup_qa"][
                    "residual_dark_border_pixels"
                ]
            },
        }
        result = aggregate_evaluation(
            job,
            load_rubric(),
            generation_status="succeeded",
            candidate_present=True,
            local_results=local,
            visual_results=passing_visual_results(job, score=5),
        )

        self.assertEqual(result["aggregate"]["status"], "failed")
        self.assertEqual(result["visual_qa"]["status"], "not_run")

    def test_unknown_result_id_is_rejected_instead_of_silently_ignored(self):
        job = load_fixture("static-object.json")
        local = passing_local_results(job)
        local["lucky-score"] = {"passed": True, "reasons": [], "observations": {}}

        with self.assertRaises(EvaluationAggregationError):
            aggregate_evaluation(
                job,
                load_rubric(),
                generation_status="succeeded",
                candidate_present=True,
                local_results=local,
                visual_results=passing_visual_results(job),
            )

    def test_generation_failure_or_missing_candidate_never_enters_qa(self):
        job = load_fixture("static-object.json")
        for generation_status, candidate_present in (
            ("failed", False),
            ("not_called", False),
            ("succeeded", False),
        ):
            with self.subTest(
                generation_status=generation_status,
                candidate_present=candidate_present,
            ):
                result = aggregate_evaluation(
                    job,
                    load_rubric(),
                    generation_status=generation_status,
                    candidate_present=candidate_present,
                    local_results=passing_local_results(job),
                    visual_results=passing_visual_results(job, score=5),
                )
                self.assertEqual(result["local_qa"]["status"], "not_run")
                self.assertEqual(result["visual_qa"]["status"], "not_run")
                self.assertEqual(result["aggregate"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
