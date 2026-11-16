from datetime import datetime, timezone

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
from app.utils.time import ensure_utc, utcnow


class DeviceNotAssignedError(Exception):
    pass


def ingest_reading(
    db: Session, *, device: Device, payload: ReadingIngest, setting: Setting
) -> tuple[Reading, list]:
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
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    reading = Reading(
        device_id=device.id,
        truck_id=device.truck_id,
        temperature=payload.temperature,
        humidity=payload.humidity,
        latitude=payload.latitude,
        longitude=payload.longitude,
        received_at=now,
        reading_timestamp=timestamp,
    )
    db.add(reading)
    device.last_seen = now
    db.add(device)
    db.commit()
    db.refresh(reading)
    db.refresh(device)

    alerts = alert_service.evaluate_reading(
        db, device=device, reading=reading, setting=setting
    )
    return reading, alerts


def list_readings(
    db: Session,
    *,
    truck_id: int | None,
    device_id: int | None,
    date_from: datetime | None,
    date_to: datetime | None,
    page: int,
    page_size: int,
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
    )
    return Page(
        items=[serialize_reading(reading) for reading in readings],
        total=total,
        page=page,
        page_size=page_size,
    )
