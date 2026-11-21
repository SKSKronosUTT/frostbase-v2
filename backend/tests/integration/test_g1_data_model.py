"""Restricciones del modelo de datos de conductores (G1).

Valida a nivel de base de datos las decisiones de G0: unicidad global del
correo, relevo conductor-camión con una asignación activa, una ruta activa por
conductor y día, un viaje en curso por conductor/camión, idempotencia de
eventos de puerta y motivo obligatorio en órdenes fallidas.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.alert import Alert
from app.models.device import Device
from app.models.door_event import DoorEvent
from app.models.driver import Driver, DriverTruckAssignment
from app.models.login_identity import LoginIdentity
from app.models.route import Route, RouteDeliveryDay
from app.models.setting import Setting
from app.models.trip import Trip, TripOrder
from app.models.truck import Truck, TruckThresholdOverride
from app.utils.time import utcnow


def _driver(email: str = "juan.perez@frostbase.local") -> Driver:
    return Driver(
        first_name="Juan",
        last_name="Pérez",
        email=email,
        phone="6641234567",
        birthdate=date(1990, 5, 17),
        password_hash=hash_password("Temporal123!"),
    )


def _truck(plate: str = "G1-001") -> Truck:
    return Truck(brand="Test", model="G1", year=2024, plate=plate)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def test_driver_email_is_globally_unique_case_insensitive(db):
    db.add(_driver("juan.perez@frostbase.local"))
    db.commit()

    db.add(_driver("JUAN.PEREZ@frostbase.local"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_login_identity_email_unique_across_account_types(db):
    db.add(
        LoginIdentity(email="uno@frostbase.local", account_type="admin", account_id=1)
    )
    db.commit()

    db.add(
        LoginIdentity(email="uno@frostbase.local", account_type="driver", account_id=1)
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_only_one_active_assignment_per_driver_and_per_truck(db):
    driver_a = _driver("a@frostbase.local")
    driver_b = _driver("b@frostbase.local")
    truck_one = _truck("G1-001")
    truck_two = _truck("G1-002")
    db.add_all([driver_a, driver_b, truck_one, truck_two])
    db.flush()

    db.add_all(
        [
            DriverTruckAssignment(driver_id=driver_a.id, truck_id=truck_one.id),
            DriverTruckAssignment(driver_id=driver_b.id, truck_id=truck_two.id),
        ]
    )
    db.commit()

    # Mismo conductor, segundo camión activo.
    db.add(DriverTruckAssignment(driver_id=driver_a.id, truck_id=truck_two.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Otro conductor, camión ya ocupado.
    db.add(DriverTruckAssignment(driver_id=driver_b.id, truck_id=truck_one.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # El relevo cierra la asignación anterior y permite la nueva:
    # el camión 1 pasa del conductor A al conductor B.
    now = utcnow()
    db.execute(
        DriverTruckAssignment.__table__.update()
        .where(DriverTruckAssignment.unassigned_at.is_(None))
        .values(unassigned_at=now)
    )
    db.flush()
    db.add(DriverTruckAssignment(driver_id=driver_b.id, truck_id=truck_one.id))
    db.commit()

    active = (
        db.query(DriverTruckAssignment)
        .filter(DriverTruckAssignment.unassigned_at.is_(None))
        .all()
    )
    assert len(active) == 1
    assert active[0].driver_id == driver_b.id
    assert active[0].truck_id == truck_one.id


def test_one_route_per_driver_per_weekday(db):
    driver = _driver()
    truck_one = _truck("G1-101")
    truck_two = _truck("G1-102")
    db.add_all([driver, truck_one, truck_two])
    db.flush()

    route_one = Route(name="Ruta lunes A", assigned_driver_id=driver.id)
    route_two = Route(name="Ruta lunes B", assigned_driver_id=driver.id)
    db.add_all([route_one, route_two])
    db.flush()

    db.add(RouteDeliveryDay(route_id=route_one.id, driver_id=driver.id, weekday=1))
    db.commit()

    # Segunda ruta del mismo conductor el mismo día.
    db.add(RouteDeliveryDay(route_id=route_two.id, driver_id=driver.id, weekday=1))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # El mismo día repetido en la misma ruta también se rechaza.
    db.add(RouteDeliveryDay(route_id=route_one.id, driver_id=driver.id, weekday=1))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Otro día de la semana sí está permitido.
    db.add(RouteDeliveryDay(route_id=route_two.id, driver_id=driver.id, weekday=2))
    db.commit()


def test_only_one_in_progress_trip_per_driver_and_truck(db):
    driver_a = _driver("viajero.a@frostbase.local")
    driver_b = _driver("viajero.b@frostbase.local")
    truck_one = _truck("G1-201")
    truck_two = _truck("G1-202")
    db.add_all([driver_a, driver_b, truck_one, truck_two])
    db.flush()

    trip = Trip(driver_id=driver_a.id, truck_id=truck_one.id, state="in_progress")
    db.add(trip)
    db.commit()

    # Segundo viaje en curso del mismo conductor.
    db.add(
        Trip(
            driver_id=driver_a.id,
            truck_id=truck_two.id,
            state="in_progress",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Mismo camión con otro conductor en curso.
    db.add(
        Trip(
            driver_id=driver_b.id,
            truck_id=truck_one.id,
            state="in_progress",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Finalizar el viaje libera conductor y camión.
    trip.state = "completed"
    trip.ended_at = utcnow()
    db.commit()
    db.add(
        Trip(
            driver_id=driver_a.id,
            truck_id=truck_one.id,
            state="in_progress",
        )
    )
    db.commit()


def test_failed_order_requires_reason(db):
    driver = _driver("ordenes@frostbase.local")
    truck = _truck("G1-301")
    db.add_all([driver, truck])
    db.flush()
    trip = Trip(driver_id=driver.id, truck_id=truck.id)
    db.add(trip)
    db.commit()
    trip_id = trip.id

    def _order(reason):
        return TripOrder(
            trip_id=trip_id,
            order_index=0,
            name="Tienda centro",
            latitude=32.53,
            longitude=-117.03,
            state="failed",
            failure_reason=reason,
        )

    # Sin motivo.
    db.add(_order(None))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Motivo solo con espacios.
    db.add(_order("   "))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Motivo de texto libre (decisión G0).
    db.add(_order("Cliente cerrado, no se pudo entregar"))
    db.commit()


def test_door_event_is_idempotent_per_device_and_time(db):
    truck = _truck("G1-401")
    db.add(truck)
    db.flush()
    device = Device(
        device_id="ESP32-G1-001",
        truck_id=truck.id,
        key_hash="irrelevante",
        key_scheme="hmac",
    )
    db.add(device)
    db.flush()

    event_time = datetime.now(UTC) - timedelta(seconds=10)
    db.add(
        DoorEvent(
            device_id=device.id,
            truck_id=truck.id,
            is_open=True,
            event_time=event_time,
        )
    )
    db.commit()

    db.add(
        DoorEvent(
            device_id=device.id,
            truck_id=truck.id,
            is_open=True,
            event_time=event_time,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_alerts_gain_trip_and_acknowledgement(db):
    driver = _driver("alerta@frostbase.local")
    truck = _truck("G1-501")
    db.add_all([driver, truck])
    db.flush()
    device = Device(
        device_id="ESP32-G1-002",
        truck_id=truck.id,
        key_hash="irrelevante",
        key_scheme="hmac",
    )
    db.add(device)
    db.flush()
    trip = Trip(driver_id=driver.id, truck_id=truck.id)
    db.add(trip)
    db.flush()

    alert = Alert(
        truck_id=truck.id,
        device_id=device.id,
        trip_id=trip.id,
        alert_type="puerta",
        message="Apertura no autorizada",
    )
    db.add(alert)
    db.flush()

    alert.acknowledged_at = utcnow()
    alert.acknowledged_by = driver.id
    db.commit()

    assert alert.trip_id == trip.id
    assert alert.acknowledged_by == driver.id


def test_settings_default_door_grace_is_thirty_seconds(db):
    setting = db.get(Setting, 1)
    assert setting is not None
    assert setting.door_open_grace_seconds == 30


def test_truck_threshold_override_is_unique_per_truck(db):
    truck = _truck("G1-601")
    db.add(truck)
    db.flush()

    db.add(
        TruckThresholdOverride(
            truck_id=truck.id,
            temperature_ideal=-4.0,
            temperature_tolerance=2.0,
        )
    )
    db.commit()

    db.add(TruckThresholdOverride(truck_id=truck.id, humidity_ideal=70.0))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
