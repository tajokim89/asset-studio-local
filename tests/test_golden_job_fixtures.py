from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from asset_studio.evaluation import GoldenJobValidationError, validate_golden_job


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "golden-job.schema.json"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "evaluation"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class GoldenJobFixtureTests(unittest.TestCase):
    def test_golden_job_schema_is_strict_and_versioned(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["properties"]["schema_version"]["const"], "asset-studio.golden-job/v1")
        self.assertFalse(schema["additionalProperties"])

    def test_static_object_fixture_round_trips_as_a_provider_neutral_job(self):
        job = load_fixture("static-object.json")
        original = copy.deepcopy(job)

        validated = validate_golden_job(job)

        self.assertEqual(json.loads(json.dumps(validated, sort_keys=True)), original)
        self.assertEqual(job, original)
        self.assertEqual(job["family"], "object")
        self.assertEqual(job["contract"]["kind"], "static")
        self.assertEqual(job["contract"]["frame_count"], 1)
        self.assertTrue(job["contract"]["transparent_background"])
        self.assertEqual(job["generation"]["development_runs"], 5)
        self.assertGreaterEqual(job["generation"]["release_runs"], 20)
        self.assertNotIn("dungeon-cleanup-inc", json.dumps(job).lower())
        self.assertNotIn("hermes", job["prompt"].lower())

    def test_invalid_static_job_is_rejected(self):
        cases = {}
        cases["multiple static frames"] = load_fixture("static-object.json")
        cases["multiple static frames"]["contract"]["frame_count"] = 2

        cases["missing alpha requirement"] = load_fixture("static-object.json")
        cases["missing alpha requirement"]["contract"]["transparent_background"] = False

        cases["duplicate check"] = load_fixture("static-object.json")
        cases["duplicate check"]["required_local_checks"].append(
            cases["duplicate check"]["required_local_checks"][0]
        )

        cases["unknown field"] = load_fixture("static-object.json")
        cases["unknown field"]["provider"] = "hermes"

        for label, job in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(GoldenJobValidationError):
                    validate_golden_job(job)

    def test_actor_idle_fixture_defines_identity_reference_and_real_motion_beats(self):
        job = load_fixture("actor-idle.json")

        self.assertEqual(validate_golden_job(job), job)
        self.assertEqual(job["family"], "actor")
        self.assertEqual(job["reference"]["mode"], "identity_master")
        self.assertEqual(job["reference"]["continuity_group"], "golden-ranger-v1")
        self.assertEqual(job["contract"]["action"], "idle")
        self.assertTrue(job["contract"]["loop"])
        self.assertEqual(job["contract"]["frame_count"], 4)
        self.assertEqual(
            [beat["id"] for beat in job["contract"]["beats"]],
            ["settle", "breath-rise", "settle-return", "breath-fall"],
        )
        self.assertIn("identity-consistency", job["required_visual_checks"])
        self.assertIn("loop-naturalness", job["required_visual_checks"])
        self.assertIn("required-reference-present", job["required_local_checks"])

    def test_actor_idle_cannot_drop_identity_or_loop_contract(self):
        cases = {}
        cases["no identity master"] = load_fixture("actor-idle.json")
        cases["no identity master"]["reference"] = {
            "mode": "optional",
            "continuity_group": None,
            "max_images": 1,
        }

        cases["missing motion beat"] = load_fixture("actor-idle.json")
        cases["missing motion beat"]["contract"]["beats"].pop()

        cases["idle not looped"] = load_fixture("actor-idle.json")
        cases["idle not looped"]["contract"]["loop"] = False

        for label, job in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(GoldenJobValidationError):
                    validate_golden_job(job)

    def test_actor_walk_fixture_is_a_grounded_alternating_six_beat_cycle(self):
        idle = load_fixture("actor-idle.json")
        walk = load_fixture("actor-walk.json")

        self.assertEqual(validate_golden_job(walk), walk)
        self.assertEqual(walk["reference"]["continuity_group"], idle["reference"]["continuity_group"])
        self.assertEqual(walk["contract"]["action"], "walk")
        self.assertTrue(walk["contract"]["loop"])
        self.assertEqual(walk["contract"]["frame_count"], 6)
        self.assertEqual(
            [beat["id"] for beat in walk["contract"]["beats"]],
            [
                "contact-left",
                "down-left",
                "passing-left",
                "contact-right",
                "down-right",
                "passing-right",
            ],
        )
        self.assertIn("support-foot-alternation", walk["required_local_checks"])
        self.assertIn("gait-readability", walk["required_visual_checks"])

    def test_actor_walk_rejects_duplicate_or_incomplete_gait(self):
        cases = {}
        cases["missing gait beat"] = load_fixture("actor-walk.json")
        cases["missing gait beat"]["contract"]["beats"].pop()

        cases["duplicate gait beat"] = load_fixture("actor-walk.json")
        cases["duplicate gait beat"]["contract"]["beats"][5]["id"] = "passing-left"

        cases["walk not looped"] = load_fixture("actor-walk.json")
        cases["walk not looped"]["contract"]["loop"] = False

        for label, job in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(GoldenJobValidationError):
                    validate_golden_job(job)

    def test_actor_attack_fixture_has_readable_one_shot_combat_beats(self):
        idle = load_fixture("actor-idle.json")
        walk = load_fixture("actor-walk.json")
        attack = load_fixture("actor-attack.json")

        self.assertEqual(validate_golden_job(attack), attack)
        groups = {
            job["reference"]["continuity_group"] for job in (idle, walk, attack)
        }
        self.assertEqual(groups, {"golden-ranger-v1"})
        self.assertEqual(attack["contract"]["action"], "attack")
        self.assertFalse(attack["contract"]["loop"])
        self.assertEqual(attack["contract"]["frame_count"], 6)
        self.assertEqual(
            [beat["id"] for beat in attack["contract"]["beats"]],
            ["anticipation", "wind-up", "strike", "impact", "recovery", "return"],
        )
        self.assertIn("impact-peak-delta", attack["required_local_checks"])
        self.assertIn("impact-readability", attack["required_visual_checks"])

    def test_actor_attack_rejects_loop_or_missing_combat_phase(self):
        cases = {}
        cases["attack loops"] = load_fixture("actor-attack.json")
        cases["attack loops"]["contract"]["loop"] = True

        cases["impact missing"] = load_fixture("actor-attack.json")
        cases["impact missing"]["contract"]["beats"] = [
            beat
            for beat in cases["impact missing"]["contract"]["beats"]
            if beat["id"] != "impact"
        ]

        cases["duplicate combat phase"] = load_fixture("actor-attack.json")
        cases["duplicate combat phase"]["contract"]["beats"][4]["id"] = "strike"

        for label, job in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(GoldenJobValidationError):
                    validate_golden_job(job)

    def test_ui_button_fixture_defines_four_consistent_text_free_states(self):
        job = load_fixture("ui-button.json")

        self.assertEqual(validate_golden_job(job), job)
        self.assertEqual(job["family"], "ui")
        self.assertEqual(job["contract"]["kind"], "state_set")
        self.assertEqual(job["contract"]["frame_count"], 4)
        self.assertEqual(
            job["contract"]["states"],
            ["normal", "hover", "pressed", "disabled"],
        )
        self.assertFalse(job["contract"]["loop"])
        self.assertIn("state-canvas-alignment", job["required_local_checks"])
        self.assertIn("state-distinguishability", job["required_visual_checks"])
        self.assertIn("no text", job["prompt"].lower())

    def test_ui_button_rejects_missing_duplicate_or_animated_states(self):
        cases = {}
        cases["missing disabled state"] = load_fixture("ui-button.json")
        cases["missing disabled state"]["contract"]["states"].pop()

        cases["duplicate state"] = load_fixture("ui-button.json")
        cases["duplicate state"]["contract"]["states"][3] = "pressed"

        cases["action attached"] = load_fixture("ui-button.json")
        cases["action attached"]["contract"]["action"] = "click"

        for label, job in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(GoldenJobValidationError):
                    validate_golden_job(job)

    def test_vfx_impact_fixture_has_one_shot_energy_envelope_and_fixed_pivot(self):
        job = load_fixture("vfx-impact.json")

        self.assertEqual(validate_golden_job(job), job)
        self.assertEqual(job["family"], "effect")
        self.assertEqual(job["contract"]["kind"], "sequence")
        self.assertEqual(job["contract"]["action"], "impact")
        self.assertFalse(job["contract"]["loop"])
        self.assertEqual(job["contract"]["frame_count"], 6)
        self.assertEqual(
            [beat["id"] for beat in job["contract"]["beats"]],
            ["spark", "expand", "peak", "fragment", "dissipate", "vanish"],
        )
        self.assertIn("energy-envelope", job["required_local_checks"])
        self.assertIn("impact-readability", job["required_visual_checks"])

    def test_vfx_impact_rejects_loop_direction_or_incomplete_envelope(self):
        cases = {}
        cases["impact loops"] = load_fixture("vfx-impact.json")
        cases["impact loops"]["contract"]["loop"] = True

        cases["effect has actor direction"] = load_fixture("vfx-impact.json")
        cases["effect has actor direction"]["contract"]["directions"] = ["south"]

        cases["envelope missing phase"] = load_fixture("vfx-impact.json")
        cases["envelope missing phase"]["contract"]["beats"].pop()

        for label, job in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(GoldenJobValidationError):
                    validate_golden_job(job)


if __name__ == "__main__":
    unittest.main()
