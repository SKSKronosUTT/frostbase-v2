from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.device import Device
from app.models.truck import Truck


def get(db: Session, device_pk: int) -> Device | None:
    return db.scalar(
        select(Device)
        .options(selectinload(Device.truck))
        .where(Device.id == device_pk)
    )


def get_by_identifier(db: Session, device_id: str) -> Device | None:
    return db.scalar(
        select(Device)
        .options(selectinload(Device.truck))
        .where(Device.device_id == device_id)
    )


def get_by_truck(db: Session, truck_id: int) -> Device | None:
    return db.scalar(
        select(Device)
        .options(selectinload(Device.truck))
        .where(Device.truck_id == truck_id)
    )


def list_all(
    db: Session,
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    unassigned_only: bool = False,
) -> tuple[list[Device], int]:
    stmt = select(Device).options(selectinload(Device.truck))
    count_stmt = select(func.count(Device.id))
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(Device.device_id.ilike(pattern))
        count_stmt = count_stmt.where(Device.device_id.ilike(pattern))
    if unassigned_only:
        stmt = stmt.where(Device.truck_id.is_(None))
        count_stmt = count_stmt.where(Device.truck_id.is_(None))
    total = db.scalar(count_stmt) or 0
    stmt = (
        stmt.order_by(Device.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).unique()), total


def list_all_without_pagination(db: Session) -> list[Device]:
    return list(db.scalars(select(Device).options(selectinload(Device.truck))).unique())


def create(
    db: Session,
    *,
    device_id: str,
    truck_id: int | None,
    key_hash: str,
    key_scheme: str = "argon2",
) -> Device:
    device = Device(
        device_id=device_id.strip(),
        truck_id=truck_id,
        key_hash=key_hash,
        key_scheme=key_scheme,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def commit(db: Session, device: Device) -> Device:
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def delete(db: Session, device: Device) -> None:
    db.delete(device)
    db.commit()


def truck_exists(db: Session, truck_id: int) -> bool:
    return (
        db.scalar(
            select(Truck.id).where(Truck.id == truck_id, Truck.is_deleted.is_(False))
        )
        is not None
    )
