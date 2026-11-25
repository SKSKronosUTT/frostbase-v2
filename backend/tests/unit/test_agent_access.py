"""Allowlist de origen de agent-read (B5): lógica pura."""

from starlette.requests import Request

from app.services.ai_agent.access import client_ip, is_ip_allowed


def _request(*, headers: dict[str, str] | None = None, host: str = "192.168.1.10"):
    raw_headers = [
        (key.lower().encode(), value.encode()) for key, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": raw_headers,
            "client": (host, 1234),
        }
    )


def test_empty_allowlist_allows_everything():
    assert is_ip_allowed("203.0.113.5", "") is True
    assert is_ip_allowed(None, "  ") is True


def test_cidr_and_exact_ip():
    assert is_ip_allowed("10.0.0.5", "10.0.0.0/24") is True
    assert is_ip_allowed("10.0.1.5", "10.0.0.0/24") is False
    assert is_ip_allowed("192.168.0.103", "192.168.0.103/32") is True
    assert is_ip_allowed("2001:db8::1", "2001:db8::/32") is True
    assert is_ip_allowed("not-an-ip", "10.0.0.0/24") is False
    assert is_ip_allowed(None, "10.0.0.0/24") is False


def test_forwarded_for_only_when_trusted():
    request = _request(headers={"X-Forwarded-For": "10.1.2.3, 10.0.0.1"})
    assert client_ip(request, trust_forwarded_for=True) == "10.1.2.3"
    assert client_ip(request, trust_forwarded_for=False) == "192.168.1.10"
