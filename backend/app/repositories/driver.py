from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.driver import Driver, DriverTruckAssignment
from app.models.login_identity import LoginIdentity
from app.models.truck import Truck
from app.utils.search import escape_like


def get_by_email(db: Session, email: str) -> Driver | None:
    return db.scalar(
        select(Driver).where(func.lower(Driver.email) == email.strip().lower())
    )


def get_by_id(db: Session, driver_id: int) -> Driver | None:
    return db.get(Driver, driver_id)


def get_identity_by_email(db: Session, email: str) -> LoginIdentity | None:
    return db.scalar(
        select(LoginIdentity).where(LoginIdentity.email == email.strip().lower())
    )


def list_paginated(
    db: Session,
    *,
    search: str | None = None,
    active: bool | None = True,
    has_truck: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Driver], int]:
    stmt = select(Driver)
    count_stmt = select(func.count(Driver.id))
    if active is not None:
        stmt = stmt.where(Driver.is_active.is_(active))
        count_stmt = count_stmt.where(Driver.is_active.is_(active))
    if search:
        pattern = f"%{escape_like(search.strip())}%"
        condition = or_(
            func.lower(Driver.first_name).like(pattern, escape="\\"),
            func.lower(Driver.last_name).like(pattern, escape="\\"),
            func.lower(Driver.email).like(pattern, escape="\\"),
            Driver.phone.like(pattern, escape="\\"),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    if has_truck is True:
        condition = Driver.id.in_(
            select(DriverTruckAssignment.driver_id).where(
                DriverTruckAssignment.unassigned_at.is_(None)
            )
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    elif has_truck is False:
        condition = ~Driver.id.in_(
            select(DriverTruckAssignment.driver_id).where(
                DriverTruckAssignment.unassigned_at.is_(None)
            )
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    stmt = (
        stmt.order_by(func.lower(Driver.last_name), func.lower(Driver.first_name))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt)), total


def active_assignment(db: Session, driver_id: int) -> DriverTruckAssignment | None:
    return db.scalar(
        select(DriverTruckAssignment).where(
            DriverTruckAssignment.driver_id == driver_id,
            DriverTruckAssignment.unassigned_at.is_(None),
        )
    )


def active_assignment_for_truck(
    db: Session, truck_id: int
) -> DriverTruckAssignment | None:
    return db.scalar(
        select(DriverTruckAssignment).where(
            DriverTruckAssignment.truck_id == truck_id,
            DriverTruckAssignment.unassigned_at.is_(None),
        )
    )


def truck_by_id(db: Session, truck_id: int) -> Truck | None:
    return db.get(Truck, truck_id)


def options_with_truck(db: Session) -> list[tuple[int, str]]:
    """Conductores activos con camión asignado (para selectores de rutas, G4)."""
    rows = db.execute(
        select(Driver.id, Driver.first_name, Driver.last_name)
        .where(Driver.is_active.is_(True))
        .where(
            Driver.id.in_(
                select(DriverTruckAssignment.driver_id).where(
                    DriverTruckAssignment.unassigned_at.is_(None)
                )
            )
        )
        .order_by(func.lower(Driver.last_name))
    ).all()
    return [(row[0], f"{row[1]} {row[2]}") for row in rows]
