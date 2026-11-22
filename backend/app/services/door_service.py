"""Eventos de puerta y alerta de apertura no autorizada (G7).

Reglas (decisiones G0 + H7):

- El ESP32 envía un evento JSON inmediato en cada cambio de estado del
  Reed Switch; la ingesta es idempotente por ``(device_id, event_time)``.
- Un evento ``open`` queda **pendiente** (``evaluated_at`` nulo) y no genera
  alerta por sí solo: el watcher lo evalúa al vencer el periodo de gracia
  configurable (``settings.door_open_grace_seconds``, 30 s por defecto).
- La alerta ``puerta`` solo se crea si, al vencer la gracia, la puerta sigue
  abierta, hay un viaje ``in_progress`` del camión y **ninguna** orden está en
  entrega (apertura no autorizada, RF14).
- Un evento ``close`` resuelve la alerta activa ``puerta`` del dispositivo y
  cierra los eventos abiertos pendientes.
"""

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.device import Device
from app.models.door_event import DoorEvent
from app.models.setting import Setting
from app.models.trip import Trip, TripOrder
from app.models.truck import Truck
from app.repositories import alerts as alerts_repo
from app.schemas.iot import DoorEventIngest
from app.services.alert_service import _create_active_alert
from app.utils.time import ensure_utc, utcnow

logger = logging.getLogger("frostbase.doors")

DOOR_ALERT_TYPE = "puerta"


class DeviceNotAssignedError(Exception):
    pass


def ingest_door_event(
    db: Session,
    *,
    device: Device,
    payload: DoorEventIngest,
) -> tuple[DoorEvent, bool]:
    """Registra un evento de puerta de forma atómica e idempotente.

    Devuelve ``(event, duplicate)``. Los eventos ``open`` quedan pendientes de
    evaluación; los ``close`` resuelven la alerta activa y cierran pendientes.
    """
    if device.truck_id is None:
        raise DeviceNotAssignedError(
            "El dispositivo no está asociado a un camión. "
            "Asígnelo antes de enviar eventos de puerta."
        )

    now = utcnow()
    event_time = ensure_utc(payload.timestamp) or now

    stmt = (
        pg_insert(DoorEvent)
        .values(
            device_id=device.id,
            truck_id=device.truck_id,
            is_open=payload.is_open,
            event_time=event_time,
            received_at=now,
        )
        .on_conflict_do_nothing(index_elements=["device_id", "event_time"])
        .returning(DoorEvent)
    )
    event = db.scalars(stmt).first()

    if event is None:
        existing = db.scalar(
            select(DoorEvent).where(
                DoorEvent.device_id == device.id,
                DoorEvent.event_time == event_time,
            )
        )
        if existing is None:
            raise RuntimeError("No se pudo recuperar el evento de puerta existente")
        return existing, True

    device.last_seen = now
    db.add(device)

    if not payload.is_open:
        _handle_close(db, device)
    db.flush()
    logger.info(
        "door_event device_id=%s is_open=%s event_time=%s",
        device.device_id,
        payload.is_open,
        event_time.isoformat(),
    )
    return event, False


def _handle_close(db: Session, device: Device) -> None:
    """La puerta se cerró: resuelve la alerta activa y cierra pendientes."""
    now = utcnow()
    active = alerts_repo.find_active(db, device.id, DOOR_ALERT_TYPE)
    if active is not None:
        active.status = "resuelta"
        active.resolved_at = now
        db.add(active)
        logger.info("door_alert_resolved device_id=%s", device.device_id)

    pending = db.scalars(
        select(DoorEvent).where(
            DoorEvent.device_id == device.id,
            DoorEvent.evaluated_at.is_(None),
            DoorEvent.is_open.is_(True),
        )
    )
    for event in pending:
        event.evaluated_at = now
        db.add(event)


def evaluate_pending_door_events(db: Session, setting: Setting) -> int:
    """Evalúa los eventos ``open`` cuyo periodo de gracia ya venció.

    Crea la alerta ``puerta`` (apertura no autorizada) solo si el camión tiene
    un viaje en curso sin ninguna orden en entrega. Devuelve el número de
    alertas nuevas.
    """
    now = utcnow()
    grace = setting.door_open_grace_seconds
    deadline = now.timestamp() - grace

    pending = db.scalars(
        select(DoorEvent)
        .where(
            DoorEvent.evaluated_at.is_(None),
            DoorEvent.is_open.is_(True),
            DoorEvent.truck_id.is_not(None),
        )
        .order_by(DoorEvent.event_time)
    )
    created = 0
    for event in pending:
        if ensure_utc(event.event_time).timestamp() > deadline:
            continue

        trip = db.scalar(
            select(Trip).where(
                Trip.truck_id == event.truck_id,
                Trip.state == "in_progress",
            )
        )
        if trip is not None:
            in_delivery = db.scalar(
                select(TripOrder.id)
                .where(
                    TripOrder.trip_id == trip.id,
                    TripOrder.state == "in_delivery",
                )
                .limit(1)
            )
            if in_delivery is None:
                alert = _create_door_alert(db, event=event, trip=trip, grace=grace)
                if alert is not None:
                    event.alert_id = alert.id
                    created += 1
                    logger.warning(
                        "door_unauthorized truck_id=%s trip_id=%s grace=%ss",
                        event.truck_id,
                        trip.id,
                        grace,
                    )

        event.evaluated_at = now
        db.add(event)

    db.flush()
    return created


def _create_door_alert(
    db: Session, *, event: DoorEvent, trip: Trip, grace: int
) -> Alert | None:
    """Crea la alerta activa ``puerta``; si ya existe una, no duplica."""
    message = (
        "Puerta abierta sin autorización durante el viaje "
        f"(más de {grace} s sin entrega en curso)."
    )
    return _create_active_alert(
        db,
        Alert(
            truck_id=event.truck_id,
            device_id=event.device_id,
            trip_id=trip.id,
            alert_type=DOOR_ALERT_TYPE,
            message=message,
            started_at=ensure_utc(event.event_time) or utcnow(),
            status="activa",
        ),
    )


def ack_alert(db: Session, driver, alert_id: int) -> Alert | None:
    """El conductor reconoce una alerta **de su camión** (idempotente)."""
    from app.repositories import driver as driver_repo

    assignment = driver_repo.active_assignment(db, driver.id)
    if assignment is None:
        return None

    alert = db.scalar(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.truck_id == assignment.truck_id,
        )
    )
    if alert is None:
        return None

    if alert.acknowledged_at is None:
        alert.acknowledged_at = utcnow()
        alert.acknowledged_by = driver.id
        db.add(alert)
        db.flush()
        logger.info("alert_acknowledged alert_id=%s driver_id=%s", alert.id, driver.id)
    return alert


def latest_door_state(db: Session, truck: Truck | None) -> DoorEvent | None:
    """Último evento de puerta del camión, para el portal del conductor."""
    if truck is None:
        return None
    return db.scalar(
        select(DoorEvent)
        .where(DoorEvent.truck_id == truck.id)
        .order_by(DoorEvent.event_time.desc())
        .limit(1)
    )
