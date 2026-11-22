import logging

from sqlalchemy.orm import Session

from app.models.route import DeliveryPoint, Route
from app.repositories import driver as driver_repo
from app.repositories import routes as routes_repo
from app.repositories import trucks as trucks_repo
from app.schemas.common import OptionOut, Page
from app.schemas.route import (
    DeliveryPointIn,
    RouteCreate,
    RouteDriverIn,
    RouteOut,
    RouteUpdate,
)
from app.services import routing
from app.services.serializers import serialize_route

logger = logging.getLogger("frostbase.routes")


class RouteNotFoundError(Exception):
    pass


class RouteValidationError(Exception):
    pass


def _build_points(points: list[DeliveryPointIn]) -> list[DeliveryPoint]:
    return [
        DeliveryPoint(
            name=point.name.strip(),
            address=point.address,
            latitude=point.latitude,
            longitude=point.longitude,
            order_index=index,
        )
        for index, point in enumerate(points)
    ]


def _route_name(points: list[DeliveryPointIn]) -> str:
    return f"{points[0].name.strip()} - {points[-1].name.strip()}"


def _calculate(points: list[DeliveryPointIn]) -> tuple[list | None, str | None]:
    try:
        geometry = routing.calculate_geometry(
            [(point.latitude, point.longitude) for point in points]
        )
        return geometry, None
    except routing.RoutingUnavailableError as exc:
        return None, str(exc)


def _get_or_fail(db: Session, route_id: int) -> Route:
    route = routes_repo.get(db, route_id)
    if route is None:
        raise RouteNotFoundError("Ruta no encontrada")
    return route


def _geometry_status(geometry: list | None, warning: str | None) -> str:
    if geometry:
        return "ready"
    return "failed" if warning else "pending"


def list_routes(
    db: Session,
    *,
    search: str | None,
    status: str | None,
    missing_driver: bool | None = None,
    page: int,
    page_size: int,
) -> Page[RouteOut]:
    routes, total = routes_repo.list_paginated(
        db,
        search=search,
        status=status,
        missing_driver=missing_driver,
        page=page,
        page_size=page_size,
    )
    return Page(
        items=[serialize_route(route) for route in routes],
        total=total,
        page=page,
        page_size=page_size,
    )


def get_route(db: Session, route_id: int) -> RouteOut:
    return serialize_route(_get_or_fail(db, route_id))


def list_route_options(db: Session, *, search: str | None = None) -> list[OptionOut]:
    return [
        OptionOut(id=route_id, label=name)
        for route_id, name in routes_repo.list_options(db, search=search)
    ]


def get_route_points(db: Session, route_id: int) -> list[tuple[float, float]]:
    route = _get_or_fail(db, route_id)
    return [(point.latitude, point.longitude) for point in route.points]


def create_route(
    db: Session,
    payload: RouteCreate,
    *,
    geometry: list | None = None,
    warning: str | None = None,
    defer_geometry: bool = False,
) -> RouteOut:
    if defer_geometry:
        geometry, warning = None, None
    elif geometry is None and warning is None:
        geometry, warning = _calculate(payload.points)

    route = Route(
        name=_route_name(payload.points),
        description=payload.description,
        status=payload.status,
        geometry=geometry,
        geometry_status=_geometry_status(geometry, warning),
    )
    route.points = _build_points(payload.points)
    routes_repo.create(db, route)
    route = _get_or_fail(db, route.id)
    return serialize_route(route, warning=warning)


def update_route(
    db: Session,
    route_id: int,
    payload: RouteUpdate,
    *,
    geometry: list | None = None,
    warning: str | None = None,
    defer_geometry: bool = False,
) -> RouteOut:
    route = _get_or_fail(db, route_id)
    if defer_geometry:
        geometry, warning = None, None
    elif geometry is None and warning is None:
        geometry, warning = _calculate(payload.points)

    route.name = _route_name(payload.points)
    route.description = payload.description
    if payload.status is not None:
        route.status = payload.status
    route.geometry = geometry
    route.geometry_status = _geometry_status(geometry, warning)
    routes_repo.replace_points(db, route, _build_points(payload.points))
    routes_repo.save(db, route)
    route = _get_or_fail(db, route.id)
    return serialize_route(route, warning=warning)


def calculate_route(
    db: Session, route_id: int, *, geometry: list | None = None
) -> RouteOut:
    route = _get_or_fail(db, route_id)
    if len(route.points) < 2:
        raise RouteValidationError("La ruta necesita al menos dos puntos")
    if geometry is None:
        try:
            geometry = routing.calculate_geometry(
                [(point.latitude, point.longitude) for point in route.points]
            )
        except routing.RoutingUnavailableError as exc:
            route.geometry_status = "failed"
            routes_repo.save(db, route)
            raise RouteValidationError(str(exc)) from exc
    route.geometry = geometry
    route.geometry_status = "ready"
    routes_repo.save(db, route)
    route = _get_or_fail(db, route.id)
    return serialize_route(route)


async def calculate_geometry_background(route_id: int) -> None:
    """Calcula la geometría de una ruta en segundo plano (flag asíncrono)."""
    from app.core.database import SessionLocal

    try:
        with SessionLocal() as db:
            points = get_route_points(db, route_id)
        geometry = await routing.calculate_geometry_async(points)
    except (RouteNotFoundError, routing.RoutingUnavailableError) as exc:
        logger.warning(
            "No se pudo calcular la geometría de la ruta %s: %s", route_id, exc
        )
        with SessionLocal() as db, db.begin():
            route = routes_repo.get(db, route_id)
            if route is not None:
                route.geometry_status = "failed"
        return

    with SessionLocal() as db, db.begin():
        route = routes_repo.get(db, route_id)
        if route is not None:
            route.geometry = geometry
            route.geometry_status = "ready"


def delete_route(db: Session, route_id: int) -> None:
    route = _get_or_fail(db, route_id)
    for truck in trucks_repo.trucks_using_route(db, route.id):
        truck.route_id = None
        db.add(truck)
    db.flush()
    routes_repo.delete(db, route)


def assign_route(db: Session, route_id: int, truck_id: int) -> RouteOut:
    route = _get_or_fail(db, route_id)
    truck = trucks_repo.get(db, truck_id)
    if truck is None:
        raise RouteValidationError("El camión seleccionado no existe")
    for other in trucks_repo.trucks_using_route(db, route.id, except_id=truck.id):
        other.route_id = None
        db.add(other)
    truck.route_id = route.id
    # Se sincroniza la relación en memoria: una re-consulta devolvería el
    # valor precargado (stale) porque el objeto Route ya está en el identity
    # map de la sesión.
    route.truck = truck
    db.add(truck)
    db.flush()
    return serialize_route(route)


class RouteConflictError(Exception):
    """Conflicto de calendario: el conductor ya tiene ruta ese día."""


def assign_driver(
    db: Session,
    route_id: int,
    payload: RouteDriverIn,
    *,
    admin_id: int | None = None,
) -> RouteOut:
    """Asigna (o quita) el conductor dueño de la ruta y su calendario (G4).

    Reglas de G0/G4:

    - La ruta pertenece al conductor; el camión queda como vínculo legado.
    - El conductor debe estar activo (con o sin camión: la etiqueta del
      selector indica la placa o «sin camión»).
    - Una sola ruta por conductor y día de la semana (índice único + validación
      previa con mensaje claro).
    - ``driver_id = null`` quita al conductor y limpia el calendario.
    """
    route = _get_or_fail(db, route_id)

    if payload.driver_id is None:
        route.assigned_driver_id = None
        routes_repo.clear_delivery_days(db, route)
        routes_repo.save(db, route)
        route = _get_or_fail(db, route.id)
        return serialize_route(route)

    driver = driver_repo.get_by_id(db, payload.driver_id)
    if driver is None:
        raise RouteValidationError("El conductor seleccionado no existe")
    if not driver.is_active:
        raise RouteValidationError("El conductor está inactivo")

    conflicts = routes_repo.conflicting_delivery_days(
        db, driver.id, payload.weekdays, except_route_id=route.id
    )
    if conflicts:
        days = ", ".join(_weekday_label(day) for day in conflicts)
        raise RouteConflictError(f"El conductor ya tiene otra ruta asignada el {days}")

    route.assigned_driver_id = driver.id
    routes_repo.replace_delivery_days(db, route, driver.id, payload.weekdays)
    routes_repo.save(db, route)
    route = _get_or_fail(db, route.id)
    logger.info(
        "route_driver_assigned route_id=%s driver_id=%s days=%s admin_id=%s",
        route.id,
        driver.id,
        payload.weekdays,
        admin_id,
    )
    return serialize_route(route)


def _weekday_label(weekday: int) -> str:
    from app.schemas.route import WEEKDAY_LABELS  # noqa: PLC0415

    return WEEKDAY_LABELS[weekday]
