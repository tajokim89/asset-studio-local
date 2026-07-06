from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "server.py").read_text(encoding="utf-8")
RUNNER = (ROOT / "scripts" / "run_server.sh").read_text(encoding="utf-8")


def test_server_checks_runtime_dependencies_at_startup():
    assert "RUNTIME_DEPENDENCIES" in SERVER
    assert "check_runtime_dependencies()" in SERVER
    assert "Missing Python runtime dependencies" in SERVER
    assert "./scripts/run_server.sh" in SERVER


def test_runner_installs_missing_runtime_dependencies_before_serving():
    assert "requirements.txt" in RUNNER
    assert "pip" in RUNNER
    assert "install" in RUNNER
    assert "httpx>=0.28.0" in RUNNER
    assert "exec \"$PYTHON_BIN\" server.py" in RUNNER
