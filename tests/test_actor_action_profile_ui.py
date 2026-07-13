from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.helpers.js_runtime_harness import JavaScriptRuntimeHarness


ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads(
    (ROOT / "profiles" / "generic-pixel-actor-v1.json").read_text(encoding="utf-8")
)
HARNESS = JavaScriptRuntimeHarness(ROOT / "src" / "main.js")


class ActorActionProfileUiTests(unittest.TestCase):
    def test_profile_populates_actions_and_owns_the_request_contract(self):
        result = HARNESS.run_json(
            names=(
                "actorOutputProfileState",
                "ACTOR_ACTION_ALIASES",
                "validateActorOutputProfile",
                "actorActionRecipe",
                "applyActorOutputProfileUi",
                "inferReferenceDirection",
                "buildSpriteContract",
            ),
            prelude="""
const controls = {
  pixelAnimationPreset: { value: 'dodge', innerHTML: '' },
  pixelTargetDirection: { value: 'S', innerHTML: '' },
  pixelReferenceDirection: { value: 'S' },
  pixelDirectionMode: {
    value: '8dir',
    options: [
      { value: 'single', disabled: false },
      { value: '4dir', disabled: false },
      { value: '8dir', disabled: false },
    ],
    get selectedOptions() { return this.options.filter(option => option.value === this.value); },
  },
  pixelWalkFrames: { value: '1', disabled: false },
  pixelChromaMode: { value: 'global' },
  pixelPalette: { value: 'limited palette' },
  runDirectionalPixelPack: { hidden: false },
};
const $ = id => controls[id] || null;
const controlValue = (id, fallback = '') => controls[id]?.value ?? fallback;
""",
            script=f"""
const validated = validateActorOutputProfile({json.dumps(PROFILE)});
actorOutputProfileState = {{ status: 'ready', ...validated }};
applyActorOutputProfileUi();
const contract = buildSpriteContract('character');
console.log(JSON.stringify({{
  actionIds: [...validated.actions.keys()],
  actionHtml: controls.pixelAnimationPreset.innerHTML,
  frameValue: controls.pixelWalkFrames.value,
  frameDisabled: controls.pixelWalkFrames.disabled,
  directionMode: controls.pixelDirectionMode.value,
  directionalPackHidden: controls.runDirectionalPixelPack.hidden,
  contract,
}}));
""",
        )

        expected_actions = [action["id"] for action in PROFILE["actions"]]
        self.assertEqual(expected_actions, result["actionIds"])
        for action_id in expected_actions:
            self.assertIn(f'value="{action_id}"', result["actionHtml"])
        self.assertTrue(result["frameDisabled"])
        self.assertEqual(str(next(action["frame_count"] for action in PROFILE["actions"] if action["id"] == "dodge")), result["frameValue"])
        self.assertEqual("8dir", result["directionMode"])
        self.assertFalse(result["directionalPackHidden"])

        dodge = next(action for action in PROFILE["actions"] if action["id"] == "dodge")
        contract = result["contract"]
        self.assertEqual(PROFILE["id"], contract["output_profile_id"])
        self.assertEqual("dodge", contract["animation_mode"])
        self.assertEqual(dodge["frame_count"], contract["frame_count"])
        self.assertEqual(dodge["fps"], contract["fps"])
        self.assertEqual(dodge["loop"], contract["loop"])
        self.assertEqual(dodge["beats"], contract["beats"])


if __name__ == "__main__":
    unittest.main()
