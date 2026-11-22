"""Portal del conductor en modo consulta (G5).

Todas las consultas parten del ID del token (nunca del cliente) y solo
devuelven datos del conductor autenticado: su camión, sus rutas, sus
lecturas y las alertas de su dispositivo/camión.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.alert import Alert
from app.models.driver import Driver
from app.models.reading import Reading
from app.models.route import Route
from app.models.truck import Truck
from app.repositories import driver as driver_repo
from app.schemas.driver_portal import (
    DriverAlertOut,
    DriverContainerOut,
    DriverDashboardOut,
    DriverReadingOut,
    DriverRouteCard,
    DriverRouteDetail,
    DriverTruckCard,
)
from app.services import settings_service
from app.services.route_links import effective_route_for_truck, routes_for_driver
from app.utils.time import ensure_utc

logger = logging.getLogger("frostbase.driver_portal")

CONTAINER_STATUS_OK = "ok"
CONTAINER_STATUS_OUT_OF_RANGE = "out_of_range"
CONTAINER_STATUS_NO_DATA = "no_data"


def get_driver_truck(db: Session, driver: Driver) -> Truck | None:
    """Camión activo del conductor."""
    assignment = driver_repo.active_assignment(db, driver.id)
    if assignment is None:
        return None
    return driver_repo.truck_by_id(db, assignment.truck_id)


def _today_route(db: Session, driver: Driver) -> Route | None:
    return effective_route_for_truck(db, get_driver_truck(db, driver))


def _route_card(route: Route) -> DriverRouteCard:
    return DriverRouteCard(
        id=route.id,
        name=route.name,
        status=route.status,
        delivery_days=[day.weekday for day in route.delivery_days],
        points_count=len(route.points),
    )


def get_dashboard(db: Session, driver: Driver) -> DriverDashboardOut:
    """Resumen para la pantalla principal del conductor (una sola llamada)."""
    truck = get_driver_truck(db, driver)
    routes = routes_for_driver(db, driver.id)
    today = _today_route(db, driver)
    container = get_container_live(db, driver)
    active_alerts = 0
    if truck is not None:
        active_alerts = (
            db.scalar(
                select(Alert.id)
                .where(
                    Alert.truck_id == truck.id,
                    Alert.status == "activa",
                )
                .limit(1)
            )
            is not None
            and db.scalar(
                select(Alert.id)
                .where(Alert.truck_id == truck.id, Alert.status == "activa")
                .limit(1)
            )
            is not None
        )

        # Contar todas las activas, no solo verificar existencia.
        active_alerts = len(
            list(
                db.scalars(
                    select(Alert).where(
                        Alert.truck_id == truck.id, Alert.status == "activa"
                    )
                )
            )
        )

    return DriverDashboardOut(
        driver={
            "id": driver.id,
            "full_name": driver.full_name,
            "email": driver.email,
            "phone": driver.phone,
        },
        truck=(
            DriverTruckCard(
                id=truck.id,
                plate=truck.plate,
                brand=truck.brand,
                model=truck.model,
                year=truck.year,
                status=truck.status,
            )
            if truck
            else None
        ),
        today_route=_route_card(today) if today else None,
        routes=[_route_card(route) for route in routes],
        container=container,
        active_alerts=active_alerts,
    )


def get_container_live(db: Session, driver: Driver) -> DriverContainerOut:
    """Última lectura del camión con umbrales efectivos y estado del contenedor."""
    truck = get_driver_truck(db, driver)
    if truck is None:
        return DriverContainerOut()

    global_setting = settings_service.get_settings(db)
    from app.models.truck import TruckThresholdOverride

    override = db.scalar(
        select(TruckThresholdOverride).where(
            TruckThresholdOverride.truck_id == truck.id
        )
    )
    temp_min = (
        override.temperature_ideal - override.temperature_tolerance
        if override
        and override.temperature_ideal is not None
        and override.temperature_tolerance is not None
        else global_setting.temperature_min
    )
    temp_max = (
        override.temperature_ideal + override.temperature_tolerance
        if override
        and override.temperature_ideal is not None
        and override.temperature_tolerance is not None
        else global_setting.temperature_max
    )
    hum_min = (
        override.humidity_ideal - override.humidity_tolerance
        if override
        and override.humidity_ideal is not None
        and override.humidity_tolerance is not None
        else global_setting.humidity_min
    )
    hum_max = (
        override.humidity_ideal + override.humidity_tolerance
        if override
        and override.humidity_ideal is not None
        and override.humidity_tolerance is not None
        else global_setting.humidity_max
    )

    latest = db.scalar(
        select(Reading)
        .where(Reading.truck_id == truck.id)
        .order_by(Reading.received_at.desc())
        .limit(1)
    )

    if latest is None:
        return DriverContainerOut(
            temperature_min=temp_min,
            temperature_max=temp_max,
            humidity_min=hum_min,
            humidity_max=hum_max,
        )

    status = CONTAINER_STATUS_OK
    if latest.temperature < temp_min or latest.temperature > temp_max:
        status = CONTAINER_STATUS_OUT_OF_RANGE
    elif latest.humidity < hum_min or latest.humidity > hum_max:
        status = CONTAINER_STATUS_OUT_OF_RANGE

    return DriverContainerOut(
        temperature=latest.temperature,
        humidity=latest.humidity,
        latitude=latest.latitude,
        longitude=latest.longitude,
        received_at=ensure_utc(latest.received_at),
        status=status,
        temperature_min=temp_min,
        temperature_max=temp_max,
        humidity_min=hum_min,
        humidity_max=hum_max,
    )


def get_container_readings(
    db: Session,
    driver: Driver,
    *,
    limit: int = 60,
) -> list[DriverReadingOut]:
    """Lecturas recientes para la gráfica del contenedor."""
    truck = get_driver_truck(db, driver)
    if truck is None:
        return []
    readings = db.scalars(
        select(Reading)
        .where(Reading.truck_id == truck.id)
        .order_by(Reading.received_at.desc())
        .limit(limit)
    )
    return [
        DriverReadingOut(
            temperature=reading.temperature,
            humidity=reading.humidity,
            latitude=reading.latitude,
            longitude=reading.longitude,
            received_at=ensure_utc(reading.received_at),
            reading_timestamp=ensure_utc(reading.reading_timestamp),
        )
        for reading in reversed(list(readings))
    ]


def list_routes(db: Session, driver: Driver) -> list[DriverRouteCard]:
    return [_route_card(route) for route in routes_for_driver(db, driver.id)]


def get_route_today(db: Session, driver: Driver) -> DriverRouteCard | None:
    today = _today_route(db, driver)
    return _route_card(today) if today else None


def get_route_detail(
    db: Session, driver: Driver, route_id: int
) -> DriverRouteDetail | None:
    """Detalle de una ruta **del conductor** (404 si es de otro)."""
    route = db.scalar(
        select(Route)
        .options(selectinload(Route.delivery_days), selectinload(Route.points))
        .where(
            Route.id == route_id,
            Route.assigned_driver_id == driver.id,
        )
    )
    if route is None:
        return None
    return DriverRouteDetail(
        id=route.id,
        name=route.name,
        status=route.status,
        description=route.description,
        delivery_days=[day.weekday for day in route.delivery_days],
        geometry=route.geometry,
        points=[
            {
                "id": point.id,
                "name": point.name,
                "address": point.address,
                "latitude": point.latitude,
                "longitude": point.longitude,
                "order_index": point.order_index,
            }
            for point in sorted(route.points, key=lambda p: p.order_index)
        ],
    )


def list_alerts(
    db: Session,
    driver: Driver,
    *,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[DriverAlertOut], int]:
    """Alertas del camión del conductor, paginadas."""
    truck = get_driver_truck(db, driver)
    if truck is None:
        return [], 0

    stmt = select(Alert).where(Alert.truck_id == truck.id)
    count_stmt = select(Alert.id).where(Alert.truck_id == truck.id)
    if status:
        stmt = stmt.where(Alert.status == status)
        count_stmt = count_stmt.where(Alert.status == status)

    from sqlalchemy import func

    total = db.scalar(select(func.count()).select_from(count_stmt.subquery())) or 0

    alerts = db.scalars(
        stmt.order_by(Alert.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        DriverAlertOut(
            id=alert.id,
            alert_type=alert.alert_type,
            value=alert.value,
            min_value=alert.min_value,
            max_value=alert.max_value,
            message=alert.message,
            started_at=ensure_utc(alert.started_at),
            resolved_at=ensure_utc(alert.resolved_at),
            status=alert.status,
        )
        for alert in alerts
    ]
    return items, total
