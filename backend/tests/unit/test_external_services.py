import asyncio

import httpx
import pytest

from app.models.setting import Setting
from app.services import routing, weather_service


class FakeResponse:
    def __init__(self, payload=None, error=None):
        self.payload = payload or {}
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, response):
        self.response = response

    async def get(self, *args, **kwargs):
        return self.response


def _setting() -> Setting:
    return Setting(
        id=1,
        weather_city="Tijuana",
        weather_latitude=32.5,
        weather_longitude=-117.0,
    )


def test_weather_success_and_cache(monkeypatch):
    weather_service._breaker.record_success()
    weather_service._cache.clear()
    monkeypatch.setattr(
        weather_service,
        "get_http_client",
        lambda: FakeClient(
            FakeResponse(
                {
                    "current": {
                        "temperature_2m": 21.0,
                        "relative_humidity_2m": 50,
                        "weather_code": 0,
                        "wind_speed_10m": 5.0,
                        "time": "2026-11-20T12:00:00Z",
                    }
                }
            )
        ),
    )
    monkeypatch.setattr(
        weather_service.settings_service, "get_settings", lambda db: _setting()
    )

    result = asyncio.run(weather_service.get_weather(None))
    assert result.available is True
    assert result.city == "Tijuana"
    assert result.condition == "Despejado"

    cached = asyncio.run(weather_service.get_weather(None))
    assert cached.available is True


def test_weather_failure_returns_unavailable(monkeypatch):
    weather_service._breaker.record_success()
    weather_service._cache.clear()
    monkeypatch.setattr(
        weather_service,
        "get_http_client",
        lambda: FakeClient(FakeResponse(error=httpx.ConnectError("boom"))),
    )
    monkeypatch.setattr(
        weather_service.settings_service, "get_settings", lambda db: _setting()
    )

    result = asyncio.run(weather_service.get_weather(None))
    assert result.available is False
    assert result.error


def test_weather_circuit_breaker_returns_stale(monkeypatch):
    weather_service._breaker.record_success()
    weather_service._cache.clear()
    setting = _setting()
    key = (
        round(setting.weather_latitude, 4),
        round(setting.weather_longitude, 4),
        setting.weather_city,
    )
    weather_service._cache[key] = (
        0.0,
        {
            "available": True,
            "city": setting.weather_city,
            "temperature": 20.0,
            "humidity": 50,
            "wind_speed": 1.0,
            "condition": "Despejado",
            "icon": "fa-sun",
            "updated_at": None,
            "error": None,
        },
    )
    for _ in range(3):
        weather_service._breaker.record_failure()
    monkeypatch.setattr(
        weather_service.settings_service, "get_settings", lambda db: setting
    )

    result = asyncio.run(weather_service.get_weather(None))
    assert result.stale is True
    weather_service._breaker.record_success()


def test_routing_async_success(monkeypatch):
    routing._breaker.record_success()
    monkeypatch.setattr(
        routing,
        "get_http_client",
        lambda: FakeClient(
            FakeResponse(
                {
                    "routes": [
                        {"geometry": {"coordinates": [[-117.0, 32.5], [-117.1, 32.6]]}}
                    ]
                }
            )
        ),
    )
    geometry = asyncio.run(
        routing.calculate_geometry_async([(32.5, -117.0), (32.6, -117.1)])
    )
    assert geometry == [[32.5, -117.0], [32.6, -117.1]]


def test_routing_async_failure(monkeypatch):
    routing._breaker.record_success()
    monkeypatch.setattr(
        routing,
        "get_http_client",
        lambda: FakeClient(FakeResponse(error=httpx.ConnectError("boom"))),
    )
    with pytest.raises(routing.RoutingUnavailableError):
        asyncio.run(routing.calculate_geometry_async([(1, 2), (3, 4)]))


def test_routing_requires_two_points():
    with pytest.raises(routing.RoutingUnavailableError):
        asyncio.run(routing.calculate_geometry_async([(1, 2)]))
