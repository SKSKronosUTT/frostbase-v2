from datetime import timedelta
from typing import Any

from app.models.alert import Alert
from app.models.device import Device
from app.models.reading import Reading
from app.models.route import Route
from app.models.setting import Setting
from app.models.truck import Truck
from app.schemas.alert import AlertOut
from app.schemas.device import DeviceOut
from app.schemas.reading import ReadingOut
from app.schemas.route import (
    AssignedDriverOut,
    AssignedTruckOut,
    DeliveryPointOut,
    RouteBrief,
    RouteBriefWithGeometry,
    RouteOut,
)
from app.schemas.truck import TruckDetailOut, TruckOut
from app.utils.geo import simplify_polyline
from app.utils.time import ensure_utc, utcnow


def is_device_online(device: Device | None, timeout_seconds: int) -> bool:
    if device is None or device.last_seen is None:
        return False
    last_seen = ensure_utc(device.last_seen)
    return last_seen >= utcnow() - timedelta(seconds=timeout_seconds)


def serialize_device(device: Device | None, timeout_seconds: int) -> DeviceOut | None:
    if device is None:
        return None
    return DeviceOut(
        id=device.id,
        device_id=device.device_id,
        truck_id=device.truck_id,
        truck_plate=device.truck.plate if device.truck else None,
        is_online=is_device_online(device, timeout_seconds),
        last_seen=ensure_utc(device.last_seen),
        created_at=ensure_utc(device.created_at),
    )


def serialize_reading(reading: Reading | None) -> ReadingOut | None:
    if reading is None:
        return None
    return ReadingOut(
        id=reading.id,
        device_id=reading.device_id,
        truck_id=reading.truck_id,
        temperature=reading.temperature,
        humidity=reading.humidity,
        latitude=reading.latitude,
        longitude=reading.longitude,
        received_at=ensure_utc(reading.received_at),
        reading_timestamp=ensure_utc(reading.reading_timestamp),
    )


def serialize_point(point) -> DeliveryPointOut:
    return DeliveryPointOut(
        id=point.id,
        name=point.name,
        address=point.address,
        latitude=point.latitude,
        longitude=point.longitude,
        order_index=point.order_index,
    )


def serialize_route_brief(route: Route | None) -> RouteBrief | None:
    if route is None:
        return None
    return RouteBrief(id=route.id, name=route.name, status=route.status)


def serialize_route_brief_geometry(
    route: Route | None,
) -> RouteBriefWithGeometry | None:
    if route is None:
        return None
    return RouteBriefWithGeometry(
        id=route.id,
        name=route.name,
        status=route.status,
        geometry=simplify_polyline(route.geometry) if route.geometry else None,
    )


def serialize_route(route: Route, warning: str | None = None) -> RouteOut:
    truck = route.truck
    driver = route.assigned_driver
    return RouteOut(
        id=route.id,
        name=route.name,
        description=route.description,
        status=route.status,
        geometry=route.geometry,
        points=[
            serialize_point(point)
            for point in sorted(route.points, key=lambda p: p.order_index)
        ],
        truck=(
            AssignedTruckOut(
                id=truck.id, plate=truck.plate, brand=truck.brand, model=truck.model
            )
            if truck
            else None
        ),
        assigned_driver=(
            AssignedDriverOut(id=driver.id, full_name=driver.full_name)
            if driver
            else None
        ),
        delivery_days=[day.weekday for day in route.delivery_days],
        created_at=ensure_utc(route.created_at),
        updated_at=ensure_utc(route.updated_at),
        warning=warning,
        geometry_status=route.geometry_status,
    )


def serialize_alert(alert: Alert) -> AlertOut:
    return AlertOut(
        id=alert.id,
        truck_id=alert.truck_id,
        truck_plate=alert.truck.plate if alert.truck else None,
        device_id=alert.device_id,
        device_identifier=alert.device.device_id if alert.device else None,
        alert_type=alert.alert_type,
        value=alert.value,
        min_value=alert.min_value,
        max_value=alert.max_value,
        message=alert.message,
        started_at=ensure_utc(alert.started_at),
        resolved_at=ensure_utc(alert.resolved_at),
        status=alert.status,
    )


def reading_status(reading: Reading | None, setting: Setting) -> str:
    if reading is None:
        return "sin_lectura"
    if (
        reading.temperature < setting.temperature_min
        or reading.temperature > setting.temperature_max
    ):
        return "alerta"
    if (
        reading.humidity < setting.humidity_min
        or reading.humidity > setting.humidity_max
    ):
        return "alerta"
    return "normal"


def serialize_truck(
    truck: Truck,
    *,
    latest_reading: Reading | None,
    setting: Setting,
    active_alerts: int = 0,
    detail: bool = False,
) -> TruckOut:
    device = serialize_device(truck.device, setting.offline_timeout_seconds)
    base: dict[str, Any] = dict(
        id=truck.id,
        brand=truck.brand,
        model=truck.model,
        year=truck.year,
        plate=truck.plate,
        description=truck.description,
        status=truck.status,
        device=device,
        current_reading=serialize_reading(latest_reading),
        active_alerts=active_alerts,
        created_at=ensure_utc(truck.created_at),
    )
    if detail:
        return TruckDetailOut(
            **base,
            route=serialize_route(truck.route) if truck.route else None,
            temperature_min=setting.temperature_min,
            temperature_max=setting.temperature_max,
            humidity_min=setting.humidity_min,
            humidity_max=setting.humidity_max,
        )
    return TruckOut(**base, route=serialize_route_brief(truck.route))
