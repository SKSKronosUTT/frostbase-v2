"""Puerta y alertas (G7).

Cubre la ingesta idempotente de eventos del Reed Switch, el periodo de gracia
configurable, la alerta ``puerta`` solo cuando corresponde (viaje en curso sin
entrega activa), la resolución al cerrar, el estado de puerta en el contenedor
en vivo y el reconocimiento de alertas por el conductor.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.alert import Alert
from app.models.door_event import DoorEvent
from app.models.driver import DriverTruckAssignment
from app.models.route import DeliveryPoint, Route, RouteDeliveryDay
from app.services import door_service, settings_service
from app.services.route_links import today_weekday
from app.utils.time import utcnow


def _login(client, email, password):
    return client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": password}
    )


def _iot_headers(device_key: str) -> dict[str, str]:
    return {"X-Device-Key": device_key}


def _send_door(client, device_id: str, device_key: str, is_open: bool, timestamp=None):
    payload = {"device_id": device_id, "is_open": is_open}
    if timestamp is not None:
        payload["timestamp"] = timestamp
    return client.post(
        "/api/v1/iot/door",
        json=payload,
        headers=_iot_headers(device_key),
    )


@pytest.fixture
def door_setup(create_truck, create_device):
    truck_id = create_truck(plate="G7-TRUCK")
    device_pk, device_id, device_key = create_device(truck_id, device_id="ESP32-G7-01")
    return truck_id, device_pk, device_id, device_key


def _start_trip_for_truck(client, create_driver, truck_id):
    """Conductor con camión, ruta de hoy y viaje iniciado (vía API)."""
    driver_id, email, password = create_driver(
        email=f"portero.g7.{truck_id}@frostbase.local"
    )
    with SessionLocal() as db:
        db.add(DriverTruckAssignment(driver_id=driver_id, truck_id=truck_id))
        route = Route(
            name=f"Ruta G7 {truck_id}",
            assigned_driver_id=driver_id,
            status="activa",
        )
        db.add(route)
        db.flush()
        db.add(
            RouteDeliveryDay(
                route_id=route.id, driver_id=driver_id, weekday=today_weekday()
            )
        )
        db.add(
            DeliveryPoint(
                route_id=route.id,
                name="Punto G7",
                address="Dirección G7",
                latitude=32.50,
                longitude=-117.03,
                order_index=0,
            )
        )
        db.commit()
        route_id = route.id

    # El mismo client reutiliza la sesión del conductor que acaba de iniciar.
    response = _login(client, email, password)
    assert response.status_code == 200
    csrf = {"X-CSRF-Token": client.cookies.get("frostbase_csrf")}
    started = client.post(
        "/api/v1/driver/trips/start", json={"route_id": route_id}, headers=csrf
    )
    assert started.status_code == 201
    trip = started.json()
    return driver_id, email, password, trip


def _expire_grace(db):
    """Deja la gracia en 1 s para no depender del valor por defecto."""
    setting = settings_service.get_settings(db)
    setting.door_open_grace_seconds = 1
    db.add(setting)
    db.commit()
    return setting


# ===== Ingesta =====


def test_door_open_and_close_ingest(client, door_setup):
    _, _, device_id, device_key = door_setup
    opened = _send_door(client, device_id, device_key, is_open=True)
    assert opened.status_code == 200
    body = opened.json()
    assert body["success"] is True
    assert body["door_open"] is True
    assert body["duplicate"] is False
    assert body["event_id"] is not None

    closed = _send_door(client, device_id, device_key, is_open=False)
    assert closed.status_code == 200
    assert closed.json()["door_open"] is False


def test_door_event_is_idempotent(client, door_setup):
    _, _, device_id, device_key = door_setup
    timestamp = utcnow().isoformat()
    first = _send_door(client, device_id, device_key, is_open=True, timestamp=timestamp)
    second = _send_door(
        client, device_id, device_key, is_open=True, timestamp=timestamp
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["event_id"] == first.json()["event_id"]


def test_door_requires_device_key(client, door_setup):
    _, _, device_id, _ = door_setup
    response = client.post(
        "/api/v1/iot/door", json={"device_id": device_id, "is_open": True}
    )
    assert response.status_code == 401


# ===== Periodo de gracia y alerta =====


def test_open_within_grace_does_not_alert(client, door_setup):
    _, _, device_id, device_key = door_setup
    _send_door(client, device_id, device_key, is_open=True)

    with SessionLocal() as db:
        setting = settings_service.get_settings(db)
        created = door_service.evaluate_pending_door_events(db, setting)
        db.commit()
    assert created == 0

    with SessionLocal() as db:
        pending = db.scalar(select(DoorEvent).where(DoorEvent.is_open.is_(True)))
        assert pending is not None
        assert pending.evaluated_at is None


def test_open_after_grace_with_trip_creates_alert(client, door_setup, create_driver):
    truck_id, device_pk, device_id, device_key = door_setup
    driver_id, _, _, trip = _start_trip_for_truck(client, create_driver, truck_id)

    # Evento abierto con timestamp ya vencido (gracia 1 s).
    past = (utcnow() - timedelta(seconds=60)).isoformat()
    _send_door(client, device_id, device_key, is_open=True, timestamp=past)

    with SessionLocal() as db:
        setting = _expire_grace(db)
        created = door_service.evaluate_pending_door_events(db, setting)
        db.commit()
    assert created == 1

    with SessionLocal() as db:
        alert = db.scalar(
            select(Alert).where(Alert.alert_type == "puerta", Alert.status == "activa")
        )
        assert alert is not None
        assert alert.truck_id == truck_id
        assert alert.trip_id == trip["id"]
        assert alert.device_id == device_pk
        event = db.scalar(select(DoorEvent).where(DoorEvent.is_open.is_(True)))
        assert event.evaluated_at is not None
        assert event.alert_id == alert.id


def test_open_with_delivery_in_progress_does_not_alert(
    client, door_setup, create_driver
):
    truck_id, _, device_id, device_key = door_setup
    driver_id, _, _, trip = _start_trip_for_truck(client, create_driver, truck_id)

    # Iniciar la entrega: la apertura es legítima (RF14).
    csrf = {"X-CSRF-Token": client.cookies.get("frostbase_csrf")}
    order_id = trip["orders"][0]["id"]
    started = client.post(
        f"/api/v1/driver/trips/{trip['id']}/orders/{order_id}/start",
        headers=csrf,
    )
    assert started.status_code == 200

    past = (utcnow() - timedelta(seconds=60)).isoformat()
    _send_door(client, device_id, device_key, is_open=True, timestamp=past)

    with SessionLocal() as db:
        setting = _expire_grace(db)
        created = door_service.evaluate_pending_door_events(db, setting)
        db.commit()
    assert created == 0

    with SessionLocal() as db:
        active = db.scalar(
            select(Alert.id).where(
                Alert.alert_type == "puerta", Alert.status == "activa"
            )
        )
        assert active is None
        event = db.scalar(select(DoorEvent).where(DoorEvent.is_open.is_(True)))
        assert event.evaluated_at is not None


def test_open_after_grace_without_trip_does_not_alert(client, door_setup):
    _, _, device_id, device_key = door_setup
    past = (utcnow() - timedelta(seconds=60)).isoformat()
    _send_door(client, device_id, device_key, is_open=True, timestamp=past)

    with SessionLocal() as db:
        setting = _expire_grace(db)
        created = door_service.evaluate_pending_door_events(db, setting)
        db.commit()
    assert created == 0


def test_close_resolves_active_alert(client, door_setup, create_driver):
    truck_id, _, device_id, device_key = door_setup
    _start_trip_for_truck(client, create_driver, truck_id)

    past = (utcnow() - timedelta(seconds=60)).isoformat()
    _send_door(client, device_id, device_key, is_open=True, timestamp=past)
    with SessionLocal() as db:
        setting = _expire_grace(db)
        door_service.evaluate_pending_door_events(db, setting)
        db.commit()

    closed = _send_door(client, device_id, device_key, is_open=False)
    assert closed.status_code == 200

    with SessionLocal() as db:
        alert = db.scalar(
            select(Alert)
            .where(Alert.alert_type == "puerta", Alert.truck_id == truck_id)
            .order_by(Alert.id.desc())
        )
        assert alert is not None
        assert alert.status == "resuelta"
        assert alert.resolved_at is not None


# ===== Portal del conductor =====


def test_container_live_shows_door_state(client, door_setup, create_driver, login):
    assert login().status_code == 200
    truck_id, _, device_id, device_key = door_setup
    driver_id, email, password = create_driver(email="porta.live.g7@frostbase.local")
    with SessionLocal() as db:
        db.add(DriverTruckAssignment(driver_id=driver_id, truck_id=truck_id))
        db.commit()
    assert _login(client, email, password).status_code == 200

    live = client.get("/api/v1/driver/container/live")
    assert live.json()["door_open"] is None

    _send_door(client, device_id, device_key, is_open=True)
    live = client.get("/api/v1/driver/container/live")
    assert live.json()["door_open"] is True
    assert live.json()["door_event_at"] is not None

    _send_door(client, device_id, device_key, is_open=False)
    live = client.get("/api/v1/driver/container/live")
    assert live.json()["door_open"] is False


def test_driver_ack_alert(client, door_setup, create_driver):
    truck_id, _, device_id, device_key = door_setup
    driver_id, email, password = create_driver(email="ack.g7@frostbase.local")
    with SessionLocal() as db:
        db.add(DriverTruckAssignment(driver_id=driver_id, truck_id=truck_id))
        db.commit()
    assert _login(client, email, password).status_code == 200
    csrf = {"X-CSRF-Token": client.cookies.get("frostbase_csrf")}

    # Crear una alerta activa del camión directamente.
    with SessionLocal() as db:
        alert = Alert(
            truck_id=truck_id,
            alert_type="temperatura",
            status="activa",
            message="Prueba",
        )
        db.add(alert)
        db.commit()
        alert_id = alert.id

    acked = client.post(f"/api/v1/driver/alerts/{alert_id}/ack", headers=csrf)
    assert acked.status_code == 200
    assert acked.json()["acknowledged_at"] is not None

    # Idempotente: reconocer de nuevo no cambia nada.
    again = client.post(f"/api/v1/driver/alerts/{alert_id}/ack", headers=csrf)
    assert again.status_code == 200
    assert again.json()["acknowledged_at"] == acked.json()["acknowledged_at"]

    # Alerta inexistente o ajena → 404.
    missing = client.post("/api/v1/driver/alerts/999999/ack", headers=csrf)
    assert missing.status_code == 404


def test_driver_cannot_ack_foreign_alert(
    client, door_setup, create_driver, create_truck
):
    """Alerta de otro camión: el conductor no debe poder reconocerla."""
    my_truck = create_truck(plate="G7-MINE")
    foreign_truck = create_truck(plate="G7-FOREIGN")
    driver_id, email, password = create_driver(email="ajena.g7@frostbase.local")
    with SessionLocal() as db:
        db.add(DriverTruckAssignment(driver_id=driver_id, truck_id=my_truck))
        alert = Alert(
            truck_id=foreign_truck,
            alert_type="puerta",
            status="activa",
        )
        db.add(alert)
        db.commit()
        alert_id = alert.id
    assert _login(client, email, password).status_code == 200
    csrf = {"X-CSRF-Token": client.cookies.get("frostbase_csrf")}

    denied = client.post(f"/api/v1/driver/alerts/{alert_id}/ack", headers=csrf)
    assert denied.status_code == 404
