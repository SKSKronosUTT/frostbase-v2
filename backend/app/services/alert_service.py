import contextlib
import logging
from datetime import datetime, timedelta

from sqlalchemy import literal, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.device import Device
from app.models.reading import Reading
from app.models.setting import Setting
from app.repositories import alerts as alerts_repo
from app.utils.time import ensure_utc, utcnow

logger = logging.getLogger("frostbase.alerts")

TEMP_TYPE = "temperatura"
HUMIDITY_TYPE = "humedad"
DISCONNECT_TYPE = "desconexion"


def _resolve(db: Session, alert: Alert, when: datetime) -> None:
    alert.status = "resuelta"
    alert.resolved_at = when
    db.add(alert)


def _create_active_alert(db: Session, alert: Alert) -> Alert | None:
    """Crea una alerta activa; si otra transacción ganó la carrera, la reutiliza.

    El índice único parcial ``uq_alerts_active_device_type`` impide duplicados.
    Se usa un savepoint para que un conflicto no invalide la transacción de la
    lectura y se reintenta una vez.
    """
    for attempt in range(2):
        try:
            with db.begin_nested():
                db.add(alert)
                db.flush()
            return alert
        except IntegrityError:
            with contextlib.suppress(Exception):
                db.expunge(alert)
            existing = alerts_repo.find_active(
                db, alert.device_id, alert.alert_type
            )
            if existing is not None:
                return existing
            if attempt == 1:
                logger.warning(
                    "Conflicto de alerta activa sin fila visible "
                    "device_id=%s type=%s",
                    alert.device_id,
                    alert.alert_type,
                )
                raise
    return None


def _evaluate_metric(
    db: Session,
    *,
    device: Device,
    reading: Reading,
    alert_type: str,
    value: float,
    minimum: float,
    maximum: float,
    unit: str,
    label: str,
) -> Alert | None:
    active = alerts_repo.find_active(db, device.id, alert_type)
    is_outside = value < minimum or value > maximum

    if is_outside:
        message = (
            f"{label} fuera de rango: {value:.1f}{unit}. "
            f"Rango permitido: {minimum:.1f} a {maximum:.1f}{unit}."
        )
        if active is None:
            alert = Alert(
                truck_id=device.truck_id,
                device_id=device.id,
                alert_type=alert_type,
                status="activa",
                started_at=min(ensure_utc(reading.reading_timestamp) or utcnow(), utcnow()),
            )
            active = _create_active_alert(db, alert)
            if active is None:
                return None
        active.value = value
        active.min_value = minimum
        active.max_value = maximum
        active.message = message
        active.truck_id = device.truck_id
        db.add(active)
        return active

    if active is not None:
        resolved_at = min(ensure_utc(reading.reading_timestamp) or utcnow(), utcnow())
        _resolve(db, active, resolved_at)
    return None


def evaluate_reading(
    db: Session, *, device: Device, reading: Reading, setting: Setting
) -> list[Alert]:
    now = utcnow()

    disconnect = alerts_repo.find_active(db, device.id, DISCONNECT_TYPE)
    if disconnect is not None:
        _resolve(db, disconnect, now)

    alerts: list[Alert] = []
    temperature_alert = _evaluate_metric(
        db,
        device=device,
        reading=reading,
        alert_type=TEMP_TYPE,
        value=reading.temperature,
        minimum=setting.temperature_min,
        maximum=setting.temperature_max,
        unit=" °C",
        label="Temperatura",
    )
    if temperature_alert:
        alerts.append(temperature_alert)

    humidity_alert = _evaluate_metric(
        db,
        device=device,
        reading=reading,
        alert_type=HUMIDITY_TYPE,
        value=reading.humidity,
        minimum=setting.humidity_min,
        maximum=setting.humidity_max,
        unit=" %",
        label="Humedad",
    )
    if humidity_alert:
        alerts.append(humidity_alert)

    db.flush()
    return alerts


def check_disconnected_devices(db: Session, setting: Setting) -> int:
    """Crea y resuelve alertas de desconexión en dos sentencias set-based."""
    now = utcnow()
    threshold = now - timedelta(seconds=setting.offline_timeout_seconds)

    source = select(
        Device.truck_id.label("truck_id"),
        Device.id.label("device_id"),
        literal(DISCONNECT_TYPE).label("alert_type"),
        literal(
            "El dispositivo dejó de enviar lecturas dentro del tiempo esperado."
        ).label("message"),
        Device.last_seen.label("started_at"),
        literal("activa").label("status"),
    ).where(
        Device.last_seen.is_not(None),
        Device.last_seen < threshold,
    )
    insert_stmt = (
        pg_insert(Alert)
        .from_select(
            ["truck_id", "device_id", "alert_type", "message", "started_at", "status"],
            source,
        )
        .on_conflict_do_nothing(
            index_elements=["device_id", "alert_type"],
            index_where=text("status = 'activa'"),
        )
    )
    created = max(0, db.execute(insert_stmt).rowcount or 0)

    resolve_stmt = (
        update(Alert)
        .where(
            Alert.alert_type == DISCONNECT_TYPE,
            Alert.status == "activa",
            Alert.device_id.in_(
                select(Device.id).where(Device.last_seen >= threshold)
            ),
        )
        .values(status="resuelta", resolved_at=now)
    )
    resolved = max(0, db.execute(resolve_stmt).rowcount or 0)

    db.flush()
    if created:
        logger.info("Se generaron %s alertas de desconexión", created)
    if resolved:
        logger.info("Se resolvieron %s alertas de desconexión", resolved)
    return created


def resolve_truck_alerts(db: Session, truck_id: int, reason: str) -> None:
    now = utcnow()
    rows = db.query(Alert).filter(Alert.truck_id == truck_id, Alert.status == "activa").all()
    for alert in rows:
        alert.status = "resuelta"
        alert.resolved_at = now
        alert.message = f"{alert.message or ''} ({reason})".strip()
        db.add(alert)
    db.flush()
