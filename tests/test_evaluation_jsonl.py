from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from asset_studio.evaluation import (
    EvaluationLogError,
    append_evaluation_run,
    read_evaluation_runs,
)
from tests.test_evaluation_run_contract import valid_run


class EvaluationJsonlTests(unittest.TestCase):
    def test_append_preserves_existing_bytes_and_reader_round_trips(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "evaluation" / "runs.jsonl"
            first = valid_run()
            second = copy.deepcopy(first)
            second["run_id"] = "run-static-object-002"
            second["started_at"] = "2026-07-12T01:01:00Z"
            second["finished_at"] = "2026-07-12T01:01:01Z"
            second["user_decision"]["decided_at"] = "2026-07-12T01:01:02Z"

            self.assertEqual(append_evaluation_run(path, first), 1)
            first_bytes = path.read_bytes()
            self.assertEqual(append_evaluation_run(path, second), 2)

            self.assertTrue(path.read_bytes().startswith(first_bytes))
            self.assertEqual(read_evaluation_runs(path), [first, second])
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0], json.dumps(first, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")))

    def test_invalid_or_duplicate_run_is_not_appended(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "runs.jsonl"
            manifest = valid_run()
            append_evaluation_run(path, manifest)
            before = path.read_bytes()

            invalid = copy.deepcopy(manifest)
            invalid["aggregate"] = {"status": "passed", "reasons": []}
            invalid["local_qa"] = {"status": "failed", "checks": [
                {
                    "id": "canvas-size",
                    "status": "failed",
                    "reasons": ["wrong size"],
                    "observations": {"width": 31, "height": 32},
                }
            ]}
            with self.assertRaises(EvaluationLogError):
                append_evaluation_run(path, invalid)
            with self.assertRaises(EvaluationLogError):
                append_evaluation_run(path, manifest)

            self.assertEqual(path.read_bytes(), before)

    def test_corrupt_or_truncated_log_fails_closed_without_repairing_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "runs.jsonl"
            path.write_bytes(b'{"run_id":"truncated"}')
            before = path.read_bytes()

            with self.assertRaises(EvaluationLogError):
                read_evaluation_runs(path)
            with self.assertRaises(EvaluationLogError):
                append_evaluation_run(path, valid_run())

            self.assertEqual(path.read_bytes(), before)

    def test_missing_log_reads_as_empty_without_creating_a_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "missing.jsonl"

            self.assertEqual(read_evaluation_runs(path), [])
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
