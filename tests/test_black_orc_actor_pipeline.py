from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_black_orc_se_actor_set.py"
SPEC = importlib.util.spec_from_file_location("black_orc_actor_pipeline", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


class BlackOrcActorPipelineTests(unittest.TestCase):
    def test_master_is_the_zero_frame_default_and_explicit_selection_is_single(self):
        self.assertEqual((), pipeline.selected_frames("master"))
        self.assertEqual(
            (("walk", 0),),
            pipeline.selected_frames("all", (("walk", 0),)),
        )
        self.assertEqual(3, len(pipeline.selected_frames("pilot")))
        self.assertEqual(16, len(pipeline.selected_frames("all")))

    def test_new_provider_call_is_blocked_until_master_and_prior_frame_visual_qa_pass(self):
        state = {
            "master": {"visual_qa": {"status": "PENDING"}},
            "frames": {},
        }
        with self.assertRaisesRegex(RuntimeError, "Direction Master visual QA"):
            pipeline.require_visual_qa_before_new_call(state)

        state["master"]["visual_qa"]["status"] = "PASS"
        state["frames"] = {
            "idle": {"1": {"visual_qa": {"status": "PENDING"}}}
        }
        with self.assertRaisesRegex(RuntimeError, "idle:1"):
            pipeline.require_visual_qa_before_new_call(state)

        pipeline.require_visual_qa_before_new_call(state, excluding=("idle", 1))

    def test_visual_pass_requires_all_anatomy_checks_and_matching_artifact_digest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "master.png"
            artifact.write_bytes(b"stable-artifact")
            state = {
                "master": {
                    "path": str(artifact),
                    "artifact_sha256": pipeline.file_digest(artifact),
                },
                "frames": {},
            }
            checks = {
                name: "PASS" for name in pipeline.REQUIRED_MASTER_VISUAL_CHECKS
            }
            with mock.patch.object(pipeline, "STATE_PATH", root / "manifest.json"):
                with mock.patch.object(pipeline, "OUT", root):
                    incomplete = dict(checks)
                    incomplete.pop("hand_integrity")
                    with self.assertRaisesRegex(RuntimeError, "missing=.*hand_integrity"):
                        pipeline.record_visual_qa(
                            state,
                            "master",
                            passed=True,
                            checks=incomplete,
                            notes=[],
                        )

                    pipeline.record_visual_qa(
                        state,
                        "master",
                        passed=True,
                        checks=checks,
                        notes=["Both hands and both boots are readable."],
                    )

            self.assertEqual("PASS", state["master"]["visual_qa"]["status"])
            self.assertFalse(state["master"]["export_ready"])

    def test_request_digest_changes_when_blueprint_or_model_changes(self):
        base = {
            "contract": pipeline.PIPELINE_CONTRACT_VERSION,
            "model": "gpt-image-2-high",
            "frame": {"action": "walk", "index": 0},
        }
        changed_model = {**base, "model": "gpt-image-2-medium"}
        changed_frame = {**base, "frame": {"action": "walk", "index": 1}}

        self.assertNotEqual(
            pipeline.canonical_digest(base),
            pipeline.canonical_digest(changed_model),
        )
        self.assertNotEqual(
            pipeline.canonical_digest(base),
            pipeline.canonical_digest(changed_frame),
        )


if __name__ == "__main__":
    unittest.main()
