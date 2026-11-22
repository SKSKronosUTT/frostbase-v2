"""Portal del conductor en modo consulta (G5).

Valida que un conductor solo ve sus propios datos: contenedor con umbrales
efectivos, rutas propias con calendario, ruta de hoy por zona horaria y
alertas de su camión. Un conductor ajeno recibe ``404`` y el administrador
recibe ``403`` en los endpoints del conductor.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.database import SessionLocal
from app.models.alert import Alert
from app.models.driver import DriverTruckAssignment
from app.models.reading import Reading
from app.models.route import Route, RouteDeliveryDay
from app.services.route_links import today_weekday


def _login(client, email, password):
    return client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": password}
    )


@pytest.fixture
def driver_setup(create_driver, create_truck, create_device):
    """Conductor activo con camión, ruta de hoy, dispositivo y lecturas."""
    driver_id, email, password = create_driver(email="portal@frostbase.local")
    truck_id = create_truck(plate="G5-TRUCK")
    device_pk, _, _ = create_device(truck_id, device_id="ESP32-G5-001")
    with SessionLocal() as db:
        db.add(DriverTruckAssignment(driver_id=driver_id, truck_id=truck_id))
        db.commit()
    return driver_id, email, password, truck_id, device_pk


@pytest.fixture
def driver_session(client, driver_setup):
    _, email, password, _, _ = driver_setup
    response = _login(client, email, password)
    assert response.status_code == 200
    return response.json()


def test_dashboard_without_truck(client, login, csrf_headers, create_driver):
    assert login().status_code == 200
    _, email, password = create_driver(email="sin.truck@frostbase.local")
    assert _login(client, email, password).status_code == 200

    response = client.get("/api/v1/driver/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["truck"] is None
    assert body["today_route"] is None
    assert body["routes"] == []
    assert body["container"]["status"] == "no_data"
    assert body["active_alerts"] == 0


def test_dashboard_with_truck_routes_and_readings(client, driver_session, driver_setup):
    driver_id, _, _, truck_id, device_pk = driver_setup
    today = today_weekday()

    with SessionLocal() as db:
        route = Route(name="Ruta G5 hoy", assigned_driver_id=driver_id, status="activa")
        db.add(route)
        db.flush()
        db.add(RouteDeliveryDay(route_id=route.id, driver_id=driver_id, weekday=today))
        db.add(
            Reading(
                device_id=device_pk,
                truck_id=truck_id,
                temperature=-1.0,
                humidity=78.0,
                latitude=32.51,
                longitude=-117.03,
                received_at=datetime.now(UTC),
                reading_timestamp=datetime.now(UTC),
            )
        )
        db.add(
            Alert(
                truck_id=truck_id,
                alert_type="temperatura",
                message="Temperatura alta",
                started_at=datetime.now(UTC) - timedelta(hours=1),
                status="activa",
            )
        )
        db.commit()

    response = client.get("/api/v1/driver/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["truck"]["id"] == truck_id
    assert body["today_route"]["name"] == "Ruta G5 hoy"
    assert len(body["routes"]) == 1
    assert body["container"]["temperature"] == -1.0
    assert body["container"]["status"] == "ok"
    assert body["active_alerts"] == 1


def test_container_live_uses_effective_thresholds(client, driver_session, driver_setup):
    _, _, _, truck_id, device_pk = driver_setup
    with SessionLocal() as db:
        db.add(
            Reading(
                device_id=device_pk,
                truck_id=truck_id,
                temperature=15.0,
                humidity=50.0,
                received_at=datetime.now(UTC),
                reading_timestamp=datetime.now(UTC),
            )
        )
        db.commit()

    response = client.get("/api/v1/driver/container/live")
    assert response.status_code == 200
    body = response.json()
    assert body["temperature"] == 15.0
    assert body["status"] == "out_of_range"


def test_container_live_without_data(client, driver_session):
    response = client.get("/api/v1/driver/container/live")
    assert response.status_code == 200
    assert response.json()["status"] == "no_data"


def test_routes_list_and_today(client, driver_session, driver_setup):
    driver_id, _, _, _, device_pk = driver_setup
    today = today_weekday()

    with SessionLocal() as db:
        r_today = Route(name="Hoy si", assigned_driver_id=driver_id, status="activa")
        r_other = Route(name="Otro dia", assigned_driver_id=driver_id, status="activa")
        db.add_all([r_today, r_other])
        db.flush()
        db.add(
            RouteDeliveryDay(route_id=r_today.id, driver_id=driver_id, weekday=today)
        )
        db.add(
            RouteDeliveryDay(
                route_id=r_other.id, driver_id=driver_id, weekday=(today + 1) % 7
            )
        )
        db.commit()

    routes = client.get("/api/v1/driver/routes")
    assert routes.status_code == 200
    assert len(routes.json()) == 2

    today_route = client.get("/api/v1/driver/routes/today")
    assert today_route.status_code == 200
    assert today_route.json()["name"] == "Hoy si"


def test_route_detail_only_own_routes(client, driver_session, driver_setup):
    driver_id, _, _, _, device_pk = driver_setup
    with SessionLocal() as db:
        own = Route(name="Mia", assigned_driver_id=driver_id, status="activa")
        other = Route(name="Ajena", status="activa")
        db.add_all([own, other])
        db.commit()

    detail = client.get(f"/api/v1/driver/routes/{own.id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "Mia"

    foreign = client.get(f"/api/v1/driver/routes/{other.id}")
    assert foreign.status_code == 404


def test_alerts_only_own_truck(client, driver_session, driver_setup, create_truck):
    _, _, _, truck_id, device_pk = driver_setup
    other_truck = create_truck(plate="G5-OTHER")
    with SessionLocal() as db:
        db.add(
            Alert(
                truck_id=truck_id,
                alert_type="temperatura",
                message="Alta propia",
                started_at=datetime.now(UTC),
                status="activa",
            )
        )
        db.add(
            Alert(
                truck_id=other_truck,
                alert_type="temperatura",
                message="Alta ajena",
                started_at=datetime.now(UTC),
                status="activa",
            )
        )
        db.commit()

    response = client.get("/api/v1/driver/alerts")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["message"] == "Alta propia"


def test_container_readings_for_chart(client, driver_session, driver_setup):
    _, _, _, truck_id, device_pk = driver_setup
    with SessionLocal() as db:
        for i in range(5):
            db.add(
                Reading(
                    device_id=device_pk,
                    truck_id=truck_id,
                    temperature=2.0 + i * 0.1,
                    humidity=78.0,
                    received_at=datetime.now(UTC) - timedelta(minutes=5 - i),
                    reading_timestamp=datetime.now(UTC) - timedelta(minutes=5 - i),
                )
            )
        db.commit()

    response = client.get("/api/v1/driver/container/readings?limit=10")
    assert response.status_code == 200
    readings = response.json()
    assert len(readings) == 5
    # Orden cronológico (la más antigua primero).
    assert readings[0]["temperature"] <= readings[-1]["temperature"]


def test_admin_cannot_access_driver_portal(client, login, csrf_headers):
    assert login().status_code == 200
    assert client.get("/api/v1/driver/dashboard").status_code == 403
    assert client.get("/api/v1/driver/container/live").status_code == 403
    assert client.get("/api/v1/driver/routes").status_code == 403
    assert client.get("/api/v1/driver/alerts").status_code == 403


def test_driver_portal_requires_session(client):
    assert client.get("/api/v1/driver/dashboard").status_code == 401
    assert client.get("/api/v1/driver/routes").status_code == 401
    assert client.get("/api/v1/driver/alerts").status_code == 401
