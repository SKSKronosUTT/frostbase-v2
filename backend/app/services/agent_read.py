"""Consultas de solo lectura para el agente (A2).

Reglas: datos compactos, sin PII (alias ``Conductor {id}``), sin texto libre
salvo el nombre de ruta saneado/truncado, fechas ISO con offset y orden por
severidad/antigüedad.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.alert import Alert
from app.models.door_event import DoorEvent
from app.models.driver import Driver
from app.models.reading import Reading
from app.models.route import Route, RouteDeliveryDay
from app.models.trip import Trip, TripOrder
from app.models.truck import Truck, TruckThresholdOverride
from app.schemas.agent_read import (
    AgentAlertOut,
    AgentAlertsOut,
    AgentAlertsTodayOut,
    AgentFleetSummaryOut,
    AgentRouteOut,
    AgentRoutesOut,
    AgentThresholdOverrideOut,
    AgentThresholdsOut,
    AgentTodayAlertOut,
    AgentTripOut,
    AgentTripsOut,
    AgentTruckStatusOut,
)
from app.services import settings_service
from app.services.route_links import today_weekday
from app.utils.time import ensure_utc, utcnow

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _iso(value: datetime | None) -> str:
    moment = ensure_utc(value) or utcnow()
    return moment.astimezone(settings.tz).isoformat()


def _age_minutes(value: datetime | None) -> int:
    moment = ensure_utc(value)
    if moment is None:
        return 0
    return max(0, int((utcnow() - moment).total_seconds() // 60))


def _alias(driver_id: int | None) -> str:
    return f"Conductor {driver_id}" if driver_id is not None else "Sin conductor"


def _sanitize(text: str | None, *, limit: int = 120) -> str:
    cleaned = _CONTROL_CHARS.sub(" ", text or "").strip()
    return cleaned[:limit]


def _today_bounds() -> tuple[datetime, datetime, datetime]:
    """Medianoche local (America/Tijuana) → límites UTC y marca ISO."""
    now_local = datetime.now(settings.tz)
    start_local = datetime.combine(now_local.date(), time.min, tzinfo=settings.tz)
    end_local = datetime.combine(
        now_local.date() + timedelta(days=1), time.min, tzinfo=settings.tz
    )
    return start_local.astimezone(UTC), end_local.astimezone(UTC), start_local


def _counts_by_type(
    db: Session,
    column,
    start_utc: datetime,
    end_utc: datetime,
) -> tuple[int, dict[str, int]]:
    rows = db.execute(
        select(Alert.alert_type, func.count(Alert.id))
        .where(column.is_not(None), column >= start_utc, column < end_utc)
        .group_by(Alert.alert_type)
    ).all()
    by_type = {alert_type: int(count) for alert_type, count in rows}
    return sum(by_type.values()), by_type


def _active_by_type(db: Session) -> tuple[int, dict[str, int]]:
    rows = db.execute(
        select(Alert.alert_type, func.count(Alert.id))
        .where(Alert.status == "activa")
        .group_by(Alert.alert_type)
    ).all()
    by_type = {alert_type: int(count) for alert_type, count in rows}
    return sum(by_type.values()), by_type


def _latest_reading(db: Session, truck_id: int) -> Reading | None:
    return db.scalar(
        select(Reading)
        .where(Reading.truck_id == truck_id)
        .order_by(Reading.received_at.desc())
        .limit(1)
    )


def _latest_door(db: Session, truck_id: int) -> DoorEvent | None:
    return db.scalar(
        select(DoorEvent)
        .where(DoorEvent.truck_id == truck_id)
        .order_by(DoorEvent.event_time.desc())
        .limit(1)
    )


def _thresholds(db: Session, truck_id: int) -> tuple[float, float, float, float]:
    setting = settings_service.get_settings(db)
    override = db.scalar(
        select(TruckThresholdOverride).where(
            TruckThresholdOverride.truck_id == truck_id
        )
    )
    temp_ideal = (
        override.temperature_ideal
        if override and override.temperature_ideal is not None
        else setting.temperature_ideal
    )
    temp_tolerance = (
        override.temperature_tolerance
        if override and override.temperature_tolerance is not None
        else setting.temperature_tolerance
    )
    hum_ideal = (
        override.humidity_ideal
        if override and override.humidity_ideal is not None
        else setting.humidity_ideal
    )
    hum_tolerance = (
        override.humidity_tolerance
        if override and override.humidity_tolerance is not None
        else setting.humidity_tolerance
    )
    return (
        round(temp_ideal - temp_tolerance, 2),
        round(temp_ideal + temp_tolerance, 2),
        round(hum_ideal - hum_tolerance, 2),
        round(hum_ideal + hum_tolerance, 2),
    )


def _container_status(
    reading: Reading | None,
    door: DoorEvent | None,
    *,
    temperature_min: float,
    temperature_max: float,
    humidity_min: float,
    humidity_max: float,
    offline_seconds: int,
) -> str:
    if reading is None:
        return "no_data"
    if (
        reading.temperature < temperature_min
        or reading.temperature > temperature_max
        or reading.humidity < humidity_min
        or reading.humidity > humidity_max
    ):
        return "out_of_range"
    if door is not None and door.is_open:
        return "door_open"
    received = ensure_utc(reading.received_at) or utcnow()
    if (utcnow() - received).total_seconds() > offline_seconds:
        return "no_signal"
    return "ok"


def fleet_summary(db: Session) -> AgentFleetSummaryOut:
    trucks = list(db.scalars(select(Truck).where(Truck.is_deleted.is_(False))))
    by_status: dict[str, int] = {}
    for truck in trucks:
        by_status[truck.status] = by_status.get(truck.status, 0) + 1

    alerts_active, alerts_by_type = _active_by_type(db)
    start_utc, end_utc, start_local = _today_bounds()
    created_today, created_by_type = _counts_by_type(
        db, Alert.started_at, start_utc, end_utc
    )
    resolved_today, _ = _counts_by_type(db, Alert.resolved_at, start_utc, end_utc)

    active_trip_ids = select(Trip.id).where(Trip.state == "in_progress")
    pending_orders = int(
        db.scalar(
            select(func.count(TripOrder.id)).where(
                TripOrder.trip_id.in_(active_trip_ids),
                TripOrder.state.in_(("pending", "in_delivery")),
            )
        )
        or 0
    )
    active_trips = int(
        db.scalar(select(func.count(Trip.id)).where(Trip.state == "in_progress")) or 0
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

    return AgentFleetSummaryOut(
        generated_at=_iso(utcnow()),
        timezone=settings.app_timezone,
        window_start=_iso(start_local),
        trucks_total=len(trucks),
        trucks_by_status=by_status,
        alerts_active=alerts_active,
        alerts_by_type=alerts_by_type,
        alerts_created_today=created_today,
        alerts_created_today_by_type=created_by_type,
        alerts_resolved_today=resolved_today,
        trips_active=active_trips,
        pending_orders=pending_orders,
        routes_today=routes_today,
    )


def alerts_today(db: Session, *, limit: int = 10) -> AgentAlertsTodayOut:
    """Alertas creadas/resueltas desde la medianoche local de Tijuana."""
    start_utc, end_utc, start_local = _today_bounds()
    created_total, created_by_type = _counts_by_type(
        db, Alert.started_at, start_utc, end_utc
    )
    resolved_total, resolved_by_type = _counts_by_type(
        db, Alert.resolved_at, start_utc, end_utc
    )
    active_total, active_by_type = _active_by_type(db)

    rows = list(
        db.scalars(
            select(Alert)
            .where(Alert.started_at >= start_utc, Alert.started_at < end_utc)
            .order_by(Alert.started_at.desc())
            .limit(limit)
        )
    )
    plates = {
        truck.id: truck.plate
        for truck in db.scalars(
            select(Truck).where(
                Truck.id.in_({row.truck_id for row in rows if row.truck_id})
            )
        )
    }
    items = [
        AgentTodayAlertOut(
            alert_type=row.alert_type,
            truck_plate=plates.get(row.truck_id) if row.truck_id else None,
            status=row.status,
            started_at=_iso(row.started_at),
            resolved_at=_iso(row.resolved_at) if row.resolved_at else None,
            acknowledged=row.acknowledged_at is not None,
        )
        for row in rows
    ]
    return AgentAlertsTodayOut(
        generated_at=_iso(utcnow()),
        timezone=settings.app_timezone,
        window_start=_iso(start_local),
        created_total=created_total,
        resolved_total=resolved_total,
        active_total=active_total,
        created_by_type=created_by_type,
        resolved_by_type=resolved_by_type,
        active_by_type=active_by_type,
        items=items,
    )


def alerts(db: Session, *, limit: int = 10) -> AgentAlertsOut:
    rows = list(
        db.scalars(
            select(Alert)
            .where(Alert.status == "activa")
            .order_by(Alert.started_at.desc())
            .limit(limit)
        )
    )
    plates = {
        truck.id: truck.plate
        for truck in db.scalars(
            select(Truck).where(
                Truck.id.in_({row.truck_id for row in rows if row.truck_id})
            )
        )
    }
    items = [
        AgentAlertOut(
            alert_type=row.alert_type,
            truck_plate=plates.get(row.truck_id) if row.truck_id else None,
            value=row.value,
            min_value=row.min_value,
            max_value=row.max_value,
            started_at=_iso(row.started_at),
            age_minutes=_age_minutes(row.started_at),
            acknowledged=row.acknowledged_at is not None,
        )
        for row in rows
    ]
    return AgentAlertsOut(
        generated_at=_iso(utcnow()),
        timezone=settings.app_timezone,
        items=items,
    )


def truck_status(db: Session, truck_id: int) -> AgentTruckStatusOut | None:
    truck = db.scalar(
        select(Truck).where(Truck.id == truck_id, Truck.is_deleted.is_(False))
    )
    if truck is None:
        return None
    reading = _latest_reading(db, truck.id)
    door = _latest_door(db, truck.id)
    temp_min, temp_max, hum_min, hum_max = _thresholds(db, truck.id)
    setting = settings_service.get_settings(db)
    active_alerts = sorted(
        set(
            db.scalars(
                select(Alert.alert_type).where(
                    Alert.truck_id == truck.id, Alert.status == "activa"
                )
            )
        )
    )
    return AgentTruckStatusOut(
        generated_at=_iso(utcnow()),
        timezone=settings.app_timezone,
        truck_id=truck.id,
        plate=truck.plate,
        status=_container_status(
            reading,
            door,
            temperature_min=temp_min,
            temperature_max=temp_max,
            humidity_min=hum_min,
            humidity_max=hum_max,
            offline_seconds=setting.offline_timeout_seconds,
        ),
        temperature=reading.temperature if reading else None,
        humidity=reading.humidity if reading else None,
        age_minutes=_age_minutes(reading.received_at) if reading else None,
        door_open=door.is_open if door else None,
        temperature_min=temp_min,
        temperature_max=temp_max,
        humidity_min=hum_min,
        humidity_max=hum_max,
        active_alerts=active_alerts,
    )


def active_trips(db: Session, *, limit: int = 5) -> AgentTripsOut:
    trips = list(
        db.scalars(
            select(Trip)
            .where(Trip.state == "in_progress")
            .order_by(Trip.started_at.desc())
            .limit(limit)
        )
    )
    plates = {
        truck.id: truck.plate
        for truck in db.scalars(
            select(Truck).where(Truck.id.in_({trip.truck_id for trip in trips}))
        )
    }
    items: list[AgentTripOut] = []
    for trip in trips:
        orders = list(trip.orders)
        items.append(
            AgentTripOut(
                driver_alias=_alias(trip.driver_id),
                truck_plate=plates.get(trip.truck_id, ""),
                started_at=_iso(trip.started_at),
                orders_total=len(orders),
                orders_delivered=sum(
                    1 for order in orders if order.state == "delivered"
                ),
                orders_failed=sum(1 for order in orders if order.state == "failed"),
                orders_pending=sum(
                    1 for order in orders if order.state in ("pending", "in_delivery")
                ),
            )
        )
    return AgentTripsOut(
        generated_at=_iso(utcnow()),
        timezone=settings.app_timezone,
        items=items,
    )


def routes_today(db: Session, *, limit: int = 6) -> AgentRoutesOut:
    today = today_weekday()
    routes = list(
        db.scalars(
            select(Route)
            .where(
                Route.status == "activa",
                Route.id.in_(
                    select(RouteDeliveryDay.route_id).where(
                        RouteDeliveryDay.weekday == today
                    )
                ),
            )
            .order_by(Route.name)
            .limit(limit)
        )
    )
    items: list[AgentRouteOut] = []
    for route in routes:
        pending = int(
            db.scalar(
                select(func.count(TripOrder.id))
                .join(Trip, Trip.id == TripOrder.trip_id)
                .where(
                    Trip.route_id == route.id,
                    Trip.state == "in_progress",
                    TripOrder.state.in_(("pending", "in_delivery")),
                )
            )
            or 0
        )
        items.append(
            AgentRouteOut(
                name=_sanitize(route.name),
                driver_alias=_alias(route.assigned_driver_id),
                points=len(route.points),
                pending_orders=pending,
            )
        )
    return AgentRoutesOut(
        generated_at=_iso(utcnow()),
        timezone=settings.app_timezone,
        items=items,
    )


def thresholds(db: Session) -> AgentThresholdsOut:
    setting = settings_service.get_settings(db)
    overrides: list[AgentThresholdOverrideOut] = []
    for override in db.scalars(select(TruckThresholdOverride)):
        truck = db.get(Truck, override.truck_id)
        if truck is None or truck.is_deleted:
            continue
        temp_min, temp_max, hum_min, hum_max = _thresholds(db, truck.id)
        overrides.append(
            AgentThresholdOverrideOut(
                plate=truck.plate,
                temperature_min=temp_min,
                temperature_max=temp_max,
                humidity_min=hum_min,
                humidity_max=hum_max,
            )
        )
    return AgentThresholdsOut(
        generated_at=_iso(utcnow()),
        timezone=settings.app_timezone,
        temperature_min=round(setting.temperature_min, 2),
        temperature_max=round(setting.temperature_max, 2),
        humidity_min=round(setting.humidity_min, 2),
        humidity_max=round(setting.humidity_max, 2),
        overrides=overrides,
    )


def driver_aliases(db: Session) -> dict[int, str]:
    """Utilidad para pruebas/consumidores: id de conductor → alias."""
    return {driver_id: _alias(driver_id) for driver_id in db.scalars(select(Driver.id))}
