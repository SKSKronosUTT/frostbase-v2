"""Datos de demostración realistas e idempotentes de FrostBase.

Uso (desde backend/):
    python -m scripts.seed_demo                 # crea/actualiza la demo
    python -m scripts.seed_demo --if-empty      # solo si la base está vacía
    python -m scripts.seed_demo --reset-demo    # borra y recrea solo lo demo
    python -m scripts.seed_demo --print-keys    # imprime las claves generadas
    python -m scripts.seed_demo --trucks 20 --devices 10   # extra para carga

Garantías:

- **Idempotente**: cada entidad usa un identificador estable (placa
  ``DEMO-00x``, dispositivo ``ESP32-DEMO-00x``, correo
  ``@demo.frostbase.local``, nombre ``Demo ·``). Ejecutarlo dos veces no
  duplica nada.
- **No destructivo**: ``--reset-demo`` elimina únicamente filas demo, en orden
  seguro de claves foráneas; los datos reales del usuario nunca se tocan.
- **Determinista**: PRNG con semilla fija; los tiempos son relativos a
  ``ahora`` para que la demo nunca envejezca.
- **Coherente con las reglas del módulo**: un solo viaje activo por
  conductor/camión, una sola orden en entrega, motivos obligatorios en
  órdenes fallidas, una alerta activa por dispositivo y tipo.

Las claves de dispositivo se generan aleatorias y solo pueden mostrarse una
vez: al crear cada dispositivo se imprimen con la marca ``DEMO DEVICE KEY``.
"""

from __future__ import annotations

import argparse
import logging
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database import SessionLocal
from app.core.security import (
    device_fingerprint,
    generate_device_secret,
    hash_password,
)
from app.models.alert import Alert
from app.models.device import Device
from app.models.door_event import DoorEvent
from app.models.driver import Driver, DriverTruckAssignment
from app.models.login_identity import LoginIdentity
from app.models.reading import Reading
from app.models.route import DeliveryPoint, Route, RouteDeliveryDay
from app.models.store import Store
from app.models.trip import Trip, TripLog, TripOrder
from app.models.truck import Truck, TruckThresholdOverride
from app.services import auth_service, routing, settings_service
from app.services.bootstrap import bootstrap_database, ensure_schema
from app.services.route_links import today_weekday
from app.utils.time import utcnow

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("frostbase.seed")

# ===== Catálogo demo =====

DEMO_PASSWORD = "Demo1234!"
DEMO_EMAIL_DOMAIN = "demo.frostbase.local"
DEMO_PREFIX = "Demo ·"
DEMO_DEVICE_IDS = ("ESP32-DEMO-001", "ESP32-DEMO-002", "ESP32-DEMO-003")
DEMO_PLATES = ("DEMO-001", "DEMO-002", "DEMO-003", "DEMO-004")

RNG = random.Random(42)

STORES: list[dict[str, Any]] = [
    {
        "key": "villa-fontana",
        "name": f"{DEMO_PREFIX}Villa Fontana",
        "address": "Blvd. Gustavo Díaz Ordaz 1000, Tijuana",
        "phone": "6641001001",
        "latitude": 32.5062,
        "longitude": -116.9725,
    },
    {
        "key": "zona-centro",
        "name": f"{DEMO_PREFIX}Zona Centro",
        "address": "Av. Revolución 500, Tijuana",
        "phone": "6641001002",
        "latitude": 32.5333,
        "longitude": -117.0369,
    },
    {
        "key": "playas",
        "name": f"{DEMO_PREFIX}Playas de Tijuana",
        "address": "Paseo Ensenada 200, Tijuana",
        "phone": "6641001003",
        "latitude": 32.5346,
        "longitude": -117.1217,
    },
    {
        "key": "otay",
        "name": f"{DEMO_PREFIX}Otay",
        "address": "Blvd. Industrial 300, Tijuana",
        "phone": "6641001004",
        "latitude": 32.5351,
        "longitude": -116.9701,
    },
    {
        "key": "la-mesa",
        "name": f"{DEMO_PREFIX}La Mesa",
        "address": "Blvd. Díaz Ordaz 2500, Tijuana",
        "phone": "6641001005",
        "latitude": 32.5006,
        "longitude": -116.9571,
    },
]

TRUCKS: list[dict[str, Any]] = [
    {
        "key": "t1",
        "brand": "Freightliner",
        "model": "M2 106",
        "year": 2022,
        "plate": "DEMO-001",
        "description": "Unidad de reparto refrigerado (demo: viaje en curso)",
        "status": "en_ruta",
    },
    {
        "key": "t2",
        "brand": "Isuzu",
        "model": "NPR",
        "year": 2021,
        "plate": "DEMO-002",
        "description": "Unidad disponible (demo: lista para iniciar viaje)",
        "status": "disponible",
    },
    {
        "key": "t3",
        "brand": "Kenworth",
        "model": "T370",
        "year": 2023,
        "plate": "DEMO-003",
        "description": "Unidad con ruta sin calendario (demo: NO_ROUTE_TODAY)",
        "status": "disponible",
    },
    {
        "key": "t4",
        "brand": "Hino",
        "model": "195",
        "year": 2020,
        "plate": "DEMO-004",
        "description": "Unidad en mantenimiento (demo: no disponible)",
        "status": "mantenimiento",
    },
]

DRIVERS: list[dict[str, Any]] = [
    {
        "key": "carlos",
        "first_name": "Carlos",
        "middle_name": "Alberto",
        "last_name": "Rivera",
        "email": f"carlos.rivera@{DEMO_EMAIL_DOMAIN}",
        "phone": "6645551001",
        "birthdate": date(1990, 3, 15),
        "is_active": True,
        "truck": "t1",
    },
    {
        "key": "ana",
        "first_name": "Ana",
        "middle_name": "Paola",
        "last_name": "Morales",
        "email": f"ana.morales@{DEMO_EMAIL_DOMAIN}",
        "phone": "6645551002",
        "birthdate": date(1993, 7, 22),
        "is_active": True,
        "truck": "t2",
    },
    {
        "key": "luis",
        "first_name": "Luis",
        "middle_name": None,
        "last_name": "Hernández",
        "email": f"luis.hernandez@{DEMO_EMAIL_DOMAIN}",
        "phone": "6645551003",
        "birthdate": date(1988, 11, 2),
        "is_active": True,
        "truck": "t3",
    },
    {
        "key": "marta",
        "first_name": "Marta",
        "middle_name": None,
        "last_name": "Díaz",
        "email": f"marta.diaz@{DEMO_EMAIL_DOMAIN}",
        "phone": "6645551004",
        "birthdate": date(1995, 1, 30),
        "is_active": False,
        "truck": None,
    },
]

ROUTES: list[dict[str, Any]] = [
    {
        "key": "carlos",
        "name": f"{DEMO_PREFIX}Ruta Carlos — Centro y Playas",
        "description": "Reparto diario de cadena de frío (demo)",
        "driver": "carlos",
        "stores": ["zona-centro", "playas", "villa-fontana", "otay"],
        "weekdays": [0, 1, 2, 3, 4, 5, 6],
    },
    {
        "key": "ana",
        "name": f"{DEMO_PREFIX}Ruta Ana — Otay y La Mesa",
        "description": "Reparto diario de cadena de frío (demo)",
        "driver": "ana",
        "stores": ["otay", "la-mesa", "villa-fontana", "zona-centro"],
        "weekdays": [0, 1, 2, 3, 4, 5, 6],
    },
    {
        "key": "luis",
        "name": f"{DEMO_PREFIX}Ruta Luis — sin calendario",
        "description": "Ruta activa sin días asignados (demo: NO_ROUTE_TODAY)",
        "driver": "luis",
        "stores": ["la-mesa", "playas"],
        "weekdays": [],
    },
    {
        # Segunda ruta activa: evita el fallback de "única ruta activa" de
        # G4.1 y así Luis no tiene ruta para hoy (demuestra NO_ROUTE_TODAY).
        "key": "luis-alt",
        "name": f"{DEMO_PREFIX}Ruta Luis — día alterno",
        "description": "Ruta con calendario en otro día (demo: ruta no es de hoy)",
        "driver": "luis",
        "stores": ["otay", "villa-fontana"],
        "weekdays": [(today_weekday() + 1) % 7],
    },
]


@dataclass
class SeedOutcome:
    """Resumen de lo creado en esta ejecución (para consola y pruebas)."""

    created: dict[str, int] = field(default_factory=dict)
    device_keys: list[tuple[str, str]] = field(default_factory=list)

    def add(self, key: str, amount: int = 1) -> None:
        if amount:
            self.created[key] = self.created.get(key, 0) + amount


# ===== Consultas de estado =====


def has_business_data(db) -> bool:
    """Hay camiones, conductores o rutas (la demo no debe pisar datos reales)."""
    return any(
        db.scalar(select(func.count(model.id))) > 0 for model in (Truck, Driver, Route)
    )


def demo_driver_ids(db) -> list[int]:
    return list(
        db.scalars(select(Driver.id).where(Driver.email.like(f"%@{DEMO_EMAIL_DOMAIN}")))
    )


def demo_truck_ids(db) -> list[int]:
    return list(db.scalars(select(Truck.id).where(Truck.plate.in_(DEMO_PLATES))))


def demo_device_ids(db) -> list[int]:
    return list(
        db.scalars(select(Device.id).where(Device.device_id.in_(DEMO_DEVICE_IDS)))
    )


# ===== Reset quirúrgico =====


def reset_demo(db) -> None:
    """Elimina solo las filas demo, en orden seguro de claves foráneas."""
    drivers = demo_driver_ids(db)
    trucks = demo_truck_ids(db)
    devices = demo_device_ids(db)

    if drivers:
        # Las órdenes y bitácoras cuelgan de trips (CASCADE).
        db.execute(delete(Trip).where(Trip.driver_id.in_(drivers)))
    if devices:
        db.execute(delete(DoorEvent).where(DoorEvent.device_id.in_(devices)))
        db.execute(delete(Reading).where(Reading.device_id.in_(devices)))
        db.execute(delete(Alert).where(Alert.device_id.in_(devices)))
    if trucks:
        db.execute(delete(Alert).where(Alert.truck_id.in_(trucks)))
        db.execute(
            delete(TruckThresholdOverride).where(
                TruckThresholdOverride.truck_id.in_(trucks)
            )
        )
    if drivers:
        db.execute(
            delete(DriverTruckAssignment).where(
                DriverTruckAssignment.driver_id.in_(drivers)
            )
        )
    if trucks:
        db.execute(
            delete(DriverTruckAssignment).where(
                DriverTruckAssignment.truck_id.in_(trucks)
            )
        )

    route_ids = list(
        db.scalars(select(Route.id).where(Route.name.like(f"{DEMO_PREFIX}%")))
    )
    if route_ids:
        db.execute(
            delete(RouteDeliveryDay).where(RouteDeliveryDay.route_id.in_(route_ids))
        )
        db.execute(delete(DeliveryPoint).where(DeliveryPoint.route_id.in_(route_ids)))
        db.execute(delete(Route).where(Route.id.in_(route_ids)))

    db.execute(
        delete(LoginIdentity).where(LoginIdentity.email.like(f"%@{DEMO_EMAIL_DOMAIN}"))
    )
    db.execute(delete(Driver).where(Driver.email.like(f"%@{DEMO_EMAIL_DOMAIN}")))
    if devices:
        db.execute(delete(Device).where(Device.id.in_(devices)))
    if trucks:
        db.execute(delete(Truck).where(Truck.id.in_(trucks)))
    db.execute(delete(Store).where(Store.name.like(f"{DEMO_PREFIX}%")))
    db.flush()
    logger.info(
        "Datos demo eliminados: %s conductores, %s camiones, %s dispositivos",
        len(drivers),
        len(trucks),
        len(devices),
    )


# ===== Constructores idempotentes =====


def _get_or_create_store(db, spec: dict, outcome: SeedOutcome) -> Store:
    store = db.scalar(select(Store).where(Store.name == spec["name"]))
    if store is not None:
        return store
    store = Store(
        name=spec["name"],
        address=spec["address"],
        phone=spec["phone"],
        latitude=spec["latitude"],
        longitude=spec["longitude"],
    )
    db.add(store)
    db.flush()
    outcome.add("stores")
    return store


def _get_or_create_truck(db, spec: dict, outcome: SeedOutcome) -> Truck:
    truck = db.scalar(
        select(Truck).where(Truck.plate == spec["plate"], Truck.is_deleted.is_(False))
    )
    if truck is not None:
        return truck
    truck = Truck(
        brand=spec["brand"],
        model=spec["model"],
        year=spec["year"],
        plate=spec["plate"],
        description=spec["description"],
        status=spec["status"],
    )
    db.add(truck)
    db.flush()
    outcome.add("trucks")
    return truck


def _ensure_device(db, device_id: str, truck: Truck, outcome: SeedOutcome) -> Device:
    device = db.scalar(select(Device).where(Device.device_id == device_id))
    if device is not None:
        if device.truck_id is None:
            device.truck_id = truck.id
            db.add(device)
            db.flush()
        return device
    secret = generate_device_secret()
    device = Device(
        device_id=device_id,
        truck_id=truck.id,
        key_hash=device_fingerprint(secret),
        key_scheme="hmac",
    )
    db.add(device)
    db.flush()
    outcome.add("devices")
    outcome.device_keys.append((device_id, secret))
    return device


def _get_or_create_driver(db, spec: dict, outcome: SeedOutcome) -> Driver:
    driver = db.scalar(
        select(Driver).where(func.lower(Driver.email) == spec["email"].lower())
    )
    if driver is not None:
        return driver
    driver = Driver(
        first_name=spec["first_name"],
        middle_name=spec["middle_name"],
        last_name=spec["last_name"],
        email=spec["email"],
        phone=spec["phone"],
        birthdate=spec["birthdate"],
        password_hash=hash_password(DEMO_PASSWORD),
        is_active=spec["is_active"],
        must_change_password=False,
    )
    db.add(driver)
    db.flush()
    auth_service.ensure_login_identity(
        db, email=driver.email, account_type="driver", account_id=driver.id
    )
    outcome.add("drivers")
    return driver


def _ensure_assignment(db, driver: Driver, truck: Truck, outcome: SeedOutcome) -> None:
    current = db.scalar(
        select(DriverTruckAssignment).where(
            DriverTruckAssignment.driver_id == driver.id,
            DriverTruckAssignment.unassigned_at.is_(None),
        )
    )
    if current is not None:
        return
    db.add(DriverTruckAssignment(driver_id=driver.id, truck_id=truck.id))
    db.flush()
    outcome.add("assignments")


def _get_or_create_route(
    db, spec: dict, driver: Driver, stores: dict[str, Store], outcome: SeedOutcome
) -> Route:
    route = db.scalar(select(Route).where(Route.name == spec["name"]))
    if route is not None:
        return route

    route = Route(
        name=spec["name"],
        description=spec["description"],
        status="activa",
        assigned_driver_id=driver.id,
    )
    points: list[DeliveryPoint] = []
    for index, store_key in enumerate(spec["stores"]):
        store = stores[store_key]
        points.append(
            DeliveryPoint(
                store_id=store.id,
                name=store.name,
                address=store.address,
                latitude=store.latitude,
                longitude=store.longitude,
                order_index=index,
            )
        )
    route.points = points
    route.delivery_days = [
        RouteDeliveryDay(driver_id=driver.id, weekday=weekday)
        for weekday in spec["weekdays"]
    ]

    try:
        route.geometry = routing.calculate_geometry(
            [(point.latitude, point.longitude) for point in points]
        )
    except routing.RoutingUnavailableError as exc:
        logger.warning(
            "OSRM no disponible; ruta '%s' sin geometría: %s", spec["name"], exc
        )

    db.add(route)
    db.flush()
    outcome.add("routes")
    return route


def _ensure_thresholds(db, truck: Truck, outcome: SeedOutcome) -> None:
    existing = db.scalar(
        select(TruckThresholdOverride).where(
            TruckThresholdOverride.truck_id == truck.id
        )
    )
    if existing is not None:
        return
    db.add(
        TruckThresholdOverride(
            truck_id=truck.id,
            temperature_ideal=-1.0,
            temperature_tolerance=2.0,
        )
    )
    db.flush()
    outcome.add("thresholds")


# ===== Lecturas, alertas, puerta y viajes =====


def _reading_rows(
    *,
    device: Device,
    truck: Truck,
    start: datetime,
    end: datetime,
    step_minutes: int,
    temperature: float,
    temp_jitter: float,
    humidity: float,
    hum_jitter: float,
    last_temperature: float | None = None,
    last_humidity: float | None = None,
) -> list[dict]:
    def make_row(when: datetime) -> dict:
        return {
            "device_id": device.id,
            "truck_id": truck.id,
            "temperature": round(
                temperature + RNG.uniform(-temp_jitter, temp_jitter), 1
            ),
            "humidity": round(humidity + RNG.uniform(-hum_jitter, hum_jitter), 1),
            "latitude": round(truck_lat(truck) + RNG.uniform(-2e-4, 2e-4), 6),
            "longitude": round(truck_lon(truck) + RNG.uniform(-2e-4, 2e-4), 6),
            "received_at": when,
            "reading_timestamp": when,
        }

    rows: list[dict] = []
    current = start
    while current < end:
        rows.append(make_row(current))
        current += timedelta(minutes=step_minutes)
    # La última lectura queda exactamente en ``end`` (así el estado del
    # contenedor refleja «hace 2 minutos» o «hace 50 minutos» y no un paso más).
    rows.append(make_row(end))
    if last_temperature is not None:
        rows[-1]["temperature"] = last_temperature
    if last_humidity is not None:
        rows[-1]["humidity"] = last_humidity
    return rows


def truck_lat(truck: Truck) -> float:
    return 32.5149 if truck.plate != "DEMO-003" else 32.5006


def truck_lon(truck: Truck) -> float:
    return -117.0382 if truck.plate != "DEMO-003" else -116.9571


def _seed_readings(db, trucks: dict, devices: dict, outcome: SeedOutcome) -> None:
    now = utcnow()
    truck1 = trucks["t1"]
    truck2 = trucks["t2"]
    truck3 = trucks["t3"]
    if db.scalar(
        select(func.count(Reading.id)).where(Reading.device_id.in_(demo_device_ids(db)))
    ):
        return

    # t1: última lectura fuera de rango y reciente; t2: fresca y normal;
    # t3: última lectura antigua (no_signal/desconexión); t4: sin lecturas.
    plans = [
        (truck1, devices["t1"], now - timedelta(seconds=20), 3.5, 78.0),
        (truck2, devices["t2"], now - timedelta(seconds=20), -2.4, 80.5),
        (truck3, devices["t3"], now - timedelta(minutes=45), -2.6, 81.0),
    ]
    total = 0
    for truck, device, end, last_temperature, last_humidity in plans:
        rows = _reading_rows(
            device=device,
            truck=truck,
            start=now - timedelta(hours=24),
            end=end,
            step_minutes=10,
            temperature=-2.5,
            temp_jitter=0.4,
            humidity=80.0,
            hum_jitter=2.0,
            last_temperature=last_temperature,
            last_humidity=last_humidity,
        )
        stmt = (
            pg_insert(Reading)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["device_id", "reading_timestamp"])
        )
        db.execute(stmt)
        device.last_seen = rows[-1]["received_at"]
        db.add(device)
        total += len(rows)
    db.flush()
    outcome.add("readings", total)


def _seed_alerts(
    db,
    trucks: dict,
    devices: dict,
    drivers: dict,
    trip: Trip | None,
    outcome: SeedOutcome,
) -> list[Alert]:
    now = utcnow()
    carlos = drivers["carlos"]
    specs: list[Alert] = [
        Alert(
            truck_id=trucks["t1"].id,
            device_id=devices["t1"].id,
            trip_id=trip.id if trip else None,
            alert_type="temperatura",
            value=3.5,
            min_value=-3.0,
            max_value=1.0,
            message=(
                "Temperatura fuera de rango: 3.5 °C. Rango permitido: -3.0 a 1.0 °C."
            ),
            started_at=now - timedelta(minutes=2),
            status="activa",
        ),
        Alert(
            truck_id=trucks["t1"].id,
            device_id=devices["t1"].id,
            trip_id=trip.id if trip else None,
            alert_type="puerta",
            message=(
                "Puerta abierta sin autorización durante el viaje "
                "(más de 30 s sin entrega en curso)."
            ),
            started_at=now - timedelta(minutes=6),
            status="activa",
            acknowledged_at=now - timedelta(minutes=3),
            acknowledged_by=carlos.id,
        ),
        Alert(
            truck_id=trucks["t3"].id,
            device_id=devices["t3"].id,
            alert_type="desconexion",
            message=(
                "El dispositivo dejó de enviar lecturas dentro del tiempo esperado."
            ),
            started_at=now - timedelta(minutes=45),
            status="activa",
        ),
        Alert(
            truck_id=trucks["t2"].id,
            device_id=devices["t2"].id,
            alert_type="temperatura",
            value=6.2,
            min_value=-5.0,
            max_value=1.0,
            message="Temperatura fuera de rango (resuelta): 6.2 °C.",
            started_at=now - timedelta(hours=26),
            resolved_at=now - timedelta(hours=25),
            status="resuelta",
        ),
    ]

    created: list[Alert] = []
    for alert in specs:
        exists = db.scalar(
            select(Alert.id)
            .where(
                Alert.device_id == alert.device_id,
                Alert.alert_type == alert.alert_type,
                Alert.status == alert.status,
            )
            .limit(1)
        )
        if exists is None:
            db.add(alert)
            created.append(alert)
    db.flush()
    outcome.add("alerts", len(created))

    # Devuelve todas las alertas demo (creadas o preexistentes), no solo las
    # nuevas: otra instancia (p. ej. el watcher) pudo crear alguna antes.
    return list(
        db.scalars(select(Alert).where(Alert.device_id.in_(demo_device_ids(db))))
    )


def _seed_door_events(
    db, devices: dict, alerts: list[Alert] | None, outcome: SeedOutcome
) -> None:
    now = utcnow()
    device = devices["t1"]
    if db.scalar(
        select(func.count(DoorEvent.id)).where(DoorEvent.device_id == device.id)
    ):
        return
    door_alert = next(
        (alert for alert in (alerts or []) if alert.alert_type == "puerta"), None
    )
    events = [
        DoorEvent(
            device_id=device.id,
            truck_id=device.truck_id,
            is_open=True,
            event_time=now - timedelta(minutes=7),
            received_at=now - timedelta(minutes=7),
            evaluated_at=now - timedelta(minutes=6),
            alert_id=door_alert.id if door_alert else None,
        ),
        DoorEvent(
            device_id=device.id,
            truck_id=device.truck_id,
            is_open=False,
            event_time=now - timedelta(days=1, hours=3),
            received_at=now - timedelta(days=1, hours=3),
            evaluated_at=now - timedelta(days=1, hours=3),
        ),
        DoorEvent(
            device_id=device.id,
            truck_id=device.truck_id,
            is_open=True,
            event_time=now - timedelta(days=1, hours=4),
            received_at=now - timedelta(days=1, hours=4),
            evaluated_at=now - timedelta(days=1, hours=4),
        ),
    ]
    db.add_all(events)
    db.flush()
    outcome.add("door_events", len(events))


def _trip_orders(
    route: Route,
    *,
    states: list[str],
    started_at: datetime,
) -> list[TripOrder]:
    points = sorted(route.points, key=lambda point: point.order_index)
    orders: list[TripOrder] = []
    for index, state in enumerate(states):
        point = points[index % len(points)]
        order = TripOrder(
            delivery_point_id=point.id,
            store_id=point.store_id,
            order_index=index,
            name=point.name,
            address=point.address,
            latitude=point.latitude,
            longitude=point.longitude,
            state=state,
        )
        if state in ("in_delivery", "delivered", "failed"):
            order.started_at = started_at + timedelta(minutes=10 + index * 20)
        if state == "delivered":
            order.delivered_at = started_at + timedelta(minutes=20 + index * 20)
        if state == "failed":
            order.failure_reason = "Cliente cerrado"
        orders.append(order)
    return orders


def _create_trip(
    db,
    *,
    driver: Driver,
    truck: Truck,
    route: Route,
    started_at: datetime,
    ended_at: datetime | None,
    states: list[str],
    outcome: SeedOutcome,
) -> Trip:
    trip = Trip(
        driver_id=driver.id,
        truck_id=truck.id,
        route_id=route.id,
        state="in_progress" if ended_at is None else "completed",
        started_at=started_at,
        ended_at=ended_at,
    )
    trip.orders = _trip_orders(route, states=states, started_at=started_at)
    db.add(trip)
    db.flush()

    logs = [
        TripLog(
            trip_id=trip.id,
            event="trip_started",
            detail=f"Ruta: {route.name}",
            actor_driver_id=driver.id,
            created_at=started_at,
        )
    ]
    for order in trip.orders:
        if order.started_at is not None:
            logs.append(
                TripLog(
                    trip_id=trip.id,
                    order_id=order.id,
                    event="order_started",
                    actor_driver_id=driver.id,
                    created_at=order.started_at,
                )
            )
        if order.delivered_at is not None:
            logs.append(
                TripLog(
                    trip_id=trip.id,
                    order_id=order.id,
                    event="order_delivered",
                    actor_driver_id=driver.id,
                    created_at=order.delivered_at,
                )
            )
        if order.state == "failed":
            logs.append(
                TripLog(
                    trip_id=trip.id,
                    order_id=order.id,
                    event="order_failed",
                    detail=f"Motivo: {order.failure_reason}",
                    actor_driver_id=driver.id,
                    created_at=order.started_at or started_at,
                )
            )
    if ended_at is not None:
        logs.append(
            TripLog(
                trip_id=trip.id,
                event="trip_ended",
                detail=(
                    f"Órdenes: {len(trip.orders)} total, "
                    f"{sum(1 for order in trip.orders if order.state == 'delivered')} "
                    "entregadas"
                ),
                actor_driver_id=driver.id,
                created_at=ended_at,
            )
        )
    db.add_all(logs)
    db.flush()
    outcome.add("trips")
    outcome.add("trip_orders", len(trip.orders))
    return trip


def _seed_trips(
    db, routes: dict, drivers: dict, trucks: dict, outcome: SeedOutcome
) -> Trip | None:
    driver_ids = demo_driver_ids(db)
    if driver_ids and db.scalar(
        select(func.count(Trip.id)).where(Trip.driver_id.in_(driver_ids))
    ):
        return None

    now = utcnow()
    carlos = drivers["carlos"]
    ana = drivers["ana"]
    route_carlos = routes["carlos"]
    route_ana = routes["ana"]

    # Viaje en curso de Carlos: 1 entregada, 1 fallida, 2 pendientes.
    active = _create_trip(
        db,
        driver=carlos,
        truck=trucks["t1"],
        route=route_carlos,
        started_at=now - timedelta(hours=2),
        ended_at=None,
        states=["delivered", "failed", "pending", "pending"],
        outcome=outcome,
    )
    # Dos viajes completados para poblar el historial.
    _create_trip(
        db,
        driver=carlos,
        truck=trucks["t1"],
        route=route_carlos,
        started_at=now - timedelta(days=1, hours=6),
        ended_at=now - timedelta(days=1, hours=2),
        states=["delivered", "delivered", "failed"],
        outcome=outcome,
    )
    _create_trip(
        db,
        driver=carlos,
        truck=trucks["t1"],
        route=route_carlos,
        started_at=now - timedelta(days=2, hours=5),
        ended_at=now - timedelta(days=2, hours=1),
        states=["delivered", "delivered", "delivered"],
        outcome=outcome,
    )
    # Viaje completado de Ana (su camión queda disponible).
    _create_trip(
        db,
        driver=ana,
        truck=trucks["t2"],
        route=route_ana,
        started_at=now - timedelta(days=1, hours=7),
        ended_at=now - timedelta(days=1, hours=3),
        states=["delivered", "delivered", "delivered", "delivered"],
        outcome=outcome,
    )
    return active


# ===== Orquestación =====


def run_seed(db, *, reset: bool = False) -> SeedOutcome:
    """Siembra la demo (sin commit; el llamador decide la transacción)."""
    outcome = SeedOutcome()
    if reset:
        reset_demo(db)

    settings_service.ensure_settings(db)

    stores = {spec["key"]: _get_or_create_store(db, spec, outcome) for spec in STORES}
    trucks = {spec["key"]: _get_or_create_truck(db, spec, outcome) for spec in TRUCKS}
    devices: dict[str, Device] = {}
    for index, device_id in enumerate(DEMO_DEVICE_IDS):
        truck_key = ("t1", "t2", "t3")[index]
        devices[truck_key] = _ensure_device(db, device_id, trucks[truck_key], outcome)

    drivers = {
        spec["key"]: _get_or_create_driver(db, spec, outcome) for spec in DRIVERS
    }
    for spec in DRIVERS:
        if spec["truck"] is None:
            continue
        _ensure_assignment(db, drivers[spec["key"]], trucks[spec["truck"]], outcome)

    routes = {
        spec["key"]: _get_or_create_route(
            db, spec, drivers[spec["driver"]], stores, outcome
        )
        for spec in ROUTES
    }

    _ensure_thresholds(db, trucks["t1"], outcome)
    _seed_readings(db, trucks, devices, outcome)

    active_trip = _seed_trips(db, routes, drivers, trucks, outcome)

    alerts = _seed_alerts(db, trucks, devices, drivers, active_trip, outcome)
    _seed_door_events(db, devices, alerts, outcome)

    return outcome


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Datos demo de FrostBase")
    parser.add_argument(
        "--if-empty",
        action="store_true",
        help="Siembra solo si no hay camiones, conductores ni rutas",
    )
    parser.add_argument(
        "--reset-demo",
        "--reset",
        dest="reset_demo",
        action="store_true",
        help="Elimina solo los datos demo antes de sembrar",
    )
    parser.add_argument(
        "--print-keys",
        action="store_true",
        help="Imprime las claves de dispositivo generadas en esta ejecución",
    )
    parser.add_argument(
        "--trucks", type=int, default=len(TRUCKS), help="Total de camiones"
    )
    parser.add_argument(
        "--devices",
        type=int,
        default=len(DEMO_DEVICE_IDS),
        help="Total de dispositivos",
    )
    parser.add_argument(
        "--no-extra",
        action="store_true",
        help="No genera camiones/dispositivos extra para pruebas de carga",
    )
    return parser.parse_args()


def _seed_extra_load_data(db, args: argparse.Namespace, outcome: SeedOutcome) -> None:
    """Camiones/dispositivos adicionales para pruebas de carga (LOAD-xxx).

    La relación camión↔dispositivo es 1:1, así que cada dispositivo extra
    recibe su propio camión de carga.
    """
    if args.no_extra:
        return

    for index in range(len(TRUCKS), args.trucks):
        plate = f"LOAD-{index + 1:03d}"
        truck = db.scalar(select(Truck).where(Truck.plate == plate))
        if truck is None:
            truck = Truck(
                brand="LoadTest",
                model="Generado",
                year=2024,
                plate=plate,
                description="Camión generado para pruebas de carga",
                status="disponible",
            )
            db.add(truck)
            db.flush()
            outcome.add("extra_trucks")

    for index in range(len(DEMO_DEVICE_IDS), args.devices):
        plate = f"LOAD-EXT-{index + 1:03d}"
        truck = db.scalar(select(Truck).where(Truck.plate == plate))
        if truck is None:
            truck = Truck(
                brand="LoadTest",
                model="Extra",
                year=2024,
                plate=plate,
                description="Camión extra para pruebas de carga",
                status="disponible",
            )
            db.add(truck)
            db.flush()
        _ensure_device(db, f"LOAD-DEV-{index + 1:03d}", truck, outcome)


def main() -> None:
    args = parse_args()
    if args.trucks < len(TRUCKS):
        raise SystemExit(f"--trucks debe ser >= {len(TRUCKS)}")
    if args.devices < len(DEMO_DEVICE_IDS):
        raise SystemExit(f"--devices debe ser >= {len(DEMO_DEVICE_IDS)}")

    ensure_schema()
    with SessionLocal() as db:
        bootstrap_database(db)
        if args.if_empty and has_business_data(db):
            logger.info(
                "Datos demo omitidos: la base ya tiene camiones, conductores "
                "o rutas (use --reset-demo para recrearlos)."
            )
            return

        outcome = run_seed(db, reset=args.reset_demo)
        _seed_extra_load_data(db, args, outcome)
        db.commit()

    print("\n=== Datos de demostración de FrostBase ===")
    summary = ", ".join(
        f"{count} {name}" for name, count in sorted(outcome.created.items())
    )
    print(f"Creado en esta ejecución: {summary or 'nada (ya existía)'}")
    print(f"Contraseña demo de conductores: {DEMO_PASSWORD}")
    print(
        "Conductores: "
        + ", ".join(spec["email"] for spec in DRIVERS if spec["is_active"])
    )
    if outcome.device_keys:
        print("\nClaves de dispositivos (guárdelas, no se muestran de nuevo):")
        for device_id, secret in outcome.device_keys:
            print(f"DEMO DEVICE KEY {device_id}: {secret}")
        print(
            "\nCopie la clave de ESP32-DEMO-001 en iot-simulator/.env como "
            "DEVICE_KEY. NO es la placa del camión."
        )
    elif args.print_keys:
        print(
            "\nLos dispositivos ya existían: sus claves no se pueden recuperar. "
            "Rótelas con scripts.rotate_device_key."
        )
    print()


if __name__ == "__main__":
    main()
