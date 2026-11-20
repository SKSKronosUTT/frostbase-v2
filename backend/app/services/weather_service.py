import logging
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings as app_settings
from app.core.http import CircuitBreaker, get_http_client
from app.schemas.dashboard import WeatherOut
from app.services import settings_service
from app.utils.time import utcnow

logger = logging.getLogger("frostbase.weather")

_cache: dict[tuple, tuple[float, dict]] = {}
_breaker = CircuitBreaker("open-meteo", failure_threshold=3, recovery_seconds=60.0)

WEATHER_CODES = {
    0: ("Despejado", "fa-sun"),
    1: ("Mayormente despejado", "fa-cloud-sun"),
    2: ("Parcialmente nublado", "fa-cloud-sun"),
    3: ("Nublado", "fa-cloud"),
    45: ("Niebla", "fa-smog"),
    48: ("Niebla con escarcha", "fa-smog"),
    51: ("Llovizna ligera", "fa-cloud-rain"),
    53: ("Llovizna", "fa-cloud-rain"),
    55: ("Llovizna intensa", "fa-cloud-rain"),
    61: ("Lluvia ligera", "fa-cloud-rain"),
    63: ("Lluvia", "fa-cloud-rain"),
    65: ("Lluvia intensa", "fa-cloud-showers-heavy"),
    71: ("Nieve ligera", "fa-snowflake"),
    73: ("Nieve", "fa-snowflake"),
    75: ("Nieve intensa", "fa-snowflake"),
    77: ("Granos de nieve", "fa-snowflake"),
    80: ("Chubascos", "fa-cloud-sun-rain"),
    81: ("Chubascos moderados", "fa-cloud-rain"),
    82: ("Chubascos fuertes", "fa-cloud-showers-heavy"),
    85: ("Chubascos de nieve", "fa-snowflake"),
    86: ("Nevada fuerte", "fa-snowflake"),
    95: ("Tormenta", "fa-bolt"),
    96: ("Tormenta con granizo", "fa-cloud-bolt"),
    99: ("Tormenta fuerte con granizo", "fa-cloud-bolt"),
}


def _describe(code: int | None) -> tuple[str, str]:
    if code is None:
        return ("Condición desconocida", "fa-cloud")
    return WEATHER_CODES.get(code, ("Condición desconocida", "fa-cloud"))


def _parse_time(value: str | None) -> datetime:
    if not value:
        return utcnow()
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return utcnow()
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def get_weather(db: Session) -> WeatherOut:
    setting = await run_in_threadpool(settings_service.get_settings, db)
    key = (
        round(setting.weather_latitude, 4),
        round(setting.weather_longitude, 4),
        setting.weather_city,
    )
    now = time.monotonic()
    cached = _cache.get(key)
    ttl = app_settings.weather_cache_seconds

    if cached and now - cached[0] < ttl:
        return WeatherOut(**{**cached[1], "stale": False})

    if not _breaker.allow():
        if cached:
            return WeatherOut(**{**cached[1], "stale": True})
        return WeatherOut(
            available=False,
            city=setting.weather_city,
            stale=True,
            error="El proveedor de clima no está disponible temporalmente",
        )

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": setting.weather_latitude,
        "longitude": setting.weather_longitude,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "timezone": "UTC",
    }
    try:
        client = get_http_client()
        response = await client.get(
            url,
            params=params,
            timeout=app_settings.weather_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        current = payload.get("current") or {}
        condition, icon = _describe(current.get("weather_code"))
        data = {
            "available": True,
            "city": setting.weather_city,
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "wind_speed": current.get("wind_speed_10m"),
            "condition": condition,
            "icon": icon,
            "updated_at": _parse_time(current.get("time")),
            "error": None,
        }
        _cache[key] = (now, data)
        _breaker.record_success()
        return WeatherOut(**data)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        _breaker.record_failure()
        logger.warning("No se pudo consultar Open-Meteo: %s", exc)
        if cached:
            return WeatherOut(**{**cached[1], "stale": True})
        return WeatherOut(
            available=False,
            city=setting.weather_city,
            error="No se pudo obtener el clima en este momento",
        )
