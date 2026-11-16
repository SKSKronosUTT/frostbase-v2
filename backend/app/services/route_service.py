from sqlalchemy.orm import Session

from app.models.route import DeliveryPoint, Route
from app.repositories import routes as routes_repo
from app.repositories import trucks as trucks_repo
from app.schemas.common import Page
from app.schemas.route import DeliveryPointIn, RouteCreate, RouteOut, RouteUpdate
from app.services import routing
from app.services.serializers import serialize_route


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


def list_routes(
    db: Session,
    *,
    search: str | None,
    status: str | None,
    page: int,
    page_size: int,
) -> Page[RouteOut]:
    routes, total = routes_repo.list_paginated(
        db, search=search, status=status, page=page, page_size=page_size
    )
    return Page(
        items=[serialize_route(route) for route in routes],
        total=total,
        page=page,
        page_size=page_size,
    )


def get_route(db: Session, route_id: int) -> RouteOut:
    return serialize_route(_get_or_fail(db, route_id))


def create_route(db: Session, payload: RouteCreate) -> RouteOut:
    geometry, warning = _calculate(payload.points)
    route = Route(
        name=_route_name(payload.points),
        description=payload.description,
        status=payload.status,
        geometry=geometry,
    )
    route.points = _build_points(payload.points)
    routes_repo.create(db, route)
    route = _get_or_fail(db, route.id)
    return serialize_route(route, warning=warning)


def update_route(db: Session, route_id: int, payload: RouteUpdate) -> RouteOut:
    route = _get_or_fail(db, route_id)
    geometry, warning = _calculate(payload.points)
    route.name = _route_name(payload.points)
    route.description = payload.description
    if payload.status is not None:
        route.status = payload.status
    route.geometry = geometry
    routes_repo.replace_points(db, route, _build_points(payload.points))
    routes_repo.commit(db, route)
    route = _get_or_fail(db, route.id)
    return serialize_route(route, warning=warning)


def calculate_route(db: Session, route_id: int) -> RouteOut:
    route = _get_or_fail(db, route_id)
    if len(route.points) < 2:
        raise RouteValidationError("La ruta necesita al menos dos puntos")
    try:
        geometry = routing.calculate_geometry(
            [(point.latitude, point.longitude) for point in route.points]
        )
    except routing.RoutingUnavailableError as exc:
        raise RouteValidationError(str(exc)) from exc
    route.geometry = geometry
    routes_repo.commit(db, route)
    route = _get_or_fail(db, route.id)
    return serialize_route(route)


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
    db.add(truck)
    db.commit()
    route = _get_or_fail(db, route.id)
    return serialize_route(route)
