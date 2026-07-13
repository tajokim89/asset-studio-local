from __future__ import annotations

import base64
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from asset_studio.actor_blueprint import render_pose_blueprint_prompt_png, se_attack_blueprints, se_idle_blueprints, se_walk_blueprints
from server import build_actor_identity_detail_png, walk_blueprints
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
            blueprint = walk_blueprints()[0]

            response = harness.post_json("/api/generate-actor-frame", {
                "prompt": "black-skinned muscular orc in a brown leather tunic",
                "negative": "green skin, extra limbs",
                "direction": "S",
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
            self.assertEqual(payload["beat"], "L")
            self.assertEqual(payload["frame_index"], 1)
            self.assertEqual(payload["frame_count"], 4)
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
            first_blueprint, blueprint = walk_blueprints()

            first = harness.post_json("/api/generate-actor-frame", {
                "prompt": "elder knight with sword and shield",
                "direction": "S", "action": "walk", "frame_index": 1,
                "direction_master": master, "pose_blueprint": first_blueprint,
                "background_mode": "chroma_green",
            })
            self.assertEqual(first.status, 200)

            response = harness.post_json("/api/generate-actor-frame", {
                "prompt": "elder knight with sword and shield",
                "direction": "S",
                "action": "walk",
                "frame_index": 3,
                "direction_master": master,
                "continuity_reference": continuity,
                "pose_blueprint": blueprint,
                "background_mode": "chroma_green",
                "run_id": first.json()["run_id"],
            })

            self.assertEqual(response.status, 200)
            self.assertTrue(response.json()["continuity_reference_used"])
            call = provider.calls[1]
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

    def test_walk_blueprints_generate_only_canonical_opposite_step_beats(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            _provider, harness = self.make_harness(Path(temp_dir))

            response = harness.get_json("/api/actor-walk-blueprints")
            payload = response.json()

            self.assertEqual(response.status, 200)
            self.assertEqual(payload["action"], "walk")
            self.assertEqual(payload["frame_count"], 4)
            self.assertEqual(payload["beats"], ["N", "L", "N", "R"])
            self.assertEqual(payload["generated_frame_indices"], [1, 3])
            self.assertEqual([item["frame_index"] for item in payload["blueprints"]], [1, 3])
            self.assertEqual([item["beat_id"] for item in payload["blueprints"]], ["L", "R"])
            self.assertTrue(all(item["direction"] == "S" for item in payload["blueprints"]))

    def test_walk_assembly_rejects_client_only_visual_labels(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider, harness = self.make_harness(Path(temp_dir))
            source = deterministic_png("uploaded-walk-source")
            frames = {"0": {
                "image": png_data_url(source),
                "artifact_digest": hashlib.sha256(source).hexdigest(),
                "visual_qa": "PASS",
            }}
            generated = harness.post_json("/api/generate-actor-frame", {
                "prompt": "preserve uploaded walk source", "direction": "S", "action": "walk",
                "frame_index": 1, "direction_master": png_data_url(source),
                "pose_blueprint": walk_blueprints()[0], "background_mode": "chroma_green",
            })
            self.assertEqual(generated.status, 200)

            response = harness.post_json("/api/assemble-actor-walk", {
                "run_id": generated.json()["run_id"], "source_digest": generated.json()["source_digest"],
                "frames": frames, "approvals": {},
            })

            self.assertEqual(response.status, 400)
            self.assertIn("frame 1", response.json()["error"])
            self.assertEqual(len(provider.calls), 1)

    def test_fake_provider_runs_uploaded_source_two_generation_and_approved_assembly_flow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider, harness = self.make_harness(Path(temp_dir))
            blueprints = harness.get_json("/api/actor-walk-blueprints").json()["blueprints"]
            source = deterministic_png("uploaded flexible actor with red coat")
            source_url = png_data_url(source)
            frames = {"0": {"image": source_url, "artifact_digest": hashlib.sha256(source).hexdigest()}}
            approvals = {}
            run_id = None
            source_digest = hashlib.sha256(source).hexdigest()

            for blueprint in blueprints:
                request = {
                    "prompt": "preserve the uploaded flexible actor with red coat",
                    "direction": "S",
                    "action": "walk",
                    "frame_index": blueprint["frame_index"],
                    "direction_master": source_url,
                    "pose_blueprint": blueprint,
                    "background_mode": "chroma_green",
                }
                if run_id is not None:
                    request["run_id"] = run_id
                response = harness.post_json("/api/generate-actor-frame", request)
                self.assertEqual(response.status, 200)
                frame = response.json()
                run_id = run_id or frame["run_id"]
                raw = Path(frame["path"]).read_bytes()
                index = blueprint["frame_index"]
                frames[str(index)] = {"image": png_data_url(raw), "artifact_digest": frame["artifact_digest"]}
                approved = harness.post_json("/api/approve-actor-walk-frame", {
                    "run_id": run_id, "source_digest": source_digest,
                    "artifact_digest": frame["artifact_digest"], "frame_index": index,
                    "beat": blueprint["beat_id"], "decision": "APPROVED",
                })
                self.assertEqual(approved.status, 200)
                approvals[str(index)] = approved.json()["approval_token"]

            assembly = harness.post_json("/api/assemble-actor-walk", {
                "run_id": run_id, "source_digest": source_digest,
                "frames": frames, "approvals": approvals, "cell_size": 64, "padding": 4,
            })

            self.assertEqual(assembly.status, 200)
            self.assertEqual(len(provider.calls), 2)
            self.assertTrue(all("uploaded flexible actor with red coat" in call["prompt"] for call in provider.calls))
            self.assertEqual(len(assembly.json()["frame_urls"]), 4)
            with Image.open(io.BytesIO(source)) as uploaded:
                self.assertEqual(assembly.json()["geometry"]["sheet_size"], [uploaded.width * 4, uploaded.height])

    def test_walk_export_requires_real_server_token_and_preserves_uploaded_neutral_rgba(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider, harness = self.make_harness(Path(temp_dir))
            source_image = Image.new("RGBA", (19, 23), (17, 29, 41, 0))
            for y in range(4, 20):
                for x in range(6, 13):
                    source_image.putpixel((x, y), (173, 61, 37, 255))
            source_buffer = io.BytesIO()
            source_image.save(source_buffer, format="PNG")
            source = source_buffer.getvalue()
            source_url = png_data_url(source)
            frames = {"0": {"image": source_url, "artifact_digest": hashlib.sha256(source).hexdigest()}}
            approvals = {}
            run_id = None
            source_digest = hashlib.sha256(source).hexdigest()

            for blueprint in harness.get_json("/api/actor-walk-blueprints").json()["blueprints"]:
                request = {
                    "prompt": "preserve uploaded actor",
                    "direction": "S", "action": "walk",
                    "frame_index": blueprint["frame_index"],
                    "direction_master": source_url,
                    "pose_blueprint": blueprint,
                    "background_mode": "chroma_green",
                }
                if run_id is not None:
                    request["run_id"] = run_id
                generated_response = harness.post_json("/api/generate-actor-frame", request)
                self.assertEqual(generated_response.status, 200)
                generated = generated_response.json()
                run_id = run_id or generated["run_id"]
                raw = Path(generated["path"]).read_bytes()
                index = blueprint["frame_index"]
                frames[str(index)] = {"image": png_data_url(raw), "artifact_digest": generated["artifact_digest"]}
                approval = harness.post_json("/api/approve-actor-walk-frame", {
                    "run_id": run_id, "source_digest": source_digest,
                    "artifact_digest": generated["artifact_digest"], "frame_index": index,
                    "beat": blueprint["beat_id"], "decision": "APPROVED",
                }).json()
                approvals[str(index)] = approval["approval_token"]

            assembly_response = harness.post_json("/api/assemble-actor-walk", {
                "run_id": run_id, "source_digest": source_digest,
                "frames": frames, "approvals": approvals, "cell_size": 64, "padding": 4,
            })
            self.assertEqual(assembly_response.status, 200)
            assembly = assembly_response.json()
            token = assembly["approval_provenance"]["assembly_token"]
            self.assertNotEqual(token, assembly["approval_provenance"]["sheet_digest"])

            forged = harness.post_json("/api/export-actor-walk", {
                "assembly_token": "forged-client-token",
                "approval_provenance": assembly["approval_provenance"],
            })
            self.assertEqual(forged.status, 400)

            exported = harness.post_json("/api/export-actor-walk", {"assembly_token": token})
            repeated = harness.post_json("/api/export-actor-walk", {"assembly_token": token})
            self.assertEqual(exported.status, 200)
            self.assertEqual(repeated.body, exported.body)
            self.assertEqual(exported.headers["Content-Type"], "application/zip")
            with zipfile.ZipFile(io.BytesIO(exported.body)) as package:
                self.assertIsNone(package.testzip())
                manifest = json.loads(package.read("manifest.json"))
                self.assertEqual(manifest["beats"], ["N", "L", "N", "R"])
                frame_1 = Image.open(io.BytesIO(package.read("frames/walk-000.png"))).convert("RGBA")
                frame_3 = Image.open(io.BytesIO(package.read("frames/walk-002.png"))).convert("RGBA")
                atlas = Image.open(io.BytesIO(package.read("atlas.png"))).convert("RGBA")
                self.assertEqual(frame_1.size, source_image.size)
                self.assertEqual(frame_3.size, source_image.size)
                self.assertEqual(frame_1.tobytes(), source_image.tobytes())
                self.assertEqual(frame_3.tobytes(), source_image.tobytes())
                self.assertEqual(atlas.crop((0, 0, 19, 23)).tobytes(), source_image.tobytes())
                self.assertEqual(atlas.crop((38, 0, 57, 23)).tobytes(), source_image.tobytes())


if __name__ == "__main__":
    unittest.main()
