from __future__ import annotations

import time
from pathlib import Path

import server


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "src" / "main.js").read_text(encoding="utf-8")
SERVER_TEXT = (ROOT / "server.py").read_text(encoding="utf-8")


def _wait_for_terminal(job_id: str, timeout: float = 1.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = server.get_generation_job(job_id)
        if job and job["status"] in {"succeeded", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("generation job did not finish")


def test_generation_job_returns_immediately_and_finishes_in_background():
    release_at = time.monotonic() + 0.08

    def slow_runner(endpoint: str, payload: dict) -> dict:
        while time.monotonic() < release_at:
            time.sleep(0.005)
        return {"success": True, "url": "/assets/generated/example.png", "endpoint": endpoint, "echo": payload}

    started = time.monotonic()
    submitted = server.create_generation_job(
        "/api/generate",
        {"prompt": "bambi on a sci-fi motorcycle"},
        runner=slow_runner,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 0.05
    assert submitted["status"] == "queued"
    job = _wait_for_terminal(submitted["job_id"])
    assert job["status"] == "succeeded"
    assert job["result"]["url"] == "/assets/generated/example.png"


def test_generation_job_records_runner_failures():
    def failing_runner(endpoint: str, payload: dict) -> dict:
        raise RuntimeError("provider unavailable")

    submitted = server.create_generation_job(
        "/api/generate-reference",
        {"prompt": "one image"},
        runner=failing_runner,
    )
    job = _wait_for_terminal(submitted["job_id"])

    assert job["status"] == "failed"
    assert "provider unavailable" in job["error"]
    assert "result" not in job


def test_http_and_frontend_expose_async_submit_and_poll_contract():
    assert 'path == "/api/generation-jobs"' in SERVER_TEXT
    assert 'path.startswith("/api/generation-jobs/")' in SERVER_TEXT
    assert "function submitGenerationJob" in JS
    assert "function waitForGenerationJob" in JS
    assert "await submitGenerationJob(endpoint, payload)" in JS
    assert "await waitForGenerationJob" in JS
    assert "setTimeout" in JS
