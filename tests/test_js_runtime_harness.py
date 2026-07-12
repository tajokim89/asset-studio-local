import unittest
from pathlib import Path

from tests.helpers.js_runtime_harness import JavaScriptRuntimeHarness


ROOT = Path(__file__).resolve().parents[1]


class JavaScriptRuntimeHarnessTests(unittest.TestCase):
    def setUp(self):
        self.harness = JavaScriptRuntimeHarness(ROOT / "src" / "main.js")

    def test_executes_extracted_production_function_and_constant(self):
        result = self.harness.run_json(
            names=("DEFAULT_STYLE_PROFILE", "normalizeStyleProfile"),
            script="process.stdout.write(JSON.stringify(normalizeStyleProfile(DEFAULT_STYLE_PROFILE)));",
        )

        self.assertEqual(result["schema_version"], "asset-studio.style-profile/v1")
        self.assertEqual(result["palette"]["mode"], "limited")

    def test_fake_dom_prelude_supplies_real_control_adapter(self):
        result = self.harness.run_json(
            names=("controlValue",),
            prelude=(
                "const controls={assetSubtype:{value:'character'}};\n"
                "const $=id=>controls[id]??null;"
            ),
            script=(
                "process.stdout.write(JSON.stringify({"
                "present:controlValue('assetSubtype','fallback'),"
                "missing:controlValue('missing','fallback')}));"
            ),
        )

        self.assertEqual(result, {"present": "character", "missing": "fallback"})

    def test_async_function_extraction_keeps_async_prefix(self):
        source = self.harness.source_for("preflightResultImage")

        self.assertTrue(source.startswith("async function preflightResultImage("))

    def test_missing_production_symbol_fails_before_node_execution(self):
        with self.assertRaisesRegex(AssertionError, "missingSymbol"):
            self.harness.source_for("missingSymbol")


if __name__ == "__main__":
    unittest.main()
