from typing import Iterable

import httpx

from app.core.config import settings
from app.core.http import CircuitBreaker, get_http_client


class RoutingUnavailableError(Exception):
    pass


_breaker = CircuitBreaker("osrm", failure_threshold=3, recovery_seconds=60.0)


def _request_params() -> dict[str, str]:
    return {"overview": "full", "geometries": "geojson", "steps": "false"}


def _build_url(coordinates: list[tuple[float, float]]) -> str:
    coordinates_path = ";".join(
        f"{longitude},{latitude}" for latitude, longitude in coordinates
    )
    return f"{settings.osrm_base_url.rstrip('/')}/route/v1/driving/{coordinates_path}"


def _parse_payload(payload: dict) -> list[list[float]]:
    routes = payload.get("routes") or []
    if not routes:
        raise RoutingUnavailableError("OSRM no devolvió una ruta válida")

    raw_coordinates = (routes[0].get("geometry") or {}).get("coordinates") or []
    if len(raw_coordinates) < 2:
        raise RoutingUnavailableError("OSRM devolvió una geometría incompleta")

    return [[latitude, longitude] for longitude, latitude in raw_coordinates]


def _validate_coordinates(points: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    coordinates = list(points)
    if len(coordinates) < 2:
        raise RoutingUnavailableError(
            "Se necesitan al menos dos puntos para calcular la ruta"
        )
    return coordinates


async def calculate_geometry_async(
    points: Iterable[tuple[float, float]],
) -> list[list[float]]:
    coordinates = _validate_coordinates(points)
    if not _breaker.allow():
        raise RoutingUnavailableError(
            "El proveedor de rutas OSRM no está disponible en este momento"
        )

    try:
        client = get_http_client()
        response = await client.get(
            _build_url(coordinates),
            params=_request_params(),
            timeout=settings.osrm_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        _breaker.record_failure()
        raise RoutingUnavailableError(
            "El proveedor de rutas OSRM no está disponible en este momento"
        ) from exc

    _breaker.record_success()
    return _parse_payload(payload)


def calculate_geometry(points: Iterable[tuple[float, float]]) -> list[list[float]]:
    """Versión síncrona para scripts y tareas de mantenimiento."""
    coordinates = _validate_coordinates(points)
    if not _breaker.allow():
        raise RoutingUnavailableError(
            "El proveedor de rutas OSRM no está disponible en este momento"
        )

    try:
        with httpx.Client(timeout=settings.osrm_timeout_seconds) as client:
            response = client.get(
                _build_url(coordinates),
                params=_request_params(),
            )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        _breaker.record_failure()
        raise RoutingUnavailableError(
            "El proveedor de rutas OSRM no está disponible en este momento"
        ) from exc

    _breaker.record_success()
    return _parse_payload(payload)
