from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.truck import Truck
from app.utils.search import escape_like


def _with_relations():
    return (
        selectinload(Truck.route),
        selectinload(Truck.device),
    )


def get(db: Session, truck_id: int, *, include_deleted: bool = False) -> Truck | None:
    stmt = select(Truck).options(*_with_relations()).where(Truck.id == truck_id)
    if not include_deleted:
        stmt = stmt.where(Truck.is_deleted.is_(False))
    return db.scalar(stmt)


def get_by_plate(db: Session, plate: str) -> Truck | None:
    return db.scalar(
        select(Truck).where(
            Truck.plate == plate.strip().upper(),
            Truck.is_deleted.is_(False),
        )
    )


def list_paginated(
    db: Session,
    *,
    search: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Truck], int]:
    stmt = select(Truck).options(*_with_relations()).where(Truck.is_deleted.is_(False))
    count_stmt = select(func.count(Truck.id)).where(Truck.is_deleted.is_(False))
    if search:
        pattern = f"%{escape_like(search.strip())}%"
        condition = or_(
            Truck.plate.ilike(pattern, escape="\\"),
            Truck.brand.ilike(pattern, escape="\\"),
            Truck.model.ilike(pattern, escape="\\"),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    if status:
        stmt = stmt.where(Truck.status == status)
        count_stmt = count_stmt.where(Truck.status == status)
    total = db.scalar(count_stmt) or 0
    stmt = stmt.order_by(Truck.plate).offset((page - 1) * page_size).limit(page_size)
    return list(db.scalars(stmt).unique()), total


def list_active(db: Session) -> list[Truck]:
    return list(
        db.scalars(
            select(Truck)
            .options(*_with_relations())
            .where(Truck.is_deleted.is_(False))
            .order_by(Truck.plate)
        ).unique()
    )


def count_by_status(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(Truck.status, func.count(Truck.id))
        .where(Truck.is_deleted.is_(False))
        .group_by(Truck.status)
    ).all()
    return {status: count for status, count in rows}


def create(db: Session, truck: Truck) -> Truck:
    db.add(truck)
    db.flush()
    return truck


def save(db: Session, truck: Truck) -> Truck:
    db.add(truck)
    db.flush()
    return truck


def trucks_using_route(
    db: Session, route_id: int, except_id: int | None = None
) -> list[Truck]:
    stmt = select(Truck).where(Truck.route_id == route_id, Truck.is_deleted.is_(False))
    if except_id is not None:
        stmt = stmt.where(Truck.id != except_id)
    return list(db.scalars(stmt))
