from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import server
from asset_studio.output_profiles import (
    action_recipe_for_profile,
    load_output_profile,
    load_output_profile_by_id,
)


ROOT = Path(__file__).resolve().parents[1]
GENERIC_PROFILE = ROOT / "profiles" / "generic-pixel-actor-v1.json"


def actor_payload(action: str, *, frame_count: int = 1) -> dict:
    return {
        "asset_family": "sprite",
        "asset_type": "character",
        "prompt": "armored courier",
        "sprite": {
            "output_profile_id": "generic-pixel-actor-v1",
            "animation_mode": action,
            "direction_mode": "single",
            "target_direction": "S",
            "reference_direction": "S",
            "frame_count": frame_count,
            "walk_frames": frame_count,
            "chroma_mode": "global",
        },
    }


class ActorActionProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = load_output_profile(GENERIC_PROFILE)

    def test_server_action_matrix_is_derived_from_the_default_profile(self):
        expected = {action["id"] for action in self.profile["actions"]}
        self.assertEqual(expected, set(server.SPRITE_ACTION_MATRIX))
        for action in self.profile["actions"]:
            spec = server.SPRITE_ACTION_MATRIX[action["id"]]
            self.assertEqual(action["frame_count"], spec["frames"])
            self.assertEqual(action["beats"], spec["columns"])
            self.assertEqual(action["prompt_contract"], spec["contract"])

    def test_normalizer_uses_profile_values_instead_of_client_frame_luck(self):
        normalized = server.normalize_asset_generation_payload(
            actor_payload("run", frame_count=1)
        )["sprite"]
        recipe = action_recipe_for_profile(self.profile, "run")

        self.assertEqual("generic-pixel-actor-v1", normalized["output_profile_id"])
        self.assertEqual("run", normalized["animation_mode"])
        self.assertEqual(recipe["frame_count"], normalized["frame_count"])
        self.assertEqual(recipe["frame_count"], normalized["walk_frames"])
        self.assertEqual(recipe["fps"], normalized["fps"])
        self.assertEqual(recipe["loop"], normalized["loop"])
        self.assertEqual(recipe["terminal"], normalized["terminal"])
        self.assertEqual(recipe["beats"], normalized["beats"])
        self.assertEqual(self.profile["frame"], normalized["frame"])
        self.assertEqual(recipe["pivot"], normalized["pivot"])

    def test_unknown_action_is_rejected_instead_of_silently_becoming_idle(self):
        with self.assertRaisesRegex(ValueError, "Unknown actor action"):
            server.normalize_asset_generation_payload(actor_payload("moonwalk"))

    def test_prompt_uses_the_profile_recipe_for_non_legacy_action(self):
        prompt = server.build_asset_family_prompt(
            server.normalize_asset_generation_payload(actor_payload("dodge"))
        )
        recipe = action_recipe_for_profile(self.profile, "dodge")

        self.assertIn(recipe["prompt_contract"], prompt)
        for beat in recipe["beats"]:
            self.assertIn(beat, prompt)

    def test_reference_prompt_uses_the_same_non_legacy_action_recipe(self):
        prompt = server.build_reference_sprite_prompt(
            "armored courier",
            animation_mode="dodge",
            output_profile_id="generic-pixel-actor-v1",
        )
        recipe = action_recipe_for_profile(self.profile, "dodge")

        self.assertIn(recipe["prompt_contract"], prompt)
        self.assertIn(f"Frame count: exactly {recipe['frame_count']}", prompt)
        for beat in recipe["beats"]:
            self.assertIn(beat, prompt)

    def test_loader_accepts_a_new_profile_action_without_server_code_changes(self):
        custom = copy.deepcopy(self.profile)
        custom["id"] = "custom-actor-v1"
        custom["title"] = "Custom actor"
        custom_action = copy.deepcopy(custom["actions"][0])
        custom_action.update({
            "id": "taunt",
            "beats": ["ready", "gesture", "hold", "recover"],
            "prompt_contract": "perform a readable taunt while staying on the root",
            "acceptance": "the gesture must read as a taunt and preserve identity",
        })
        custom["actions"] = [custom_action]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "custom-actor-v1.json"
            path.write_text(json.dumps(custom), encoding="utf-8")
            loaded = load_output_profile_by_id("custom-actor-v1", Path(directory))

        self.assertEqual("taunt", action_recipe_for_profile(loaded, "taunt")["id"])


if __name__ == "__main__":
    unittest.main()
