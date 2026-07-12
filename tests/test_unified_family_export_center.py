from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.helpers.js_runtime_harness import JavaScriptRuntimeHarness


ROOT = Path(__file__).resolve().parents[1]
MAIN_JS = ROOT / "src" / "main.js"
REGISTRY_PATH = ROOT / "contracts" / "asset-recipes.json"


class UnifiedFamilyExportCenterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.harness = JavaScriptRuntimeHarness(MAIN_JS)
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.prelude = f"const registry = {json.dumps(cls.registry)};"

    def run_export_json(self, script: str, *, include_builder: bool = False):
        names = [
            "validateAndBuildRecipeViews",
            "migrateLegacyAssetSelection",
            "familyExportDescriptor",
        ]
        if include_builder:
            names.append("buildUnifiedFamilyExportPackage")
        return self.harness.run_json(
            names=tuple(names),
            prelude=self.prelude,
            script=script,
        )

    def test_descriptor_uses_registry_capability_for_canonical_and_alias_results(self):
        result = self.run_export_json(
            """
const cases = [
  ['sprite', 'character'],
  ['sprite', 'monster'],
  ['sprite', 'effect'],
  ['ui', 'button'],
  ['object', 'item'],
];
console.log(JSON.stringify(cases.map(([family, type]) =>
  familyExportDescriptor({ id:'r1', family, type, status:'succeeded' }, registry)
)));
"""
        )

        self.assertEqual(
            [(item["route"], item["options"]) for item in result],
            [
                ("actor", ["sheets", "frames", "fps", "pivot"]),
                ("actor", ["sheets", "frames", "fps", "pivot"]),
                ("effect", ["full-cell", "trim", "fps", "pivot"]),
                ("ui", ["states", "nine-slice", "safe-area"]),
                (
                    "object",
                    ["states", "pivot", "ground", "collision", "interaction"],
                ),
            ],
        )
        self.assertTrue(
            all(
                item["schema_version"]
                == "asset-studio.family-export-center/v1"
                for item in result
            )
        )

    def test_dispatch_invokes_one_production_builder_and_accepts_effect_manifest(self):
        result = self.run_export_json(
            r"""
const calls = [];
const mk = route => (...args) => {
  calls.push([route, args.length]);
  const manifest = route === 'effect'
    ? { schema_version:'asset-studio.effect-sequence/v1', kind:'effect_sequence' }
    : { schema_version:`asset-studio.${route}/v1`, family:route };
  return { manifest, files:[], zipName:`${route}.zip` };
};
const builders = { actor:mk('actor'), effect:mk('effect'), ui:mk('ui'), object:mk('object') };
const families = [['sprite','character'], ['sprite','effect'], ['ui','button'], ['object','item']];
const output = families.map(([family, type]) => buildUnifiedFamilyExportPackage(
  { id:'r1', family, type, status:'succeeded' },
  { frames:[], contract:{}, imageData:{}, gridContract:{} },
  {}, builders, registry
));
console.log(JSON.stringify({ calls, routes:output.map(item => item.exportCenter.route) }));
""",
            include_builder=True,
        )

        self.assertEqual(
            [item[0] for item in result["calls"]],
            ["actor", "effect", "ui", "object"],
        )
        self.assertEqual(
            result["routes"], ["actor", "effect", "ui", "object"]
        )

    def test_lab_failed_unknown_and_cross_family_options_fail_before_builder(self):
        result = self.run_export_json(
            r"""
let calls = 0;
const builders = {
  actor:() => { calls += 1; }, effect:() => { calls += 1; },
  tile:() => { calls += 1; }, ui:() => { calls += 1; }, object:() => { calls += 1; },
};
const errors = [];
for (const [candidate, options] of [
  [{ family:'audio', type:'x', status:'succeeded' }, {}],
  [{ family:'tile', type:'autotile', status:'succeeded' }, {}],
  [{ family:'sprite', type:'character', status:'failed' }, {}],
  [{ family:'ui', type:'button', status:'succeeded' }, { mode:'trim' }],
]) {
  try {
    buildUnifiedFamilyExportPackage(candidate, { imageData:{}, contract:{} }, options, builders, registry);
  } catch (error) {
    errors.push(error.message);
  }
}
console.log(JSON.stringify({ calls, errors }));
""",
            include_builder=True,
        )

        self.assertEqual(result["calls"], 0)
        self.assertEqual(len(result["errors"]), 4)

    def test_capability_options_are_detached_from_registry(self):
        result = self.run_export_json(
            """
const descriptor = familyExportDescriptor(
  { id:'r1', family:'sprite', type:'character', status:'succeeded' }, registry
);
descriptor.options.push('mutated');
const actor = registry.recipes.find(item => item.id === 'actor-animation');
console.log(JSON.stringify({ descriptor:descriptor.options, registry:actor.export_capability.options }));
"""
        )

        self.assertIn("mutated", result["descriptor"])
        self.assertNotIn("mutated", result["registry"])


if __name__ == "__main__":
    unittest.main()
