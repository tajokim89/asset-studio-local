from __future__ import annotations

import copy
import hashlib
import io
import unittest

from PIL import Image

from asset_studio.actor_blueprint import (
    JOINT_NAMES,
    PoseBlueprintError,
    render_pose_blueprint_png,
    se_attack_blueprints,
    se_idle_blueprints,
    se_walk_blueprints,
    validate_pose_blueprint,
    validate_pose_blueprint_sequence,
)


def _joint(blueprint, name):
    return next(joint for joint in blueprint["joints"] if joint["name"] == name)


class ActorBlueprintTests(unittest.TestCase):
    def test_canonical_se_idle_and_walk_define_every_beat_and_joint(self):
        idle = se_idle_blueprints()
        walk = se_walk_blueprints()

        self.assertEqual(
            ["settle", "breathe-up", "settle-return", "breathe-down"],
            [item["beat_id"] for item in idle],
        )
        self.assertEqual(
            [
                "left-contact",
                "left-down",
                "left-passing",
                "right-contact",
                "right-down",
                "right-passing",
            ],
            [item["beat_id"] for item in walk],
        )
        self.assertEqual(list(range(4)), [item["frame_index"] for item in idle])
        self.assertEqual(list(range(6)), [item["frame_index"] for item in walk])

        for blueprint in (*idle, *walk):
            with self.subTest(action=blueprint["action"], beat=blueprint["beat_id"]):
                self.assertEqual("SE", blueprint["direction"])
                self.assertEqual(
                    list(JOINT_NAMES),
                    [joint["name"] for joint in blueprint["joints"]],
                )
                self.assertTrue(
                    all(
                        0 <= joint[axis] <= 1
                        for joint in blueprint["joints"]
                        for axis in ("x", "y")
                    )
                )
                self.assertEqual(blueprint["baseline"], blueprint["root"]["y"])
                self.assertEqual(blueprint, validate_pose_blueprint(blueprint))

    def test_validator_returns_a_detached_blueprint(self):
        original = se_walk_blueprints()[0]
        validated = validate_pose_blueprint(original)
        validated["joints"][0]["x"] = 0
        self.assertNotEqual(0, original["joints"][0]["x"])

    def test_se_attack_is_an_unarmed_heavy_right_punch(self):
        attack = se_attack_blueprints()
        self.assertEqual(
            ["ready", "anticipation", "wind-up", "strike", "impact", "recovery"],
            [item["beat_id"] for item in attack],
        )
        self.assertEqual(list(range(6)), [item["frame_index"] for item in attack])

        roots = {(item["root"]["x"], item["root"]["y"]) for item in attack}
        baselines = {item["baseline"] for item in attack}
        pose_signatures = {
            tuple((joint["name"], joint["x"], joint["y"]) for joint in item["joints"])
            for item in attack
        }
        self.assertEqual(1, len(roots))
        self.assertEqual(1, len(baselines))
        self.assertEqual(6, len(pose_signatures))

        for blueprint in attack:
            with self.subTest(beat=blueprint["beat_id"]):
                self.assertEqual("SE", blueprint["direction"])
                self.assertEqual("attack", blueprint["action"])
                self.assertEqual("left", blueprint["support_foot"])
                self.assertEqual("both", blueprint["contact_foot"])
                self.assertEqual("planted", blueprint["foot_state_l"])
                self.assertEqual("planted", blueprint["foot_state_r"])
                self.assertEqual("fist", blueprint["hand_state_l"])
                self.assertEqual("fist", blueprint["hand_state_r"])
                self.assertEqual({"left": False, "right": False}, blueprint["weapon_contact"])
                self.assertEqual([], blueprint["equipment_anchors"])
                self.assertEqual(list(JOINT_NAMES), [joint["name"] for joint in blueprint["joints"]])
                self.assertEqual(blueprint, validate_pose_blueprint(blueprint))

    def test_attack_strike_and_impact_keep_the_right_arm_connected_through_torso_rotation(self):
        attack = {item["beat_id"]: item for item in se_attack_blueprints()}
        ready = attack["ready"]
        wind_up = attack["wind-up"]

        for beat in ("strike", "impact"):
            blueprint = attack[beat]
            right_chain = [
                _joint(blueprint, name)
                for name in ("shoulder_r", "elbow_r", "wrist_r", "hand_r")
            ]
            self.assertTrue(all(joint["visible"] for joint in right_chain))
            for start, end in zip(right_chain, right_chain[1:]):
                distance_sq = ((end["x"] - start["x"]) * 31) ** 2 + (
                    (end["y"] - start["y"]) * 31
                ) ** 2
                self.assertGreater(distance_sq, 0)
                self.assertLessEqual(distance_sq, 25)
            self.assertGreater(_joint(blueprint, "hand_r")["x"], _joint(wind_up, "hand_r")["x"])
            self.assertNotEqual(
                (
                    _joint(ready, "shoulder_l")["x"],
                    _joint(ready, "shoulder_r")["x"],
                    _joint(ready, "pelvis")["x"],
                ),
                (
                    _joint(blueprint, "shoulder_l")["x"],
                    _joint(blueprint, "shoulder_r")["x"],
                    _joint(blueprint, "pelvis")["x"],
                ),
            )

    def test_validator_rejects_missing_required_pose_data(self):
        for field in ("support_foot", "contact_foot", "hand_state_l", "baseline"):
            with self.subTest(field=field):
                invalid = copy.deepcopy(se_walk_blueprints()[0])
                del invalid[field]
                with self.assertRaisesRegex(PoseBlueprintError, "missing"):
                    validate_pose_blueprint(invalid)

    def test_validator_rejects_unknown_fields_at_strict_boundaries(self):
        invalid = copy.deepcopy(se_idle_blueprints()[0])
        invalid["canvas"]["helpful_guess"] = 32
        with self.assertRaisesRegex(PoseBlueprintError, "unknown"):
            validate_pose_blueprint(invalid)

    def test_validator_rejects_missing_and_duplicate_humanoid_joints(self):
        missing = copy.deepcopy(se_idle_blueprints()[0])
        missing["joints"].pop()
        with self.assertRaisesRegex(PoseBlueprintError, "missing"):
            validate_pose_blueprint(missing)

        duplicate = copy.deepcopy(se_idle_blueprints()[0])
        duplicate["joints"][-1]["name"] = "toe_l"
        with self.assertRaisesRegex(PoseBlueprintError, "duplicate joint"):
            validate_pose_blueprint(duplicate)

    def test_walk_rejects_opposite_or_incoherent_support_data(self):
        cases = (
            ({"beat_id": "right-contact"}, "must be 'right'"),
            ({"contact_foot": "right"}, "must match support_foot"),
            ({"foot_state_l": "flight"}, "support foot must be"),
            ({"foot_state_r": "planted"}, "opposite foot cannot"),
        )
        for mutation, message in cases:
            with self.subTest(mutation=mutation):
                invalid = copy.deepcopy(se_walk_blueprints()[0])
                invalid.update(mutation)
                with self.assertRaisesRegex(PoseBlueprintError, message):
                    validate_pose_blueprint(invalid)

    def test_idle_requires_both_planted_feet(self):
        invalid = copy.deepcopy(se_idle_blueprints()[0])
        invalid["support_foot"] = "left"
        invalid["contact_foot"] = "left"
        invalid["foot_state_r"] = "passing"
        with self.assertRaisesRegex(PoseBlueprintError, "idle requires both"):
            validate_pose_blueprint(invalid)

    def test_validator_rejects_out_of_range_joint_coordinates(self):
        invalid = copy.deepcopy(se_idle_blueprints()[0])
        _joint(invalid, "hand_l")["x"] = 1.01
        with self.assertRaisesRegex(PoseBlueprintError, "must be in 0..1"):
            validate_pose_blueprint(invalid)

    def test_sequence_rejects_duplicate_frame_and_beat_data(self):
        duplicate_frame = list(se_idle_blueprints())
        duplicate_frame[1]["frame_index"] = 0
        with self.assertRaisesRegex(PoseBlueprintError, "duplicate frame index"):
            validate_pose_blueprint_sequence(duplicate_frame)

        duplicate_beat = list(se_idle_blueprints())
        duplicate_beat[1]["beat_id"] = duplicate_beat[0]["beat_id"]
        with self.assertRaisesRegex(PoseBlueprintError, "duplicate beat id"):
            validate_pose_blueprint_sequence(duplicate_beat)

    def test_renderer_is_deterministic_and_nearest_neighbor_only(self):
        blueprint = se_walk_blueprints()[0]
        first = render_pose_blueprint_png(blueprint, scale=8)
        second = render_pose_blueprint_png(blueprint, scale=8)
        self.assertEqual(first, second)

        with Image.open(io.BytesIO(first)) as rendered:
            rendered.load()
            self.assertEqual("RGBA", rendered.mode)
            self.assertEqual((256, 256), rendered.size)
            target = rendered.resize((32, 32), Image.Resampling.NEAREST)
            restored = target.resize((256, 256), Image.Resampling.NEAREST)
            self.assertEqual(restored.tobytes(), rendered.tobytes())

        target_png = render_pose_blueprint_png(blueprint, scale=1)
        with Image.open(io.BytesIO(target_png)) as target:
            target.load()
            self.assertEqual(
                "e974f64d835f49aff83334e7f09224ad8b2cc2d84a2b4885246d0f0c22520257",
                hashlib.sha256(target.tobytes()).hexdigest(),
            )

    def test_renderer_rejects_invalid_scale(self):
        for scale in (0, 65, 1.5, True):
            with self.subTest(scale=scale):
                with self.assertRaisesRegex(PoseBlueprintError, "scale"):
                    render_pose_blueprint_png(se_idle_blueprints()[0], scale=scale)


if __name__ == "__main__":
    unittest.main()
