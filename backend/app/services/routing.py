from typing import Iterable

import httpx

from app.core.config import settings


class RoutingUnavailableError(Exception):
    pass


def calculate_geometry(points: Iterable[tuple[float, float]]) -> list[list[float]]:
    coordinates = list(points)
    if len(coordinates) < 2:
        raise RoutingUnavailableError("Se necesitan al menos dos puntos para calcular la ruta")

    coordinates_path = ";".join(
        f"{longitude},{latitude}" for latitude, longitude in coordinates
    )
    url = f"{settings.osrm_base_url.rstrip('/')}/route/v1/driving/{coordinates_path}"
    params = {"overview": "full", "geometries": "geojson", "steps": "false"}

    try:
        with httpx.Client(timeout=settings.osrm_timeout_seconds) as client:
            response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RoutingUnavailableError(
            "El proveedor de rutas OSRM no está disponible en este momento"
        ) from exc

    routes = payload.get("routes") or []
    if not routes:
        raise RoutingUnavailableError("OSRM no devolvió una ruta válida")

    raw_coordinates = (routes[0].get("geometry") or {}).get("coordinates") or []
    if len(raw_coordinates) < 2:
        raise RoutingUnavailableError("OSRM devolvió una geometría incompleta")

    return [[latitude, longitude] for longitude, latitude in raw_coordinates]
