from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.route import DeliveryPoint, Route, RouteDeliveryDay
from app.utils.search import escape_like


def _with_relations():
    return (
        selectinload(Route.points),
        selectinload(Route.truck),
    )


def get(db: Session, route_id: int) -> Route | None:
    return db.scalar(
        select(Route).options(*_with_relations()).where(Route.id == route_id)
    )


def list_paginated(
    db: Session,
    *,
    search: str | None = None,
    status: str | None = None,
    missing_driver: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Route], int]:
    stmt = select(Route).options(*_with_relations())
    count_stmt = select(func.count(Route.id))
    if search:
        pattern = f"%{escape_like(search.strip())}%"
        stmt = stmt.where(Route.name.ilike(pattern, escape="\\"))
        count_stmt = count_stmt.where(Route.name.ilike(pattern, escape="\\"))
    if status:
        stmt = stmt.where(Route.status == status)
        count_stmt = count_stmt.where(Route.status == status)
    if missing_driver is True:
        stmt = stmt.where(Route.assigned_driver_id.is_(None))
        count_stmt = count_stmt.where(Route.assigned_driver_id.is_(None))
    elif missing_driver is False:
        stmt = stmt.where(Route.assigned_driver_id.is_not(None))
        count_stmt = count_stmt.where(Route.assigned_driver_id.is_not(None))
    total = db.scalar(count_stmt) or 0
    stmt = (
        stmt.order_by(Route.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).unique()), total


def list_all(db: Session) -> list[Route]:
    return list(
        db.scalars(
            select(Route).options(*_with_relations()).order_by(Route.name)
        ).unique()
    )


def list_options(
    db: Session, *, search: str | None = None, limit: int = 500
) -> list[tuple[int, str]]:
    stmt = select(Route.id, Route.name).order_by(Route.name).limit(limit)
    if search:
        pattern = f"%{escape_like(search.strip())}%"
        stmt = stmt.where(Route.name.ilike(pattern, escape="\\"))
    return [(row[0], row[1]) for row in db.execute(stmt).all()]


def create(db: Session, route: Route) -> Route:
    db.add(route)
    db.flush()
    return route


def save(db: Session, route: Route) -> Route:
    db.add(route)
    db.flush()
    return route


def delete(db: Session, route: Route) -> None:
    db.delete(route)
    db.flush()


def replace_points(db: Session, route: Route, points: list[DeliveryPoint]) -> None:
    route.points.clear()
    db.flush()
    for index, point in enumerate(points):
        point.order_index = index
        point.route_id = route.id
        route.points.append(point)
    db.flush()


def replace_delivery_days(
    db: Session, route: Route, driver_id: int, weekdays: list[int]
) -> None:
    """Sustituye el calendario semanal de la ruta (G4).

    ``driver_id`` se guarda desnormalizado para que la base de datos pueda
    exigir una sola ruta activa por conductor y día.
    """
    route.delivery_days.clear()
    db.flush()
    for weekday in sorted(set(weekdays)):
        route.delivery_days.append(
            RouteDeliveryDay(route_id=route.id, driver_id=driver_id, weekday=weekday)
        )
    db.flush()


def clear_delivery_days(db: Session, route: Route) -> None:
    route.delivery_days.clear()
    db.flush()


def conflicting_delivery_days(
    db: Session, driver_id: int, weekdays: list[int], *, except_route_id: int
) -> list[int]:
    """Días en los que el conductor ya tiene otra ruta asignada."""
    if not weekdays:
        return []
    rows = db.scalars(
        select(RouteDeliveryDay.weekday).where(
            RouteDeliveryDay.driver_id == driver_id,
            RouteDeliveryDay.route_id != except_route_id,
            RouteDeliveryDay.weekday.in_(weekdays),
        )
    )
    return sorted(set(rows))
