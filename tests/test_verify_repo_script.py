import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts" / "verify_repo.sh"


class VerifyRepoScriptTests(unittest.TestCase):
    def run_verify(self, *args):
        env = os.environ.copy()
        env.setdefault("HERMES_REPO", str(Path.home() / ".hermes/hermes-agent"))
        return subprocess.run(
            ["bash", str(VERIFY), *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_static_mode_checks_python_javascript_html_shell_and_diff(self):
        completed = self.run_verify("static")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("python: PASS", completed.stdout)
        self.assertIn("javascript: PASS", completed.stdout)
        self.assertIn("html: PASS", completed.stdout)
        self.assertIn("shell: PASS", completed.stdout)
        self.assertIn("diff: PASS", completed.stdout)

    def test_focused_mode_requires_at_least_one_test_path(self):
        completed = self.run_verify("focused")

        self.assertEqual(completed.returncode, 2)
        self.assertIn("focused mode requires at least one test path", completed.stderr)

    def test_unknown_mode_fails_with_usage(self):
        completed = self.run_verify("unknown")

        self.assertEqual(completed.returncode, 2)
        self.assertIn("Usage:", completed.stderr)


if __name__ == "__main__":
    unittest.main()
