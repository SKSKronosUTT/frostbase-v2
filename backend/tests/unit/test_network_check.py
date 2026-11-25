"""Script de diagnóstico de red: lógica pura sin tocar la red real."""

from scripts.network_check import (
    backend_host_port,
    probe_agent_read,
    probe_health,
    suggested_hosts,
)


def test_backend_host_port_uses_configured_url():
    assert backend_host_port("http://192.168.1.20:9000", None) == (
        "192.168.1.20",
        9000,
    )
    assert backend_host_port("", "192.168.1.45") == ("192.168.1.45", 8050)


def test_suggested_hosts_adds_local_defaults_and_new_ip():
    assert (
        suggested_hosts("localhost,127.0.0.1,testserver", "192.168.1.45")
        == "localhost,127.0.0.1,testserver,192.168.1.45"
    )
    assert suggested_hosts("", "10.0.0.5") == "localhost,127.0.0.1,10.0.0.5"


def test_agent_read_requires_token():
    result = probe_agent_read("http://127.0.0.1:1", "", 0.1)
    assert result.ok is False
    assert "token" in result.detail.lower()


def test_health_probe_handles_unreachable(monkeypatch):
    import scripts.network_check as module

    def boom(*_args, **_kwargs):
        raise module.httpx.ConnectError("down")

    monkeypatch.setattr(module.httpx, "get", boom)
    result = probe_health("http://127.0.0.1:8050/health/ready", 0.1)
    assert result.ok is False
    assert result.detail == "ConnectError"
