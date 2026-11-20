from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.alert import Alert
from app.models.device import Device


def get(db: Session, alert_id: int) -> Alert | None:
    return db.scalar(
        select(Alert)
        .options(selectinload(Alert.truck), selectinload(Alert.device))
        .where(Alert.id == alert_id)
    )


def list_paginated(
    db: Session,
    *,
    truck_id: int | None = None,
    alert_type: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
    cursor: tuple[datetime, int] | None = None,
) -> tuple[list[Alert], int]:
    stmt = select(Alert).options(selectinload(Alert.truck), selectinload(Alert.device))
    count_stmt = select(func.count(Alert.id))
    conditions = []
    if truck_id is not None:
        conditions.append(Alert.truck_id == truck_id)
    if alert_type is not None:
        conditions.append(Alert.alert_type == alert_type)
    if status is not None:
        conditions.append(Alert.status == status)
    if date_from is not None:
        conditions.append(Alert.started_at >= date_from)
    if date_to is not None:
        conditions.append(Alert.started_at <= date_to)
    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    if cursor is not None:
        cursor_timestamp, cursor_id = cursor
        stmt = stmt.where(
            or_(
                Alert.started_at < cursor_timestamp,
                and_(
                    Alert.started_at == cursor_timestamp,
                    Alert.id < cursor_id,
                ),
            )
        )
    total = db.scalar(count_stmt) or 0
    stmt = (
        stmt.order_by(Alert.started_at.desc(), Alert.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).unique()), total


def list_active(db: Session) -> list[Alert]:
    return list(
        db.scalars(
            select(Alert)
            .options(selectinload(Alert.truck), selectinload(Alert.device))
            .where(Alert.status == "activa")
            .order_by(Alert.started_at.desc())
        ).unique()
    )


def count_active(db: Session) -> int:
    return db.scalar(select(func.count(Alert.id)).where(Alert.status == "activa")) or 0


def count_active_by_truck(db: Session, truck_id: int) -> int:
    return (
        db.scalar(
            select(func.count(Alert.id)).where(
                Alert.status == "activa", Alert.truck_id == truck_id
            )
        )
        or 0
    )


def active_counts_by_truck(db: Session) -> dict[int, int]:
    rows = db.execute(
        select(Alert.truck_id, func.count(Alert.id))
        .where(Alert.status == "activa", Alert.truck_id.is_not(None))
        .group_by(Alert.truck_id)
    ).all()
    return {truck_id: count for truck_id, count in rows if truck_id is not None}


def find_active(db: Session, device_id: int, alert_type: str) -> Alert | None:
    return db.scalar(
        select(Alert).where(
            Alert.device_id == device_id,
            Alert.alert_type == alert_type,
            Alert.status == "activa",
        )
    )


def create(db: Session, alert: Alert) -> Alert:
    db.add(alert)
    db.flush()
    return alert


def devices_without_recent_contact(db: Session, threshold: datetime) -> list[Device]:
    return list(
        db.scalars(
            select(Device)
            .options(selectinload(Device.truck))
            .where(Device.last_seen.is_not(None), Device.last_seen < threshold)
        ).unique()
    )
