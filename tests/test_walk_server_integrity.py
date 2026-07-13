from __future__ import annotations

import base64
import hashlib
import io
import tempfile
import threading
import unittest
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from PIL import Image

import server
from tests.helpers.fake_image_provider import FakeImageProvider, deterministic_png
from tests.helpers.http_generation_harness import GenerationHttpHarness


def data_url(raw: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def bounded_source(label: str) -> bytes:
    return deterministic_png(label)


class WalkServerIntegrityTests(unittest.TestCase):
    def setUp(self):
        for name in ("WALK_RUNS", "WALK_GENERATED_ARTIFACTS", "WALK_VISUAL_APPROVALS", "WALK_ASSEMBLIES", "WALK_ASSEMBLY_RESERVATIONS"):
            getattr(server, name).clear()

    def make_harness(self, root: Path):
        provider = FakeImageProvider(root / "provider")
        return provider, GenerationHttpHarness(provider, root / "generated")

    def generate(self, harness, source: bytes, frame_index: int, *, run_id: str | None = None):
        blueprint = next(item for item in server.walk_blueprints() if item["frame_index"] == frame_index)
        payload = {
            "prompt": "preserve this exact uploaded actor",
            "direction": "S",
            "action": "walk",
            "frame_index": frame_index,
            "direction_master": data_url(source),
            "pose_blueprint": blueprint,
            "background_mode": "chroma_green",
            "output_profile_id": "generic-pixel-actor-v1",
        }
        if run_id is not None:
            payload["run_id"] = run_id
        return harness.post_json("/api/generate-actor-frame", payload)

    def complete_run(self, harness, source: bytes):
        source_digest = hashlib.sha256(source).hexdigest()
        frames = {"0": {"image": data_url(source), "artifact_digest": source_digest}}
        approvals = {}
        first = self.generate(harness, source, 1)
        self.assertEqual(first.status, 200)
        run_id = first.json()["run_id"]
        for response in (first, self.generate(harness, source, 3, run_id=run_id)):
            self.assertEqual(response.status, 200)
            item = response.json()
            raw = Path(item["path"]).read_bytes()
            index = item["frame_index"]
            frames[str(index)] = {"image": data_url(raw), "artifact_digest": item["artifact_digest"]}
            approved = harness.post_json("/api/approve-actor-walk-frame", {
                "run_id": run_id, "source_digest": source_digest,
                "artifact_digest": item["artifact_digest"], "frame_index": index,
                "beat": item["beat"], "decision": "APPROVED",
            })
            self.assertEqual(approved.status, 200)
            approvals[str(index)] = approved.json()["approval_token"]
        return run_id, source_digest, frames, approvals

    def test_failed_deterministic_frame_is_never_registered_or_approvable(self):
        with tempfile.TemporaryDirectory() as directory:
            _provider, harness = self.make_harness(Path(directory))
            source = bounded_source("qa-fail-source")
            failed_qa = {
                "single_frame_qa": {"pass": False},
                "cleanup_qa": {"pass": True},
                "method": "forced-fail",
            }
            with mock.patch.object(server, "postprocess_actor_single_frame_bytes", return_value=(bounded_source("failed-frame"), failed_qa)):
                response = self.generate(harness, source, 1)
            self.assertEqual(response.status, 422)
            result = response.json()
            self.assertNotIn(result["artifact_digest"], server.WALK_GENERATED_ARTIFACTS)
            rejected = harness.post_json("/api/approve-actor-walk-frame", {
                "run_id": result["run_id"],
                "source_digest": result["source_digest"],
                "artifact_digest": result["artifact_digest"],
                "frame_index": 1,
                "beat": "L",
                "decision": "APPROVED",
            })
            self.assertEqual(rejected.status, 400)

    def test_f4_is_bound_to_f2_run_source_profile_and_direction_before_provider_spend(self):
        with tempfile.TemporaryDirectory() as directory:
            provider, harness = self.make_harness(Path(directory))
            source_a = bounded_source("actor-a")
            source_b = bounded_source("actor-b")
            f2 = self.generate(harness, source_a, 1)
            self.assertEqual(f2.status, 200)
            run_id = f2.json()["run_id"]
            self.assertEqual(f2.json()["source_digest"], hashlib.sha256(source_a).hexdigest())
            mixed = self.generate(harness, source_b, 3, run_id=run_id)
            self.assertEqual(mixed.status, 400)
            self.assertIn("bound", mixed.json()["error"].lower())
            self.assertEqual(len(provider.calls), 1)

    def test_production_walk_rejects_non_s_direction_before_provider_spend(self):
        with tempfile.TemporaryDirectory() as directory:
            provider, harness = self.make_harness(Path(directory))
            source = bounded_source("non-s-walk")
            blueprint = dict(next(item for item in server.walk_blueprints() if item["frame_index"] == 1))
            blueprint["direction"] = "W"
            response = harness.post_json("/api/generate-actor-frame", {
                "prompt": "preserve this exact uploaded actor", "direction": "W", "action": "walk",
                "frame_index": 1, "direction_master": data_url(source), "pose_blueprint": blueprint,
                "background_mode": "chroma_green", "output_profile_id": "generic-pixel-actor-v1",
            })
            self.assertEqual(response.status, 400)
            self.assertIn("direction S only", response.json()["error"])
            self.assertEqual(provider.calls, [])

    def test_walk_source_dimension_budget_rejects_before_proof_or_provider_allocation(self):
        with tempfile.TemporaryDirectory() as directory:
            provider, harness = self.make_harness(Path(directory))
            image = Image.new("RGBA", (513, 2), (0, 0, 0, 0))
            image.putpixel((0, 0), (255, 255, 255, 255))
            output = io.BytesIO()
            image.save(output, "PNG")
            response = self.generate(harness, output.getvalue(), 1)
            self.assertEqual(response.status, 400)
            self.assertIn("512", response.json()["error"])
            self.assertEqual(provider.calls, [])

    def test_provider_sized_generated_frames_can_reach_walk_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            _provider, harness = self.make_harness(Path(directory))
            source_image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
            for y in range(12, 500):
                for x in range(100, 412):
                    source_image.putpixel((x, y), (30, 30, 30, 255))
            source_output = io.BytesIO()
            source_image.save(source_output, "PNG")
            source = source_output.getvalue()
            image = Image.new("RGBA", (1254, 1254), (0, 0, 0, 0))
            for y in range(96, 1158):
                for x in range(260, 994):
                    image.putpixel((x, y), (45, 45, 45, 255))
            output = io.BytesIO()
            image.save(output, "PNG")
            provider_sized_frame = output.getvalue()
            image.putpixel((261, 97), (46, 45, 45, 255))
            alternate_output = io.BytesIO()
            image.save(alternate_output, "PNG")
            alternate_provider_sized_frame = alternate_output.getvalue()
            passing_qa = {
                "single_frame_qa": {"pass": True},
                "cleanup_qa": {"pass": True},
                "method": "provider-sized-test",
            }

            with mock.patch.object(
                server,
                "postprocess_actor_single_frame_bytes",
                side_effect=[
                    (provider_sized_frame, passing_qa),
                    (alternate_provider_sized_frame, passing_qa),
                ],
            ):
                f2 = self.generate(harness, source, 1)
                self.assertEqual(f2.status, 200)
                run_id = f2.json()["run_id"]
                f4 = self.generate(harness, source, 3, run_id=run_id)
                self.assertEqual(f4.status, 200)

            frames = {
                "0": {
                    "image": data_url(source),
                    "artifact_digest": hashlib.sha256(source).hexdigest(),
                }
            }
            for response in (f2, f4):
                item = response.json()
                raw = Path(item["path"]).read_bytes()
                frames[str(item["frame_index"])] = {
                    "image": data_url(raw),
                    "artifact_digest": item["artifact_digest"],
                }

            preview = harness.post_json("/api/preview-actor-walk", {
                "run_id": run_id,
                "source_digest": hashlib.sha256(source).hexdigest(),
                "frames": frames,
            })
            self.assertEqual(preview.status, 200, preview.json())
            self.assertEqual(preview.json()["beats"], ["N", "L", "N", "R"])

            other_source = bounded_source("wrong-preview-f1")
            forged_frames = {**frames, "0": {
                "image": data_url(other_source),
                "artifact_digest": hashlib.sha256(other_source).hexdigest(),
            }}
            rejected = harness.post_json("/api/preview-actor-walk", {
                "run_id": run_id,
                "source_digest": hashlib.sha256(source).hexdigest(),
                "frames": forged_frames,
            })
            self.assertEqual(rejected.status, 400)
            self.assertIn("source_digest", rejected.json()["error"])

    def test_prune_helper_expires_then_caps_oldest_records_and_bytes_without_sleep(self):
        store = {
            "expired": {"created_at": 1.0, "byte_size": 1},
            "old": {"created_at": 90.0, "byte_size": 4},
            "middle": {"created_at": 91.0, "byte_size": 4},
            "new": {"created_at": 92.0, "byte_size": 4},
        }
        removed = server._prune_walk_store(store, now=100.0, ttl_seconds=20.0, max_records=2, max_bytes=8)
        self.assertEqual(set(removed), {"expired", "old"})
        self.assertEqual(list(store), ["middle", "new"])
        server._prune_walk_store(store, now=100.0, ttl_seconds=20.0, max_records=2, max_bytes=5)
        self.assertEqual(list(store), ["new"])

    def test_identical_concurrent_assembly_is_reserved_once_and_failure_releases_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _provider, harness = self.make_harness(root)
            run_id, source_digest, frames, approvals = self.complete_run(harness, bounded_source("concurrent-assembly"))
            payload = {"run_id": run_id, "source_digest": source_digest, "frames": frames, "approvals": approvals}
            original_assemble = server.assemble_canonical_walk_frames
            entered = threading.Event()
            release = threading.Event()
            calls = 0

            def blocked_assemble(*args):
                nonlocal calls
                calls += 1
                entered.set()
                self.assertTrue(release.wait(5))
                return original_assemble(*args)

            with mock.patch.object(server, "assemble_canonical_walk_frames", side_effect=blocked_assemble):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    first_future = executor.submit(harness.post_json, "/api/assemble-actor-walk", payload)
                    self.assertTrue(entered.wait(5))
                    conflict = harness.post_json("/api/assemble-actor-walk", payload)
                    self.assertEqual(conflict.status, 409)
                    self.assertEqual(conflict.json()["status"], "assembly_in_progress")
                    self.assertTrue(conflict.json()["retriable"])
                    release.set()
                    first = first_future.result(timeout=10)
            self.assertEqual(first.status, 200)
            self.assertEqual(calls, 1)
            self.assertEqual(len(list((root / "generated").glob("actor_walk_package_*.zip"))), 1)
            self.assertEqual(server.WALK_ASSEMBLY_RESERVATIONS, {})
            completed = harness.post_json("/api/assemble-actor-walk", payload)
            self.assertEqual(completed.status, 200)
            self.assertEqual(completed.json(), first.json())

            retry_run, retry_digest, retry_frames, retry_approvals = self.complete_run(harness, bounded_source("failed-then-retry"))
            retry_payload = {"run_id": retry_run, "source_digest": retry_digest, "frames": retry_frames, "approvals": retry_approvals}
            with mock.patch.object(server, "assemble_canonical_walk_frames", side_effect=server.ActorAssemblyError("forced assembly failure")):
                failed = harness.post_json("/api/assemble-actor-walk", retry_payload)
            self.assertEqual(failed.status, 400)
            self.assertNotIn(retry_run, server.WALK_ASSEMBLY_RESERVATIONS)
            retried = harness.post_json("/api/assemble-actor-walk", retry_payload)
            self.assertEqual(retried.status, 200)

    def test_successful_assembly_creates_valid_durable_package_and_rejects_mixed_run_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _provider, harness = self.make_harness(root)
            source_a = bounded_source("durable-actor-a")
            source_b = bounded_source("durable-actor-b")

            def complete_run(source: bytes):
                frames = {"0": {"image": data_url(source), "artifact_digest": hashlib.sha256(source).hexdigest()}}
                approvals = {}
                first = self.generate(harness, source, 1)
                self.assertEqual(first.status, 200)
                run_id = first.json()["run_id"]
                generated = [first, self.generate(harness, source, 3, run_id=run_id)]
                for response in generated:
                    self.assertEqual(response.status, 200)
                    item = response.json()
                    raw = Path(item["path"]).read_bytes()
                    index = item["frame_index"]
                    frames[str(index)] = {"image": data_url(raw), "artifact_digest": item["artifact_digest"]}
                    approved = harness.post_json("/api/approve-actor-walk-frame", {
                        "run_id": run_id,
                        "source_digest": item["source_digest"],
                        "artifact_digest": item["artifact_digest"],
                        "frame_index": index,
                        "beat": item["beat"],
                        "decision": "APPROVED",
                    })
                    self.assertEqual(approved.status, 200)
                    approvals[str(index)] = approved.json()["approval_token"]
                return run_id, hashlib.sha256(source).hexdigest(), frames, approvals

            run_a, digest_a, frames_a, approvals_a = complete_run(source_a)
            _run_b, _digest_b, _frames_b, approvals_b = complete_run(source_b)
            mixed = harness.post_json("/api/assemble-actor-walk", {
                "run_id": run_a,
                "source_digest": digest_a,
                "frames": frames_a,
                "approvals": {"1": approvals_a["1"], "3": approvals_b["3"]},
            })
            self.assertEqual(mixed.status, 400)

            assembled = harness.post_json("/api/assemble-actor-walk", {
                "run_id": run_a,
                "source_digest": digest_a,
                "frames": frames_a,
                "approvals": approvals_a,
            })
            self.assertEqual(assembled.status, 200)
            result = assembled.json()
            self.assertTrue(result["export_ready"])
            self.assertEqual(result["run_id"], run_a)
            self.assertEqual(result["source_digest"], digest_a)
            self.assertRegex(result["package_url"], r"^/assets/generated/actor_walk_package_[0-9a-f]{32}\.zip$")
            package_path = root / "generated" / Path(result["package_url"]).name
            self.assertTrue(package_path.is_file())
            with zipfile.ZipFile(package_path) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.read("frames/walk-000.png"), archive.read("frames/walk-002.png"))

            package_names = set((root / "generated").glob("actor_walk_package_*.zip"))
            retried = harness.post_json("/api/assemble-actor-walk", {
                "run_id": run_a,
                "source_digest": digest_a,
                "frames": frames_a,
                "approvals": approvals_a,
            })
            self.assertEqual(retried.status, 200)
            self.assertEqual(retried.json(), result)
            self.assertEqual(set((root / "generated").glob("actor_walk_package_*.zip")), package_names)
            self.assertIn(run_a, server.WALK_RUNS)
            self.assertTrue(all(token in server.WALK_VISUAL_APPROVALS for token in approvals_a.values()))
            self.assertEqual(len([record for record in server.WALK_ASSEMBLIES.values() if record["run_id"] == run_a]), 1)

            token = result["approval_provenance"]["assembly_token"]
            server.WALK_ASSEMBLIES.clear()  # durable URL remains valid after process state loss
            self.assertTrue(package_path.is_file())
            self.assertEqual(harness.post_json("/api/export-actor-walk", {"assembly_token": token}).status, 400)


if __name__ == "__main__":
    unittest.main()
