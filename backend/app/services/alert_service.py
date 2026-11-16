import logging
from datetime import datetime, timedelta

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
                value=value,
                min_value=minimum,
                max_value=maximum,
                message=message,
                started_at=ensure_utc(reading.reading_timestamp) or utcnow(),
                status="activa",
            )
            alerts_repo.create(db, alert)
        else:
            active.value = value
            active.message = message
            active.truck_id = device.truck_id
            db.add(active)
            alert = active
        return alert

    if active is not None:
        _resolve(db, active, ensure_utc(reading.reading_timestamp) or utcnow())
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

    db.commit()
    for alert in alerts:
        db.refresh(alert)
    return alerts


def check_disconnected_devices(db: Session, setting: Setting) -> int:
    now = utcnow()
    threshold = now - timedelta(seconds=setting.offline_timeout_seconds)
    created = 0

    for alert in alerts_repo.list_active(db):
        if alert.alert_type != DISCONNECT_TYPE or alert.device is None:
            continue
        last_seen = ensure_utc(alert.device.last_seen)
        if last_seen is not None and last_seen >= threshold:
            _resolve(db, alert, now)

    devices = alerts_repo.devices_without_recent_contact(db, threshold)
    for device in devices:
        active = alerts_repo.find_active(db, device.id, DISCONNECT_TYPE)
        if active is not None:
            continue
        alert = Alert(
            truck_id=device.truck_id,
            device_id=device.id,
            alert_type=DISCONNECT_TYPE,
            message="El dispositivo dejó de enviar lecturas dentro del tiempo esperado.",
            started_at=threshold,
            status="activa",
        )
        alerts_repo.create(db, alert)
        created += 1

    db.commit()
    if created:
        logger.info("Se generaron %s alertas de desconexión", created)
    return created


def resolve_truck_alerts(db: Session, truck_id: int, reason: str) -> None:
    now = utcnow()
    rows = db.query(Alert).filter(Alert.truck_id == truck_id, Alert.status == "activa").all()
    for alert in rows:
        alert.status = "resuelta"
        alert.resolved_at = now
        alert.message = f"{alert.message or ''} ({reason})".strip()
        db.add(alert)
    db.commit()
