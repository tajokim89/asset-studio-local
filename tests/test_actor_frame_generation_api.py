from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from asset_studio.actor_blueprint import render_pose_blueprint_prompt_png, se_attack_blueprints, se_idle_blueprints, se_walk_blueprints
from server import build_actor_identity_detail_png
from tests.helpers.fake_image_provider import FakeImageProvider, deterministic_png
from tests.helpers.http_generation_harness import GenerationHttpHarness


def image_data_url(label: str) -> str:
    encoded = base64.b64encode(deterministic_png(label)).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def png_data_url(raw: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


class ActorFrameGenerationApiTests(unittest.TestCase):
    def make_harness(self, root: Path):
        provider = FakeImageProvider(root / "provider")
        return provider, GenerationHttpHarness(provider, root / "generated")

    def test_actor_master_generates_exactly_one_direction_reference(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider, harness = self.make_harness(Path(temp_dir))

            response = harness.post_json("/api/generate-actor-master", {
                "prompt": "black-skinned muscular orc in a brown leather tunic",
                "negative": "green skin, weapon",
                "direction": "SE",
                "background_mode": "chroma_green",
            })
            payload = response.json()

            self.assertEqual(response.status, 200)
            self.assertTrue(payload["success"])
            self.assertEqual(payload["generation_stage"], "direction-master")
            self.assertEqual(payload["direction"], "SE")
            self.assertEqual(
                payload["identity_spec"]["character_description"],
                "black-skinned muscular orc in a brown leather tunic",
            )
            self.assertEqual(payload["identity_spec"]["frame_change_policy"], "pose-only")
            self.assertEqual(len(provider.calls), 1)
            self.assertNotIn("image_url", provider.calls[0])
            self.assertIn("exactly one complete full-body character", provider.calls[0]["prompt"])
            self.assertIn("SE front-right three-quarter", provider.calls[0]["prompt"])

    def test_actor_frame_uses_master_and_pose_guide_as_ordered_references(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider, harness = self.make_harness(Path(temp_dir))
            master = image_data_url("master")
            blueprint = se_walk_blueprints()[1]

            response = harness.post_json("/api/generate-actor-frame", {
                "prompt": "black-skinned muscular orc in a brown leather tunic",
                "negative": "green skin, extra limbs",
                "direction": "SE",
                "action": "walk",
                "frame_index": 1,
                "direction_master": master,
                "pose_blueprint": blueprint,
                "background_mode": "chroma_green",
            })
            payload = response.json()

            self.assertEqual(response.status, 200)
            self.assertTrue(payload["success"])
            self.assertEqual(payload["generation_stage"], "actor-frame")
            self.assertEqual(payload["action"], "walk")
            self.assertEqual(payload["beat"], "left-down")
            self.assertEqual(payload["frame_index"], 1)
            self.assertEqual(payload["frame_count"], 6)
            self.assertEqual(len(provider.calls), 1)
            call = provider.calls[0]
            self.assertEqual(call["image_url"], master)
            self.assertEqual(
                call["reference_image_urls"],
                [
                    png_data_url(render_pose_blueprint_prompt_png(blueprint)),
                    png_data_url(build_actor_identity_detail_png(base64.b64decode(master.split(",", 1)[1]))),
                ],
            )
            self.assertIn("Generate ONE frame only", call["prompt"])
            self.assertIn("IMAGE 1 is the Direction Master", call["prompt"])
            self.assertIn("IMAGE 2 is the Pose Guide", call["prompt"])
            self.assertIn("IMAGE 3 is the Identity Detail", call["prompt"])

    def test_actor_frame_rejects_missing_pose_blueprint_without_spending_a_provider_call(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider, harness = self.make_harness(Path(temp_dir))

            response = harness.post_json("/api/generate-actor-frame", {
                "prompt": "black-skinned muscular orc",
                "direction": "SE",
                "action": "idle",
                "frame_index": 0,
                "direction_master": image_data_url("master"),
            })

            self.assertEqual(response.status, 400)
            self.assertIn("pose_blueprint", response.json()["error"])
            self.assertEqual(provider.calls, [])

    def test_actor_frame_can_use_an_approved_continuity_reference_after_the_first_frame(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider, harness = self.make_harness(Path(temp_dir))
            master = image_data_url("master")
            continuity = image_data_url("approved-frame-1")
            blueprint = se_walk_blueprints()[2]

            response = harness.post_json("/api/generate-actor-frame", {
                "prompt": "elder knight with sword and shield",
                "direction": "SE",
                "action": "walk",
                "frame_index": 2,
                "direction_master": master,
                "continuity_reference": continuity,
                "pose_blueprint": blueprint,
                "background_mode": "chroma_green",
            })

            self.assertEqual(response.status, 200)
            self.assertTrue(response.json()["continuity_reference_used"])
            call = provider.calls[0]
            self.assertEqual(call["reference_image_urls"][-1], continuity)
            self.assertIn("IMAGE 4 is the approved Continuity Reference", call["prompt"])

    def test_actor_frame_rejects_frame_index_outside_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider, harness = self.make_harness(Path(temp_dir))

            response = harness.post_json("/api/generate-actor-frame", {
                "prompt": "black-skinned muscular orc",
                "direction": "SE",
                "action": "attack",
                "frame_index": 6,
                "direction_master": image_data_url("master"),
                "pose_blueprint": se_attack_blueprints()[0],
            })

            self.assertEqual(response.status, 400)
            self.assertIn("frame_index", response.json()["error"])
            self.assertEqual(provider.calls, [])

    def test_attack_motion_directive_can_authoritatively_select_unarmed_motion(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider, harness = self.make_harness(Path(temp_dir))

            response = harness.post_json("/api/generate-actor-frame", {
                "prompt": "black-skinned muscular orc in a brown leather tunic",
                "direction": "SE",
                "action": "attack",
                "frame_index": 3,
                "motion_directive": "Unarmed heavy right punch; no weapon.",
                "direction_master": image_data_url("master"),
                "pose_blueprint": se_attack_blueprints()[3],
            })

            self.assertEqual(response.status, 200)
            request_prompt = provider.calls[0]["prompt"]
            self.assertIn("Motion directive: Unarmed heavy right punch; no weapon.", request_prompt)
            self.assertIn("authoritative for weapon and equipment presence", request_prompt)

    def test_actor_frame_rejects_blueprint_that_does_not_match_requested_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider, harness = self.make_harness(Path(temp_dir))

            response = harness.post_json("/api/generate-actor-frame", {
                "prompt": "black-skinned muscular orc",
                "direction": "SE",
                "action": "walk",
                "frame_index": 0,
                "direction_master": image_data_url("master"),
                "pose_blueprint": se_idle_blueprints()[0],
            })

            self.assertEqual(response.status, 400)
            self.assertIn("pose_blueprint action", response.json()["error"])
            self.assertEqual(provider.calls, [])

    def test_walk4_blueprints_include_opposite_crossing_passes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            _provider, harness = self.make_harness(Path(temp_dir))

            response = harness.get_json("/api/actor-walk4-blueprints")
            payload = response.json()

            self.assertEqual(response.status, 200)
            self.assertEqual(payload["frame_count"], 4)
            self.assertEqual(
                payload["beats"],
                ["left-contact", "left-passing", "right-contact", "right-passing"],
            )
            self.assertEqual(
                [blueprint["frame_index"] for blueprint in payload["blueprints"]],
                [0, 2, 3, 5],
            )

            left_pass, right_pass = payload["blueprints"][1], payload["blueprints"][3]
            left_contact, right_contact = payload["blueprints"][0], payload["blueprints"][2]
            left_joints = {joint["name"]: joint for joint in left_pass["joints"]}
            right_joints = {joint["name"]: joint for joint in right_pass["joints"]}
            left_contact_joints = {joint["name"]: joint for joint in left_contact["joints"]}
            right_contact_joints = {joint["name"]: joint for joint in right_contact["joints"]}

            self.assertLess(left_joints["toe_r"]["x"], left_joints["toe_l"]["x"])
            self.assertGreater(right_joints["toe_l"]["x"], right_joints["toe_r"]["x"])
            self.assertLess(left_joints["toe_r"]["y"], left_pass["baseline"])
            self.assertLess(right_joints["toe_l"]["y"], right_pass["baseline"])
            self.assertLessEqual(round(abs(left_contact_joints["toe_l"]["x"] - left_contact_joints["toe_r"]["x"]) * 31), 2)
            self.assertLessEqual(round(abs(right_contact_joints["toe_l"]["x"] - right_contact_joints["toe_r"]["x"]) * 31), 2)
            self.assertGreater(left_joints["hand_l"]["y"], left_joints["hand_r"]["y"])
            self.assertLess(right_joints["hand_l"]["y"], right_joints["hand_r"]["y"])
            self.assertEqual(
                {(joint["x"], joint["y"]) for joint in [
                    left_contact_joints["head"], left_joints["head"],
                    right_contact_joints["head"], right_joints["head"],
                ]},
                {(17 / 31, 6 / 31)},
            )

    def test_walk4_assembly_requires_four_visually_approved_frames(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider, harness = self.make_harness(Path(temp_dir))
            frames = [
                {"image": image_data_url(f"walk-{index}"), "visual_qa": "PASS"}
                for index in range(4)
            ]
            frames[2]["visual_qa"] = "PENDING"

            response = harness.post_json("/api/assemble-actor-walk4", {"frames": frames})

            self.assertEqual(response.status, 400)
            self.assertIn("visual_qa=PASS", response.json()["error"])
            self.assertEqual(provider.calls, [])

    def test_walk4_assembly_returns_sheet_and_normalized_preview_frames_without_provider_call(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider, harness = self.make_harness(Path(temp_dir))
            frames = [
                {"image": image_data_url(f"walk-{index}"), "visual_qa": "PASS"}
                for index in range(4)
            ]

            response = harness.post_json("/api/assemble-actor-walk4", {
                "frames": frames,
                "cell_size": 64,
                "padding": 4,
            })
            payload = response.json()

            self.assertEqual(response.status, 200)
            self.assertTrue(payload["export_ready"])
            self.assertEqual(len(payload["frame_urls"]), 4)
            self.assertEqual(payload["geometry"]["sheet_size"], [256, 64])
            self.assertEqual(payload["geometry"]["alignment"], "head-and-ground-lock")
            self.assertEqual(provider.calls, [])

    def test_fake_provider_runs_complete_master_four_frame_and_assembly_flow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider, harness = self.make_harness(Path(temp_dir))
            blueprints = harness.get_json("/api/actor-walk4-blueprints").json()["blueprints"]
            master_response = harness.post_json("/api/generate-actor-master", {
                "prompt": "a flexible user-defined actor with a red coat",
                "direction": "SE",
                "background_mode": "chroma_green",
            }).json()
            master_data_url = png_data_url(Path(master_response["path"]).read_bytes())
            approved_frames = []

            for blueprint in blueprints:
                response = harness.post_json("/api/generate-actor-frame", {
                    "prompt": "this value must be replaced by identity_spec",
                    "identity_spec": master_response["identity_spec"],
                    "direction": "SE",
                    "action": "walk",
                    "frame_index": blueprint["frame_index"],
                    "direction_master": master_data_url,
                    "pose_blueprint": blueprint,
                    "background_mode": "chroma_green",
                })
                self.assertEqual(response.status, 200)
                frame = response.json()
                approved_frames.append({
                    "image": png_data_url(Path(frame["path"]).read_bytes()),
                    "visual_qa": "PASS",
                })

            assembly = harness.post_json("/api/assemble-actor-walk4", {
                "frames": approved_frames,
                "cell_size": 64,
                "padding": 4,
            })

            self.assertEqual(assembly.status, 200)
            self.assertEqual(len(provider.calls), 5)
            self.assertTrue(
                all(
                    "a flexible user-defined actor with a red coat" in call["prompt"]
                    for call in provider.calls
                )
            )
            self.assertEqual(len(assembly.json()["frame_urls"]), 4)


if __name__ == "__main__":
    unittest.main()
