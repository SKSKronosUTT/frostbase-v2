from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.config import settings as app_settings
from app.repositories import alerts as alerts_repo
from app.repositories import readings as readings_repo
from app.repositories import trucks as trucks_repo
from app.schemas.dashboard import (
    DashboardAlert,
    DashboardSummary,
    DashboardTruck,
)
from app.services import settings_service
from app.services.serializers import (
    is_device_online,
    reading_status,
    serialize_route_brief_geometry,
)
from app.utils.time import ensure_utc, utcnow

SUMMARY_CACHE_KEY = "dashboard:summary"
SUMMARY_CACHE_SECONDS = 10


def get_summary(db: Session) -> DashboardSummary:
    cached = cache_get(SUMMARY_CACHE_KEY)
    if cached:
        try:
            return DashboardSummary.model_validate_json(cached)
        except ValueError:
            pass

    setting = settings_service.get_settings(db)
    status_counts = trucks_repo.count_by_status(db)
    total_trucks = sum(status_counts.values())
    active_trucks = status_counts.get("en_ruta", 0)

    trucks = trucks_repo.list_active(db)
    latest = readings_repo.get_latest_for_trucks(db, [truck.id for truck in trucks])
    fresh_threshold = utcnow() - timedelta(minutes=app_settings.dashboard_fresh_minutes)
    fresh_temperatures = [
        reading.temperature
        for reading in latest.values()
        if ensure_utc(reading.received_at) is not None
        and ensure_utc(reading.received_at) >= fresh_threshold
    ]
    avg_temperature = (
        round(sum(fresh_temperatures) / len(fresh_temperatures), 1)
        if fresh_temperatures
        else None
    )

    since = utcnow() - timedelta(hours=24)
    valid, total = readings_repo.effectiveness_since(
        db,
        since,
        setting.temperature_min,
        setting.temperature_max,
        setting.humidity_min,
        setting.humidity_max,
    )
    effectiveness = round(valid / total * 100, 1) if total else None

    summary = DashboardSummary(
        total_trucks=total_trucks,
        active_trucks=active_trucks,
        avg_temperature=avg_temperature,
        effectiveness=effectiveness,
        readings_24h=readings_repo.count_since(db, since),
        active_alerts=alerts_repo.count_active(db),
        trucks_by_status={
            "en_ruta": status_counts.get("en_ruta", 0),
            "disponible": status_counts.get("disponible", 0),
            "mantenimiento": status_counts.get("mantenimiento", 0),
        },
        last_update=ensure_utc(readings_repo.get_latest_received_at(db)),
        generated_at=utcnow(),
    )
    cache_set(
        SUMMARY_CACHE_KEY,
        summary.model_dump_json(),
        SUMMARY_CACHE_SECONDS,
    )
    return summary


def get_trucks(db: Session) -> list[DashboardTruck]:
    setting = settings_service.get_settings(db)
    trucks = trucks_repo.list_active(db)
    latest = readings_repo.get_latest_for_trucks(db, [truck.id for truck in trucks])
    active_counts = alerts_repo.active_counts_by_truck(db)

    return [
        DashboardTruck(
            id=truck.id,
            plate=truck.plate,
            brand=truck.brand,
            model=truck.model,
            status=truck.status,
            temperature=latest[truck.id].temperature if truck.id in latest else None,
            humidity=latest[truck.id].humidity if truck.id in latest else None,
            latitude=latest[truck.id].latitude if truck.id in latest else None,
            longitude=latest[truck.id].longitude if truck.id in latest else None,
            last_update=ensure_utc(latest[truck.id].received_at)
            if truck.id in latest
            else None,
            device_online=is_device_online(truck.device, setting.offline_timeout_seconds),
            reading_status=reading_status(latest.get(truck.id), setting),
            route=serialize_route_brief_geometry(truck.route),
            active_alerts=active_counts.get(truck.id, 0),
        )
        for truck in trucks
    ]


def get_alerts(db: Session) -> list[DashboardAlert]:
    return [
        DashboardAlert(
            id=alert.id,
            truck_id=alert.truck_id,
            truck_plate=alert.truck.plate if alert.truck else None,
            device_identifier=alert.device.device_id if alert.device else None,
            alert_type=alert.alert_type,
            value=alert.value,
            min_value=alert.min_value,
            max_value=alert.max_value,
            message=alert.message,
            started_at=ensure_utc(alert.started_at),
        )
        for alert in alerts_repo.list_active(db)
    ]
