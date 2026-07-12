import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import server


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_server.sh"
INDEX = ROOT / "index.html"
MAIN_JS = ROOT / "src" / "main.js"


class _FakeProvider:
    name = "fake-image-provider"
    display_name = "Fake Image Provider"

    def __init__(self):
        self.generate_calls = 0

    def is_available(self):
        return True

    def capabilities(self):
        return {"modalities": ["text", "image"], "max_reference_images": 2}

    def default_model(self):
        return "fake-image-v1"

    def generate(self, *_args, **_kwargs):
        self.generate_calls += 1
        raise AssertionError("health checks must not generate images")


class _QuietHandler(server.Handler):
    def log_message(self, _format, *_args):
        pass


class HermesEnvironmentTests(unittest.TestCase):
    def test_default_repo_uses_the_current_user_home(self):
        expected = Path("/tmp/asset-studio-home/.hermes/hermes-agent")
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(Path, "home", return_value=Path("/tmp/asset-studio-home")):
                self.assertEqual(server.resolve_hermes_repo(), expected)

    def test_explicit_repo_overrides_the_default_and_expands_home(self):
        expected = Path.home() / "custom-hermes"
        with mock.patch.dict(os.environ, {"HERMES_REPO": "~/custom-hermes"}, clear=True):
            self.assertEqual(server.resolve_hermes_repo(), expected)

    def test_hermes_home_discovers_nested_agent_repo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir) / "hermes-home"
            repo = home / "hermes-agent"
            provider = repo / "plugins/image_gen/openai-codex/__init__.py"
            provider.parent.mkdir(parents=True)
            provider.write_text("", encoding="utf-8")

            with mock.patch.dict(os.environ, {"HERMES_HOME": str(home)}, clear=True):
                self.assertEqual(server.resolve_hermes_repo(), repo)

    def test_path_command_discovers_its_owning_agent_repo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "hermes-agent"
            provider = repo / "plugins/image_gen/openai-codex/__init__.py"
            command = repo / "venv/bin/hermes"
            provider.parent.mkdir(parents=True)
            command.parent.mkdir(parents=True)
            provider.write_text("", encoding="utf-8")
            command.write_text("", encoding="utf-8")

            with mock.patch.dict(os.environ, {}, clear=True), mock.patch(
                "shutil.which", return_value=str(command)
            ):
                self.assertEqual(server.resolve_hermes_repo(), repo.resolve())

    def test_runner_exports_default_repo_before_selecting_python(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir) / "home"
            home.mkdir()
            fake_python = Path(temp_dir) / "python"
            fake_python.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$HERMES_REPO\"\n"
                "if [[ \"${1:-}\" == \"-\" ]]; then cat >/dev/null; fi\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            env = os.environ.copy()
            env.pop("HERMES_REPO", None)
            env.update({"HOME": str(home), "ASSET_STUDIO_PYTHON": str(fake_python)})

            completed = subprocess.run(
                ["bash", str(RUNNER)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

            expected = str(home / ".hermes/hermes-agent")
            self.assertEqual(completed.stdout.splitlines(), [expected, expected])

    def test_runner_defaults_to_high_quality_gpt_image(self):
        script = RUNNER.read_text(encoding="utf-8")
        self.assertIn(
            'OPENAI_IMAGE_MODEL="${OPENAI_IMAGE_MODEL:-gpt-image-2-high}"',
            script,
        )

    @unittest.skipUnless(server.PROVIDER_PATH.is_file(), "Hermes image provider is not installed")
    def test_installed_provider_imports_without_generating_an_image(self):
        provider = server.load_provider()

        self.assertEqual(type(provider).__name__, "OpenAICodexImageGenProvider")
        self.assertEqual(
            provider.capabilities(),
            {"modalities": ["text", "image"], "max_reference_images": 16},
        )

    def test_provider_health_reports_capabilities_without_generating(self):
        provider = _FakeProvider()
        with mock.patch.object(server, "load_provider", return_value=provider):
            health = server.provider_health()

        self.assertEqual(health["status"], "ready")
        self.assertTrue(health["available"])
        self.assertEqual(health["provider"], "fake-image-provider")
        self.assertEqual(health["default_model"], "fake-image-v1")
        self.assertEqual(health["capabilities"]["max_reference_images"], 2)
        self.assertEqual(provider.generate_calls, 0)

    def test_provider_health_fails_closed_without_exposing_exception_details(self):
        with mock.patch.object(
            server,
            "load_provider",
            side_effect=RuntimeError("/Users/example/private/provider/path"),
        ):
            health = server.provider_health()

        self.assertEqual(health["status"], "unavailable")
        self.assertFalse(health["available"])
        self.assertEqual(health["reason"], "provider_load_failed")
        self.assertNotIn("/Users/example", json.dumps(health))

    def test_provider_health_distinguishes_missing_installation(self):
        with mock.patch.object(server, "resolve_hermes_repo", return_value=Path("/missing/hermes")):
            health = server.provider_health()

        self.assertEqual(health["status"], "unavailable")
        self.assertEqual(health["reason"], "hermes_not_installed")
        self.assertEqual(health["integration_mode"], "hermes-openai-codex")
        self.assertNotIn("/missing/hermes", json.dumps(health))

    def test_provider_health_endpoint_returns_json_without_generating(self):
        provider = _FakeProvider()
        with mock.patch.object(server, "load_provider", return_value=provider):
            handler = _QuietHandler.__new__(_QuietHandler)
            handler.path = "/api/provider-health"
            handler.command = "GET"
            handler.headers = {}
            handler.wfile = io.BytesIO()
            handler.send_response = mock.Mock()
            handler.send_header = mock.Mock()
            handler.end_headers = mock.Mock()
            handler.do_GET()
            payload = json.loads(handler.wfile.getvalue())

        handler.send_response.assert_called_once_with(200)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["provider"], "fake-image-provider")
        self.assertEqual(provider.generate_calls, 0)

    def test_page_surfaces_provider_health_without_starting_generation(self):
        html = INDEX.read_text(encoding="utf-8")
        javascript = MAIN_JS.read_text(encoding="utf-8")

        self.assertIn('id="providerStatus"', html)
        self.assertIn("fetch('/api/provider-health')", javascript)
        self.assertIn("refreshProviderHealth();", javascript)
        self.assertIn('id="actorWalk4Start"', html)
        self.assertIn("'/api/generate-actor-master'", javascript)
        self.assertIn("'/api/generate-actor-frame'", javascript)
        self.assertIn("'/api/assemble-actor-walk4'", javascript)


if __name__ == "__main__":
    unittest.main()
