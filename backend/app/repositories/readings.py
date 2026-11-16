from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.reading import Reading


def create(db: Session, reading: Reading) -> Reading:
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


def get_latest_for_trucks(db: Session, truck_ids: list[int]) -> dict[int, Reading]:
    if not truck_ids:
        return {}
    stmt = (
        select(Reading)
        .where(Reading.truck_id.in_(truck_ids))
        .distinct(Reading.truck_id)
        .order_by(Reading.truck_id, Reading.reading_timestamp.desc())
    )
    return {reading.truck_id: reading for reading in db.scalars(stmt) if reading.truck_id}


def get_latest_for_truck(db: Session, truck_id: int) -> Reading | None:
    return db.scalar(
        select(Reading)
        .where(Reading.truck_id == truck_id)
        .order_by(Reading.reading_timestamp.desc())
        .limit(1)
    )


def get_latest_received_at(db: Session) -> datetime | None:
    return db.scalar(select(func.max(Reading.received_at)))


def list_paginated(
    db: Session,
    *,
    truck_id: int | None = None,
    device_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Reading], int]:
    stmt = select(Reading)
    count_stmt = select(func.count(Reading.id))
    conditions = []
    if truck_id is not None:
        conditions.append(Reading.truck_id == truck_id)
    if device_id is not None:
        conditions.append(Reading.device_id == device_id)
    if date_from is not None:
        conditions.append(Reading.reading_timestamp >= date_from)
    if date_to is not None:
        conditions.append(Reading.reading_timestamp <= date_to)
    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    total = db.scalar(count_stmt) or 0
    stmt = (
        stmt.order_by(Reading.reading_timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt)), total


def effectiveness_since(
    db: Session,
    since: datetime,
    temperature_min: float,
    temperature_max: float,
    humidity_min: float,
    humidity_max: float,
) -> tuple[int, int]:
    total = (
        db.scalar(
            select(func.count(Reading.id)).where(
                Reading.reading_timestamp >= since, Reading.truck_id.is_not(None)
            )
        )
        or 0
    )
    valid = (
        db.scalar(
            select(func.count(Reading.id)).where(
                Reading.reading_timestamp >= since,
                Reading.truck_id.is_not(None),
                Reading.temperature.between(temperature_min, temperature_max),
                Reading.humidity.between(humidity_min, humidity_max),
            )
        )
        or 0
    )
    return valid, total


def count_since(db: Session, since: datetime) -> int:
    return (
        db.scalar(
            select(func.count(Reading.id)).where(Reading.reading_timestamp >= since)
        )
        or 0
    )
