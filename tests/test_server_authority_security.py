import http.client
import socket
import threading
from unittest.mock import patch

import pytest

import server


VALID_HOSTS = ["localhost", "LOCALHOST:4184", "127.0.0.1", "127.0.0.1:65535", "[::1]", "[::1]:1"]
INVALID_AUTHORITIES = [
    "user@localhost", "localhost/path", "localhost?x", "localhost#x",
    " localhost", "localhost ", "local host", "localhost\t", "localhost\\evil",
    "http://localhost", "://localhost", "localhost://", "", "[]", "[::1", "::1",
    "[::2]", "localhost:", "localhost:0", "localhost:65536", "localhost:999999",
    "localhost:abc", "localhost:80:90", "127.0.0.1.evil",
]


@pytest.mark.parametrize("authority", VALID_HOSTS)
def test_host_authority_accepts_only_supported_loopback_serializations(authority):
    assert server.Handler._loopback_authority(authority)


@pytest.mark.parametrize("authority", INVALID_AUTHORITIES)
def test_host_authority_rejects_non_authority_and_malformed_values(authority):
    assert not server.Handler._loopback_authority(authority)


@pytest.mark.parametrize("origin", [
    "http://localhost", "https://LOCALHOST:4184", "http://127.0.0.1:1", "https://[::1]:65535",
])
def test_origin_parser_accepts_exact_http_loopback_origins(origin):
    assert server.Handler._loopback_origin(origin) is not None


@pytest.mark.parametrize("origin", [
    "localhost", "ftp://localhost", "HTTP://localhost", "http:/localhost", "http:///localhost",
    "http://", "http://user@localhost", "http://localhost/", "http://localhost/path",
    "http://localhost?x", "http://localhost#x", " http://localhost", "http://localhost ",
    "http://local host", "http://localhost\\evil", "http://[::1", "http://::1",
    "http://localhost:0", "http://localhost:65536", "http://localhost:abc",
])
def test_origin_parser_rejects_everything_except_exact_origin_serialization(origin):
    assert server.Handler._loopback_origin(origin) is None


def _request(method, host, origin=None):
    httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=3)
        headers = {"Host": host}
        if origin is not None:
            headers["Origin"] = origin
        conn.request(method, "/index.html", headers=headers)
        response = conn.getresponse()
        body = response.read()
        return response.status, dict(response.getheaders()), body
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)


def _raw_http10_request(method):
    """Send HTTP/1.0 without Host; http.client always synthesizes one."""
    httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        body = b'{"prompt":"must not be parsed"}' if method == "POST" else b""
        request = f"{method} /api/generate HTTP/1.0\r\n".encode("ascii")
        if body:
            request += f"Content-Length: {len(body)}\r\n".encode("ascii")
        request += b"\r\n" + body
        with socket.create_connection(("127.0.0.1", httpd.server_port), timeout=3) as sock:
            sock.sendall(request)
            response = bytearray()
            while chunk := sock.recv(65536):
                response.extend(chunk)
        head, _, response_body = bytes(response).partition(b"\r\n\r\n")
        status = int(head.split(b"\r\n", 1)[0].split()[1])
        headers = {}
        for line in head.split(b"\r\n")[1:]:
            name, value = line.split(b":", 1)
            headers[name.decode("ascii")] = value.strip().decode("ascii")
        return status, headers, response_body
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)


@pytest.mark.parametrize("method", ["GET", "HEAD", "POST", "OPTIONS"])
def test_http10_missing_host_is_forbidden_before_request_processing(method):
    guards = {"GET": "send_head", "HEAD": "send_head"}
    guard = guards.get(method)
    context = (
        patch.object(server.Handler, guard, side_effect=AssertionError("file lookup occurred"))
        if guard else patch.object(server.json, "loads", side_effect=AssertionError("body parsed"))
    )
    with context:
        status, headers, body = _raw_http10_request(method)

    assert status == 403
    assert headers["Vary"] == "Origin"
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    if method == "HEAD":
        assert body == b""
    else:
        assert b"Forbidden origin or host" in body


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_hostile_host_blocks_static_request_before_file_lookup(method):
    with patch.object(server.Handler, "send_head", side_effect=AssertionError("file lookup occurred")):
        status, headers, body = _request(method, "evil.example")
    assert status == 403
    assert headers["Vary"] == "Origin"
    if method == "HEAD":
        assert body == b""


def test_valid_static_get_preserves_app_and_normalizes_cors_origin():
    status, headers, body = _request("GET", "LOCALHOST:4184", "https://LOCALHOST:4184")
    assert status == 200
    assert body
    assert headers["Access-Control-Allow-Origin"] == "https://localhost:4184"
    assert headers["Vary"] == "Origin"


def test_no_origin_cli_request_remains_allowed():
    status, headers, body = _request("GET", "127.0.0.1")
    assert status == 200
    assert "Access-Control-Allow-Origin" not in headers
    assert body
