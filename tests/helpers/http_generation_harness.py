from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

import server


@dataclass(frozen=True)
class HarnessResponse:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> dict:
        return json.loads(self.body)


class GenerationHttpHarness:
    """Exercise the real request handler without binding a local socket."""

    def __init__(self, provider, generated_dir: Path):
        self.provider = provider
        self.generated_dir = Path(generated_dir)

    def post_json(self, path: str, payload: dict) -> HarnessResponse:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        status: list[int] = []
        headers: dict[str, str] = {}
        handler = server.Handler.__new__(server.Handler)
        handler.path = path
        handler.command = "POST"
        handler.request_version = "HTTP/1.1"
        handler.headers = {
            "Host": "127.0.0.1",
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        handler.send_response = lambda code: status.append(code)
        handler.send_header = lambda name, value: headers.__setitem__(name, value)
        handler.end_headers = lambda: None

        self.generated_dir.mkdir(parents=True, exist_ok=True)
        with mock.patch.object(server, "load_provider", return_value=self.provider):
            with mock.patch.object(server, "GENERATED", self.generated_dir):
                handler.do_POST()

        if len(status) != 1:
            raise AssertionError(f"Expected one response status, received {status!r}")
        return HarnessResponse(status=status[0], headers=headers, body=handler.wfile.getvalue())

    def get_json(self, path: str) -> HarnessResponse:
        status: list[int] = []
        headers: dict[str, str] = {}
        handler = server.Handler.__new__(server.Handler)
        handler.path = path
        handler.command = "GET"
        handler.request_version = "HTTP/1.1"
        handler.headers = {"Host": "127.0.0.1"}
        handler.wfile = io.BytesIO()
        handler.send_response = lambda code: status.append(code)
        handler.send_header = lambda name, value: headers.__setitem__(name, value)
        handler.end_headers = lambda: None

        handler.do_GET()

        if len(status) != 1:
            raise AssertionError(f"Expected one response status, received {status!r}")
        return HarnessResponse(status=status[0], headers=headers, body=handler.wfile.getvalue())
