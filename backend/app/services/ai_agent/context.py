"""Contexto mínimo que se envía al agente en cada mensaje (A1, estrategia P).

Solo datos operativos: placas, estado, cifras y antigüedad. **Sin nombres,
correos, teléfonos ni texto libre** de usuarios (mitiga inyección indirecta).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.alert import Alert
from app.models.door_event import DoorEvent
from app.models.reading import Reading
from app.models.route import Route, RouteDeliveryDay
from app.models.trip import Trip, TripOrder
from app.models.truck import Truck
from app.services import settings_service
from app.services.route_links import today_weekday
from app.utils.time import ensure_utc, utcnow

STATUS_ORDER = {
    "out_of_range": 0,
    "door_open": 1,
    "no_signal": 2,
    "ok": 3,
    "no_data": 4,
}
STATUS_LABEL = {
    "out_of_range": "fuera de rango",
    "door_open": "puerta abierta",
    "no_signal": "sin señal",
    "ok": "ok",
    "no_data": "sin datos",
}


def _latest_readings(db: Session) -> dict[int, Reading]:
    rows = db.scalars(
        select(Reading)
        .distinct(Reading.truck_id)
        .order_by(Reading.truck_id, Reading.received_at.desc())
    )
    return {row.truck_id: row for row in rows if row.truck_id is not None}


def _latest_doors(db: Session) -> dict[int, DoorEvent]:
    rows = db.scalars(
        select(DoorEvent)
        .where(DoorEvent.truck_id.is_not(None))
        .distinct(DoorEvent.truck_id)
        .order_by(DoorEvent.truck_id, DoorEvent.event_time.desc())
    )
    return {row.truck_id: row for row in rows if row.truck_id is not None}


def collect_snapshot(db: Session) -> dict:
    setting = settings_service.get_settings(db)
    now = utcnow()
    trucks = list(
        db.scalars(
            select(Truck).where(Truck.is_deleted.is_(False)).order_by(Truck.plate)
        )
    )
    readings = _latest_readings(db)
    doors = _latest_doors(db)

    alerts = list(
        db.scalars(
            select(Alert)
            .where(Alert.status == "activa")
            .order_by(Alert.started_at.desc())
        )
    )
    alerts_by_truck: dict[int, list[str]] = {}
    alert_counts: dict[str, int] = {}
    for alert in alerts:
        alert_counts[alert.alert_type] = alert_counts.get(alert.alert_type, 0) + 1
        if alert.truck_id is not None:
            alerts_by_truck.setdefault(alert.truck_id, []).append(alert.alert_type)

    active_trip_ids = select(Trip.id).where(Trip.state == "in_progress")
    active_trips = int(
        db.scalar(select(func.count(Trip.id)).where(Trip.state == "in_progress")) or 0
    )
    pending_orders = int(
        db.scalar(
            select(func.count(TripOrder.id)).where(
                TripOrder.trip_id.in_(active_trip_ids),
                TripOrder.state.in_(("pending", "in_delivery")),
            )
        )
        or 0
    )
    today = today_weekday()
    routes_today = int(
        db.scalar(
            select(func.count(func.distinct(RouteDeliveryDay.route_id))).where(
                RouteDeliveryDay.weekday == today,
                RouteDeliveryDay.route_id.in_(
                    select(Route.id).where(Route.status == "activa")
                ),
            )
        )
        or 0
    )

    entries: list[dict] = []
    cutoff_seconds = setting.offline_timeout_seconds
    for truck in trucks:
        reading = readings.get(truck.id)
        door = doors.get(truck.id)
        status = "no_data"
        if reading is not None:
            received = ensure_utc(reading.received_at) or now
            age_seconds = (now - received).total_seconds()
            if (
                reading.temperature < setting.temperature_min
                or reading.temperature > setting.temperature_max
                or reading.humidity < setting.humidity_min
                or reading.humidity > setting.humidity_max
            ):
                status = "out_of_range"
            elif door is not None and door.is_open:
                status = "door_open"
            elif age_seconds > cutoff_seconds:
                status = "no_signal"
            else:
                status = "ok"
        entries.append(
            {
                "plate": truck.plate,
                "status": status,
                "temperature": reading.temperature if reading else None,
                "humidity": reading.humidity if reading else None,
                "age_minutes": (
                    round(
                        (now - (ensure_utc(reading.received_at) or now)).total_seconds()
                        / 60
                    )
                    if reading
                    else None
                ),
                "alerts": sorted(set(alerts_by_truck.get(truck.id, []))),
            }
        )

    critical = sorted(
        (entry for entry in entries if entry["status"] != "ok" or entry["alerts"]),
        key=lambda entry: (STATUS_ORDER.get(entry["status"], 9), entry["plate"]),
    )

    return {
        "generated_at": now,
        "timezone": settings.app_timezone,
        "trucks_total": len(trucks),
        "truck_statuses": {
            status: sum(1 for truck in trucks if truck.status == status)
            for status in sorted({truck.status for truck in trucks})
        },
        "alerts_active": len(alerts),
        "alert_counts": alert_counts,
        "active_trips": active_trips,
        "pending_orders": pending_orders,
        "routes_today": routes_today,
        "thresholds": {
            "temperature_min": setting.temperature_min,
            "temperature_max": setting.temperature_max,
            "humidity_min": setting.humidity_min,
            "humidity_max": setting.humidity_max,
        },
        "critical": critical,
    }


def _format_alert_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "sin alertas activas"
    labels = {
        "temperatura": "temperatura",
        "humedad": "humedad",
        "puerta": "puerta",
        "desconexion": "desconexión",
    }
    parts = [
        f"{labels.get(key, key)}: {value}" for key, value in sorted(counts.items())
    ]
    return ", ".join(parts)


def build_context(db: Session, *, max_trucks: int = 6) -> str:
    snapshot = collect_snapshot(db)
    now_local: datetime = snapshot["generated_at"].astimezone(settings.tz)
    lines = [
        f"[Contexto FrostBase · {now_local:%Y-%m-%d %H:%M} {snapshot['timezone']}]",
        (
            f"Flota: {snapshot['trucks_total']} camiones · "
            f"{snapshot['alerts_active']} alertas activas "
            f"({_format_alert_counts(snapshot['alert_counts'])}) · "
            f"{snapshot['active_trips']} viajes en curso · "
            f"{snapshot['pending_orders']} entregas pendientes · "
            f"{snapshot['routes_today']} rutas hoy."
        ),
    ]
    thresholds = snapshot["thresholds"]
    t_min = thresholds["temperature_min"]
    t_max = thresholds["temperature_max"]
    h_min = thresholds["humidity_min"]
    h_max = thresholds["humidity_max"]
    lines.append(
        f"Umbrales: {t_min:.1f} a {t_max:.1f} °C, {h_min:.1f} a {h_max:.1f} %."
    )
    critical = snapshot["critical"][:max_trucks]
    if critical:
        lines.append("Camiones críticos:")
        for entry in critical:
            details = [STATUS_LABEL.get(entry["status"], entry["status"])]
            if entry["temperature"] is not None:
                details.append(
                    f"{entry['temperature']:.1f} °C / {entry['humidity']:.1f} %"
                )
            if entry["age_minutes"] is not None:
                details.append(f"lectura hace {entry['age_minutes']} min")
            if entry["alerts"]:
                details.append("alertas: " + ", ".join(entry["alerts"]))
            lines.append(f"- {entry['plate']}: " + "; ".join(details))
    else:
        lines.append("Sin camiones en estado crítico.")
    lines.append("Usa solo estos datos para responder; si falta información, dilo.")
    return "\n".join(lines)
