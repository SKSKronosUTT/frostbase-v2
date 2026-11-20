from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.route import DeliveryPoint, Route
from app.models.truck import Truck
from app.utils.search import escape_like


def _with_relations():
    return (
        selectinload(Route.points),
        selectinload(Route.truck),
    )


def get(db: Session, route_id: int) -> Route | None:
    return db.scalar(select(Route).options(*_with_relations()).where(Route.id == route_id))


def list_paginated(
    db: Session,
    *,
    search: str | None = None,
    status: str | None = None,
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
    total = db.scalar(count_stmt) or 0
    stmt = (
        stmt.order_by(Route.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).unique()), total


def list_all(db: Session) -> list[Route]:
    return list(
        db.scalars(select(Route).options(*_with_relations()).order_by(Route.name)).unique()
    )


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


def unassign_truck(db: Session, route_id: int, except_truck_id: int | None = None) -> None:
    stmt = select(Truck).where(Truck.route_id == route_id)
    if except_truck_id is not None:
        stmt = stmt.where(Truck.id != except_truck_id)
    for truck in db.scalars(stmt):
        truck.route_id = None
    db.flush()
