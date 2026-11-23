"""Pruebas del script de sondeo del agente (A0)."""

import json

import httpx
import pytest

from scripts.ai_probe import _assert_private_host, _payload_for, probe_http


def test_private_host_guard_allows_private_and_localhost():
    _assert_private_host("192.168.4.1", allow_public=False)
    _assert_private_host("10.0.0.10", allow_public=False)
    _assert_private_host("127.0.0.1", allow_public=False)
    _assert_private_host("localhost", allow_public=False)
    _assert_private_host("esp-claw.local", allow_public=False)


def test_private_host_guard_rejects_public_ip():
    with pytest.raises(SystemExit):
        _assert_private_host("8.8.8.8", allow_public=False)


def test_private_host_guard_allows_public_with_flag():
    _assert_private_host("8.8.8.8", allow_public=True)


def test_payload_for_plain_text():
    assert _payload_for("{message}", "hola") == "hola"


def test_payload_for_json_template_escapes_quotes():
    payload = _payload_for('{"message": "{message}"}', 'dime "esto"')
    assert json.loads(payload)["message"] == 'dime "esto"'


def test_probe_http_reports_status_and_preview():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/status":
            return httpx.Response(
                200,
                json={"status": "ok"},
                headers={"content-type": "application/json"},
            )
        return httpx.Response(404, text="not found")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=2) as client:
        results = probe_http(
            client, "http://192.168.4.1", ["/api/status", "/nope"], None
        )

    assert results[0]["status"] == 200
    assert '"status"' in results[0]["body_preview"]
    assert '"ok"' in results[0]["body_preview"]
    assert results[1]["status"] == 404
