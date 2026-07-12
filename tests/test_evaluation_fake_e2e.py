from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.helpers.evaluation_harness import evaluate_golden_job_over_http
from tests.helpers.fake_image_provider import FakeImageProvider
from tests.helpers.http_generation_harness import GenerationHttpHarness
from tests.test_golden_job_fixtures import load_fixture
from tests.test_quality_rubric import load_rubric
from asset_studio.evaluation import read_evaluation_runs


JOB_NAMES = (
    "static-object.json",
    "actor-idle.json",
    "actor-walk.json",
    "actor-attack.json",
    "ui-button.json",
    "vfx-impact.json",
)


class EvaluationFakeE2ETests(unittest.TestCase):
    def test_every_golden_job_crosses_http_provider_qa_and_append_only_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            provider = FakeImageProvider(root / "provider")
            harness = GenerationHttpHarness(provider, root / "generated")
            log_path = root / "evaluation" / "runs.jsonl"
            rubric = load_rubric()

            produced = [
                evaluate_golden_job_over_http(
                    load_fixture(name),
                    rubric,
                    harness,
                    log_path,
                    run_number=index,
                )
                for index, name in enumerate(JOB_NAMES, start=1)
            ]
            recorded = read_evaluation_runs(log_path)

            self.assertEqual(recorded, produced)
            self.assertEqual(len(provider.calls), len(JOB_NAMES))
            self.assertEqual(len(list((root / "generated").glob("*.png"))), len(JOB_NAMES))
            self.assertEqual({record["job_id"] for record in recorded}, {
                "static-object",
                "actor-idle",
                "actor-walk",
                "actor-attack",
                "ui-button",
                "vfx-impact",
            })
            for record in recorded:
                with self.subTest(job=record["job_id"]):
                    self.assertEqual(record["generation"]["status"], "succeeded")
                    self.assertEqual(record["generation"]["call_count"], 1)
                    self.assertEqual(record["local_qa"]["status"], "failed")
                    self.assertEqual(record["visual_qa"]["status"], "not_run")
                    self.assertEqual(record["aggregate"]["status"], "failed")
                    self.assertEqual(record["user_decision"]["status"], "pending")
                    self.assertFalse(Path(record["candidate"]["artifact_ref"]).is_absolute())
                    metrics = {item["id"]: item["value"] for item in record["metrics"]}
                    self.assertTrue(metrics["provider-response-success"])
                    self.assertFalse(metrics["local-qa-pass"])
                    self.assertFalse(metrics["visual-qa-pass"])

            actor_records = [record for record in recorded if record["job_id"].startswith("actor-")]
            for record in actor_records:
                reference_check = next(
                    check
                    for check in record["local_qa"]["checks"]
                    if check["id"] == "required-reference-present"
                )
                self.assertEqual(reference_check["status"], "failed")
                self.assertEqual(reference_check["observations"]["sent_reference_count"], 0)


if __name__ == "__main__":
    unittest.main()
