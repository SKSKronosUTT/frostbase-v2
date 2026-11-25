import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _settings(**overrides) -> Settings:
    values = {
        "secret_key": "a" * 64,
        "device_key_pepper": "b" * 64,
        "admin_password": "StrongPass123!",
    }
    values.update(overrides)
    return Settings(**values)


def test_agent_read_allowlist_accepts_cidrs():
    config = _settings(
        ai_agent_read_allowed_ips="192.168.0.0/24, 10.0.0.5, 2001:db8::/32"
    )
    assert len(config.ai_agent_read_allowed_networks) == 3


def test_agent_read_allowlist_rejects_invalid_cidr():
    with pytest.raises(ValidationError):
        _settings(ai_agent_read_allowed_ips="192.168.0.0/24, nope")


def test_obsolete_settings_are_removed():
    for field in (
        "device_offline_seconds",
        "weather_city",
        "weather_latitude",
        "weather_longitude",
    ):
        assert field not in Settings.model_fields
