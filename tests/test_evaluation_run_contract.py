from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from asset_studio.evaluation import EvaluationRunValidationError, validate_evaluation_run


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "evaluation-run.schema.json"


def valid_run() -> dict:
    prompt = "small red potion, transparent background, pixel art"
    return {
        "schema_version": "asset-studio.evaluation-run/v1",
        "run_id": "run-static-object-001",
        "job_id": "static-object",
        "recipe_id": "static-transparent-object",
        "output_profile_id": "generic-pixel-object-v1",
        "started_at": "2026-07-12T01:00:00Z",
        "finished_at": "2026-07-12T01:00:01Z",
        "request": {
            "prompt": prompt,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "reference_sha256s": [],
            "parameters": {"aspect_ratio": "square"},
        },
        "generation": {
            "status": "succeeded",
            "call_count": 1,
            "provider": "fake-image-provider",
            "model": "fake-image-v1",
            "error": None,
        },
        "candidate": {
            "candidate_id": "candidate-001",
            "artifact_ref": "artifacts/candidate-001.png",
            "sha256": "b" * 64,
            "media_type": "image/png",
        },
        "postprocess": {
            "pipeline_version": "pixel-postprocess-v1",
            "steps": [
                {"id": "alpha-cleanup", "version": "v1"},
                {"id": "nearest-resize", "version": "v1"},
            ],
        },
        "local_qa": {
            "status": "passed",
            "checks": [
                {
                    "id": "canvas-size",
                    "status": "passed",
                    "reasons": [],
                    "observations": {"width": 32, "height": 32},
                }
            ],
        },
        "visual_qa": {
            "status": "passed",
            "checks": [
                {
                    "id": "pixel-readability",
                    "status": "passed",
                    "reasons": [],
                    "observations": {"score": 4},
                }
            ],
        },
        "aggregate": {"status": "passed", "reasons": []},
        "metrics": [
            {"id": "provider-response-success", "value": True},
            {"id": "local-qa-pass", "value": True},
            {"id": "visual-qa-pass", "value": True},
            {"id": "user-approval", "value": True},
            {"id": "candidates-to-approval", "value": 1},
            {"id": "manual-edit-seconds", "value": 0},
            {"id": "export-contract-match", "value": True},
        ],
        "user_decision": {
            "status": "approved",
            "decided_at": "2026-07-12T01:00:02Z",
            "reason": None,
        },
    }


class EvaluationRunContractTests(unittest.TestCase):
    def test_schema_is_strict_draft_2020_12_and_matches_the_manifest_surface(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"], "https://asset-studio.local/contracts/evaluation-run.schema.json")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(valid_run()))

    def test_valid_manifest_round_trips_without_mutation(self):
        manifest = valid_run()
        original = copy.deepcopy(manifest)

        validated = validate_evaluation_run(manifest)
        encoded = json.dumps(validated, ensure_ascii=False, sort_keys=True)

        self.assertEqual(json.loads(encoded), original)
        self.assertEqual(manifest, original)
        self.assertIsNot(validated, manifest)

    def test_provider_failure_is_preserved_without_becoming_a_qa_pass(self):
        manifest = valid_run()
        manifest["generation"] = {
            "status": "failed",
            "call_count": 1,
            "provider": "fake-image-provider",
            "model": "fake-image-v1",
            "error": {"code": "unavailable", "message": "provider unavailable"},
        }
        manifest["candidate"] = None
        manifest["postprocess"]["steps"] = []
        manifest["local_qa"] = {"status": "not_run", "checks": []}
        manifest["visual_qa"] = {"status": "not_run", "checks": []}
        manifest["aggregate"] = {"status": "failed", "reasons": ["generation failed"]}
        manifest["metrics"] = [
            {"id": "provider-response-success", "value": False},
            {"id": "local-qa-pass", "value": False},
            {"id": "visual-qa-pass", "value": False},
            {"id": "user-approval", "value": False},
            {"id": "candidates-to-approval", "value": None},
            {"id": "manual-edit-seconds", "value": None},
            {"id": "export-contract-match", "value": False},
        ]
        manifest["user_decision"] = {
            "status": "pending",
            "decided_at": None,
            "reason": None,
        }

        self.assertEqual(validate_evaluation_run(manifest), manifest)

    def test_invalid_or_false_pass_manifests_are_rejected(self):
        cases = {}

        cases["more than one generation call"] = valid_run()
        cases["more than one generation call"]["generation"]["call_count"] = 2

        cases["success without candidate"] = valid_run()
        cases["success without candidate"]["candidate"] = None

        cases["provider failure without error"] = valid_run()
        cases["provider failure without error"]["generation"].update(
            {"status": "failed", "error": None}
        )
        cases["provider failure without error"]["candidate"] = None

        cases["provider failure forged as QA pass"] = valid_run()
        cases["provider failure forged as QA pass"]["generation"] = {
            "status": "failed",
            "call_count": 1,
            "provider": "fake-image-provider",
            "model": "fake-image-v1",
            "error": {"code": "unavailable", "message": "provider unavailable"},
        }
        cases["provider failure forged as QA pass"]["candidate"] = None
        cases["provider failure forged as QA pass"]["user_decision"] = {
            "status": "pending",
            "decided_at": None,
            "reason": None,
        }

        cases["visual pass after local failure"] = valid_run()
        cases["visual pass after local failure"]["local_qa"] = {
            "status": "failed",
            "checks": [
                {
                    "id": "canvas-size",
                    "status": "failed",
                    "reasons": ["wrong size"],
                    "observations": {"width": 31, "height": 32},
                }
            ],
        }

        cases["aggregate hides detailed failure"] = copy.deepcopy(
            cases["visual pass after local failure"]
        )
        cases["aggregate hides detailed failure"]["visual_qa"] = {
            "status": "not_run",
            "checks": [],
        }

        cases["approval before aggregate pass"] = valid_run()
        cases["approval before aggregate pass"]["aggregate"] = {
            "status": "pending",
            "reasons": [],
        }

        cases["failed check without reason"] = valid_run()
        cases["failed check without reason"]["local_qa"] = {
            "status": "failed",
            "checks": [
                {
                    "id": "canvas-size",
                    "status": "failed",
                    "reasons": [],
                    "observations": {"width": 31, "height": 32},
                }
            ],
        }

        cases["unsafe artifact path"] = valid_run()
        cases["unsafe artifact path"]["candidate"]["artifact_ref"] = "../outside.png"

        cases["malformed digest"] = valid_run()
        cases["malformed digest"]["request"]["prompt_sha256"] = "not-a-digest"

        cases["mismatched prompt digest"] = valid_run()
        cases["mismatched prompt digest"]["request"]["prompt_sha256"] = "c" * 64

        cases["unknown top-level field"] = valid_run()
        cases["unknown top-level field"]["lucky_score"] = 100

        cases["non-finite metric"] = valid_run()
        cases["non-finite metric"]["metrics"][4]["value"] = float("nan")

        for label, manifest in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(EvaluationRunValidationError):
                    validate_evaluation_run(manifest)


if __name__ == "__main__":
    unittest.main()
