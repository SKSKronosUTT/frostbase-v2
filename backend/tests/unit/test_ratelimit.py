from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.responses import Response

from app.core.ratelimit import MemoryBackend, RateLimit, client_ip


def _request(ip: str = "127.0.0.1"):
    return SimpleNamespace(client=SimpleNamespace(host=ip), headers={})


def test_memory_backend_sliding_window(monkeypatch):
    now = 100.0
    monkeypatch.setattr("app.core.ratelimit.time.monotonic", lambda: now)
    backend = MemoryBackend()

    first = backend.hit("key", limit=2, window_seconds=10)
    assert first.allowed is True
    assert first.remaining == 1

    second = backend.hit("key", limit=2, window_seconds=10)
    assert second.allowed is True
    assert second.remaining == 0

    third = backend.hit("key", limit=2, window_seconds=10)
    assert third.allowed is False
    assert third.retry_after >= 1

    now = 112.0
    fourth = backend.hit("key", limit=2, window_seconds=10)
    assert fourth.allowed is True


def test_rate_limit_check_sets_headers_and_raises():
    limiter = RateLimit("test", limit=1, window_seconds=60)
    request = _request()
    response = Response()
    assert limiter.check(request, response) is not None
    assert response.headers["X-RateLimit-Limit"] == "1"

    with pytest.raises(HTTPException) as exc:
        limiter.check(request, response)
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers


def test_rate_limit_extra_key_is_independent():
    limiter = RateLimit("device", limit=1, window_seconds=60)
    request = _request()
    limiter.check(request, extra="a")
    limiter.check(request, extra="b")

    with pytest.raises(HTTPException):
        limiter.check(request, extra="a")


def test_client_ip_falls_back():
    assert client_ip(_request("10.0.0.1")) == "10.0.0.1"
    assert client_ip(SimpleNamespace(client=None, headers={})) == "unknown"
