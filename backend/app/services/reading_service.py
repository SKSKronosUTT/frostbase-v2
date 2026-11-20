from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.reading import Reading
from app.models.setting import Setting
from app.models.truck import Truck
from app.repositories import readings as readings_repo
from app.schemas.common import Page
from app.schemas.iot import ReadingIngest
from app.schemas.reading import ReadingOut
from app.services import alert_service
from app.services.serializers import serialize_reading
from app.utils.pagination import encode_cursor
from app.utils.time import ensure_utc, utcnow


class DeviceNotAssignedError(Exception):
    pass


def ingest_reading(
    db: Session, *, device: Device, payload: ReadingIngest, setting: Setting
) -> tuple[Reading, list, bool]:
    """Inserta una lectura de forma atómica e idempotente.

    Devuelve ``(reading, alerts, duplicate)``. Si ya existe una lectura con el
    mismo ``(device_id, reading_timestamp)``, no se evalúan alertas de nuevo.
    """
    if device.truck_id is None:
        raise DeviceNotAssignedError(
            "El dispositivo no está asociado a un camión. Asígnelo antes de enviar lecturas."
        )

    truck = db.get(Truck, device.truck_id)
    if truck is not None and truck.status == "disponible":
        truck.status = "en_ruta"
        db.add(truck)

    now = utcnow()
    timestamp = ensure_utc(payload.timestamp) or now

    stmt = (
        pg_insert(Reading)
        .values(
            device_id=device.id,
            truck_id=device.truck_id,
            temperature=payload.temperature,
            humidity=payload.humidity,
            latitude=payload.latitude,
            longitude=payload.longitude,
            received_at=now,
            reading_timestamp=timestamp,
        )
        .on_conflict_do_nothing(
            index_elements=["device_id", "reading_timestamp"]
        )
        .returning(Reading)
    )
    reading = db.scalars(stmt).first()

    if reading is None:
        existing = db.scalar(
            select(Reading).where(
                Reading.device_id == device.id,
                Reading.reading_timestamp == timestamp,
            )
        )
        if existing is None:
            raise RuntimeError("No se pudo recuperar la lectura existente")
        return existing, [], True

    device.last_seen = now
    db.add(device)
    db.flush()

    alerts = alert_service.evaluate_reading(
        db, device=device, reading=reading, setting=setting
    )
    return reading, alerts, False


def list_readings(
    db: Session,
    *,
    truck_id: int | None,
    device_id: int | None,
    date_from: datetime | None,
    date_to: datetime | None,
    page: int,
    page_size: int,
    cursor: tuple[datetime, int] | None = None,
) -> Page[ReadingOut]:
    date_from = ensure_utc(date_from)
    date_to = ensure_utc(date_to)
    readings, total = readings_repo.list_paginated(
        db,
        truck_id=truck_id,
        device_id=device_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        cursor=cursor,
    )
    next_cursor = None
    if readings and len(readings) == page_size:
        last = readings[-1]
        next_cursor = encode_cursor(last.reading_timestamp, last.id)
    return Page(
        items=[serialize_reading(reading) for reading in readings],
        total=total,
        page=page,
        page_size=page_size,
        next_cursor=next_cursor,
    )
