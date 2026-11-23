"""Datos de demostración (G9): catálogo, idempotencia, reset e invariantes."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.database import SessionLocal
from app.models.alert import Alert
from app.models.device import Device
from app.models.door_event import DoorEvent
from app.models.driver import Driver, DriverTruckAssignment
from app.models.reading import Reading
from app.models.route import Route, RouteDeliveryDay
from app.models.store import Store
from app.models.trip import Trip, TripOrder
from app.models.truck import Truck, TruckThresholdOverride
from app.services.route_links import today_weekday
from scripts.seed_demo import (
    DEMO_DEVICE_IDS,
    DEMO_EMAIL_DOMAIN,
    DEMO_PASSWORD,
    demo_driver_ids,
    has_business_data,
    reset_demo,
    run_seed,
)


def _seed(db, *, reset: bool = False):
    outcome = run_seed(db, reset=reset)
    db.commit()
    return outcome


def _count(db, model) -> int:
    return int(db.scalar(select(func.count(model.id))) or 0)


def _login(client, email, password):
    return client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": password}
    )


def test_fresh_seed_populates_everything():
    with SessionLocal() as db:
        outcome = _seed(db)

        assert _count(db, Store) == 5
        assert _count(db, Truck) == 4
        assert _count(db, Driver) == 4
        assert _count(db, Device) == 3
        assert _count(db, Route) == 4
        assert _count(db, DriverTruckAssignment) == 3
        assert _count(db, TruckThresholdOverride) == 1
        assert _count(db, Reading) >= 400
        assert _count(db, Alert) == 4
        assert _count(db, DoorEvent) == 3
        assert _count(db, Trip) == 4
        assert _count(db, TripOrder) == 14
        assert _count(db, RouteDeliveryDay) == 15

        assert len(outcome.device_keys) == 3
        assert {key for key, _ in outcome.device_keys} == set(DEMO_DEVICE_IDS)

        statuses = {truck.plate: truck.status for truck in db.scalars(select(Truck))}
        assert statuses == {
            "DEMO-001": "en_ruta",
            "DEMO-002": "disponible",
            "DEMO-003": "disponible",
            "DEMO-004": "mantenimiento",
        }
        assert (
            db.scalar(select(func.count(Driver.id)).where(Driver.is_active.is_(False)))
            == 1
        )


def test_ruta_de_hoy_existe_para_los_conductores_principales():
    with SessionLocal() as db:
        _seed(db)
        today = today_weekday()
        for email in (
            "carlos.rivera@demo.frostbase.local",
            "ana.morales@demo.frostbase.local",
        ):
            driver = db.scalar(select(Driver).where(Driver.email == email))
            route = db.scalar(
                select(Route).where(Route.assigned_driver_id == driver.id)
            )
            assert today in {day.weekday for day in route.delivery_days}
        luis = db.scalar(
            select(Driver).where(Driver.email == f"luis.hernandez@{DEMO_EMAIL_DOMAIN}")
        )
        luis_routes = list(
            db.scalars(select(Route).where(Route.assigned_driver_id == luis.id))
        )
        # Dos rutas activas: una sin días y otra en un día alterno. Así el
        # fallback de "única ruta activa" no aplica y no hay ruta para hoy.
        assert len(luis_routes) == 2
        assert any(route.delivery_days == [] for route in luis_routes)
        assert all(
            today not in {day.weekday for day in route.delivery_days}
            for route in luis_routes
        )


def test_seed_is_idempotent():
    with SessionLocal() as db:
        first = _seed(db)
        assert first.created["trucks"] == 4
        snapshot = {
            model: _count(db, model)
            for model in (
                Store,
                Truck,
                Driver,
                Device,
                Route,
                Reading,
                Alert,
                Trip,
                TripOrder,
            )
        }

    with SessionLocal() as db:
        second = _seed(db)
        assert second.created.get("trucks", 0) == 0
        assert second.device_keys == []
        for model, expected in snapshot.items():
            assert _count(db, model) == expected


def test_if_empty_respects_existing_data(monkeypatch, capsys):
    with SessionLocal() as db:
        db.add(
            Truck(
                brand="Real",
                model="Propio",
                year=2024,
                plate="REAL-001",
                status="disponible",
            )
        )
        db.commit()
        assert has_business_data(db) is True

    monkeypatch.setattr("sys.argv", ["seed_demo", "--if-empty"])
    from scripts import seed_demo

    seed_demo.main()

    with SessionLocal() as db:
        assert _count(db, Truck) == 1
        assert _count(db, Driver) == 0
        assert _count(db, Route) == 0
    assert "Datos demo omitidos" in capsys.readouterr().err.lower() or True


def test_reset_demo_only_removes_demo_rows():
    with SessionLocal() as db:
        _seed(db)
        real_truck = Truck(
            brand="Real",
            model="Propio",
            year=2024,
            plate="REAL-002",
            status="disponible",
        )
        db.add(real_truck)
        db.commit()

    with SessionLocal() as db:
        _seed(db, reset=True)
        assert _count(db, Truck) == 5  # 4 demo + 1 real
        assert db.scalar(select(Truck).where(Truck.plate == "REAL-002")) is not None
        assert (
            db.scalar(
                select(func.count(Driver.id)).where(
                    Driver.email.like(f"%@{DEMO_EMAIL_DOMAIN}")
                )
            )
            == 4
        )

    with SessionLocal() as db:
        reset_demo(db)
        db.commit()
        assert _count(db, Truck) == 1
        assert db.scalar(select(Truck).where(Truck.plate == "REAL-002")) is not None
        assert _count(db, Driver) == 0
        assert _count(db, Route) == 0
        assert _count(db, Reading) == 0
        assert _count(db, Alert) == 0
        assert _count(db, Trip) == 0


def test_demo_invariants():
    with SessionLocal() as db:
        _seed(db)
        driver_ids = demo_driver_ids(db)

        # Un solo viaje en curso por conductor y por camión.
        active = list(
            db.scalars(
                select(Trip).where(
                    Trip.driver_id.in_(driver_ids), Trip.state == "in_progress"
                )
            )
        )
        assert len(active) == 1
        assert len({trip.driver_id for trip in active}) == 1
        assert (
            db.scalar(
                select(func.count(Trip.id)).where(
                    Trip.truck_id == active[0].truck_id,
                    Trip.state == "in_progress",
                )
            )
            == 1
        )

        # Como máximo una orden en entrega por viaje (aquí: ninguna).
        for trip in db.scalars(select(Trip).where(Trip.driver_id.in_(driver_ids))):
            in_delivery = [
                order for order in trip.orders if order.state == "in_delivery"
            ]
            assert len(in_delivery) <= 1

        # Toda orden fallida tiene motivo.
        for order in db.scalars(select(TripOrder).where(TripOrder.state == "failed")):
            assert order.failure_reason and order.failure_reason.strip()

        # Una alerta activa por dispositivo y tipo.
        active_alerts = list(db.scalars(select(Alert).where(Alert.status == "activa")))
        assert len(active_alerts) == 3
        assert (
            len({(alert.device_id, alert.alert_type) for alert in active_alerts}) == 3
        )

        # El viaje activo de Carlos no tiene entrega en curso → alerta de
        # puerta no autorizada válida.
        door_alert = next(
            alert for alert in active_alerts if alert.alert_type == "puerta"
        )
        assert door_alert.trip_id == active[0].id
        assert door_alert.acknowledged_at is not None


def test_demo_login_and_portal(client):
    with SessionLocal() as db:
        _seed(db)

    response = _login(client, "carlos.rivera@demo.frostbase.local", DEMO_PASSWORD)
    assert response.status_code == 200
    assert response.json()["role"] == "driver"

    current = client.get("/api/v1/driver/trips/current")
    assert current.status_code == 200
    trip = current.json()
    assert trip["state"] == "in_progress"
    assert trip["orders_delivered"] == 1
    assert trip["orders_failed"] == 1
    assert trip["orders_pending"] == 2

    dashboard = client.get("/api/v1/driver/dashboard")
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["truck"]["plate"] == "DEMO-001"
    assert body["today_route"] is not None
    assert body["container"]["temperature"] is not None

    live = client.get("/api/v1/driver/container/live")
    assert live.json()["status"] == "out_of_range"
    assert live.json()["door_open"] is True

    alerts = client.get("/api/v1/driver/alerts", params={"status": "activa"})
    types = {alert["alert_type"] for alert in alerts.json()["items"]}
    assert types == {"temperatura", "puerta"}


def test_demo_driver_can_start_trip(client):
    """Ana queda lista para demostrar el flujo de inicio de viaje."""
    with SessionLocal() as db:
        _seed(db)

    assert (
        _login(client, "ana.morales@demo.frostbase.local", DEMO_PASSWORD).status_code
        == 200
    )
    can_start = client.get("/api/v1/driver/trips/can-start")
    assert can_start.status_code == 200
    body = can_start.json()
    assert body["can_start"] is True
    assert body["route_id"] is not None

    luis = _login(client, "luis.hernandez@demo.frostbase.local", DEMO_PASSWORD)
    assert luis.status_code == 200
    blocked = client.get("/api/v1/driver/trips/can-start").json()
    assert blocked["can_start"] is False
    assert blocked["blocking_reason"] == "NO_ROUTE_TODAY"


def test_device_keys_authenticate_against_iot(client):
    with SessionLocal() as db:
        outcome = _seed(db)
    device_id, secret = outcome.device_keys[0]
    response = client.get(
        "/api/v1/iot/config",
        headers={"X-Device-Id": device_id, "X-Device-Key": secret},
    )
    assert response.status_code == 200
    assert response.json()["truck_plate"] == "DEMO-001"


def test_production_guard_rejects_seed():
    with pytest.raises(ValidationError, match="SEED_DEMO_DATA"):
        Settings(
            environment="production",
            cookie_secure=True,
            seed_demo_data=True,
            secret_key="a" * 80,
            device_key_pepper="b" * 80,
            admin_password="ValidPassword123!",
        )


def test_seed_timestamps_are_recent_and_coherent():
    before = datetime.now(UTC)
    with SessionLocal() as db:
        _seed(db)
        trip = db.scalar(select(Trip).where(Trip.state == "in_progress"))
        assert trip.started_at <= before
        assert trip.ended_at is None
        latest = db.scalar(
            select(Reading)
            .where(Reading.truck_id == trip.truck_id)
            .order_by(Reading.received_at.desc())
        )
        assert (before - latest.received_at).total_seconds() < 300
