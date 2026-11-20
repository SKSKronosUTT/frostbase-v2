import asyncio

from app.core.http import CircuitBreaker, close_http_client, get_http_client


def test_circuit_breaker_opens_and_recovers(monkeypatch):
    now = 100.0
    monkeypatch.setattr("app.core.http.time.monotonic", lambda: now)
    breaker = CircuitBreaker("test", failure_threshold=2, recovery_seconds=10)

    assert breaker.allow() is True
    breaker.record_failure()
    assert breaker.allow() is True
    breaker.record_failure()
    assert breaker.allow() is False

    now = 111.0
    assert breaker.allow() is True
    breaker.record_success()
    assert breaker.allow() is True
    assert breaker.state == "closed"


def test_http_client_lifecycle():
    client = get_http_client()
    assert client is get_http_client()
    asyncio.run(close_http_client())
    assert get_http_client() is not client
    asyncio.run(close_http_client())
