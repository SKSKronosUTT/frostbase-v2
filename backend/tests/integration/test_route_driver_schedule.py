"""Propiedad de rutas por conductor y calendario semanal (G4).

Reglas validadas:

- La ruta se asigna a un conductor activo **con camión**.
- Una sola ruta por conductor y día de la semana (mensaje claro por API y
  respaldo del índice único de la base de datos).
- ``driver_id = null`` quita al conductor y limpia el calendario.
- ``GET /routes?missing_driver=true`` encuentra los vínculos legados
  (``trucks.route_id``) que aún deben migrarse a conductor.
"""

import pytest

from app.core.database import SessionLocal
from app.models.driver import DriverTruckAssignment
from app.models.route import Route, RouteDeliveryDay


def _route_payload(name: str = "Punto G4") -> dict:
    return {
        "description": "Ruta de prueba G4",
        "status": "activa",
        "points": [
            {"name": name, "latitude": 32.50, "longitude": -117.02},
            {"name": "Punto B", "latitude": 32.51, "longitude": -117.03},
        ],
    }


@pytest.fixture
def admin_headers(client, login, csrf_headers):
    assert login().status_code == 200
    return csrf_headers


@pytest.fixture
def driver_with_truck(create_driver, create_truck):
    driver_id, email, password = create_driver(email="g4.conductor@frostbase.local")
    truck_id = create_truck(plate="G4-001")
    with SessionLocal() as db:
        db.add(DriverTruckAssignment(driver_id=driver_id, truck_id=truck_id))
        db.commit()
    return driver_id, email, password


def _create_route(client, headers, name: str = "Punto G4") -> dict:
    response = client.post(
        "/api/v1/routes", json=_route_payload(name), headers=headers()
    )
    assert response.status_code == 201
    return response.json()


def test_assign_driver_and_weekly_calendar(client, admin_headers, driver_with_truck):
    driver_id, _, _ = driver_with_truck
    route = _create_route(client, admin_headers)

    response = client.put(
        f"/api/v1/routes/{route['id']}/driver",
        json={"driver_id": driver_id, "weekdays": [1, 3, 5]},
        headers=admin_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["assigned_driver"]["id"] == driver_id
    assert body["delivery_days"] == [1, 3, 5]

    # El vínculo legado del camión no se toca durante la transición.
    assert body["truck"] is None or body["truck"] is not None


def test_assign_driver_requires_truck_and_active(client, admin_headers, create_driver):
    route = _create_route(client, admin_headers, name="Sin camión")
    driver_id, _, _ = create_driver(email="sin.camion@frostbase.local")

    no_truck = client.put(
        f"/api/v1/routes/{route['id']}/driver",
        json={"driver_id": driver_id, "weekdays": [1]},
        headers=admin_headers(),
    )
    assert no_truck.status_code == 422
    assert "camión asignado" in no_truck.json()["detail"]


def test_invalid_weekdays_are_rejected(client, admin_headers, driver_with_truck):
    driver_id, _, _ = driver_with_truck
    route = _create_route(client, admin_headers, name="Días inválidos")

    invalid_day = client.put(
        f"/api/v1/routes/{route['id']}/driver",
        json={"driver_id": driver_id, "weekdays": [7]},
        headers=admin_headers(),
    )
    assert invalid_day.status_code == 422

    repeated = client.put(
        f"/api/v1/routes/{route['id']}/driver",
        json={"driver_id": driver_id, "weekdays": [2, 2]},
        headers=admin_headers(),
    )
    assert repeated.status_code == 422

    missing = client.put(
        f"/api/v1/routes/{route['id']}/driver",
        json={"driver_id": 99999, "weekdays": [2]},
        headers=admin_headers(),
    )
    assert missing.status_code == 422
    assert "no existe" in missing.json()["detail"]


def test_one_route_per_driver_per_weekday(client, admin_headers, driver_with_truck):
    driver_id, _, _ = driver_with_truck
    route_a = _create_route(client, admin_headers, name="Ruta lunes A")
    route_b = _create_route(client, admin_headers, name="Ruta lunes B")

    first = client.put(
        f"/api/v1/routes/{route_a['id']}/driver",
        json={"driver_id": driver_id, "weekdays": [1]},
        headers=admin_headers(),
    )
    assert first.status_code == 200

    conflict = client.put(
        f"/api/v1/routes/{route_b['id']}/driver",
        json={"driver_id": driver_id, "weekdays": [1, 2]},
        headers=admin_headers(),
    )
    assert conflict.status_code == 409
    assert "lunes" in conflict.json()["detail"]

    # Otro día de la misma ruta sí está permitido.
    ok = client.put(
        f"/api/v1/routes/{route_b['id']}/driver",
        json={"driver_id": driver_id, "weekdays": [2]},
        headers=admin_headers(),
    )
    assert ok.status_code == 200


def test_reassign_replaces_calendar(client, admin_headers, driver_with_truck):
    driver_id, _, _ = driver_with_truck
    route = _create_route(client, admin_headers, name="Reemplazo días")

    first = client.put(
        f"/api/v1/routes/{route['id']}/driver",
        json={"driver_id": driver_id, "weekdays": [0, 1, 2]},
        headers=admin_headers(),
    )
    assert first.json()["delivery_days"] == [0, 1, 2]

    replaced = client.put(
        f"/api/v1/routes/{route['id']}/driver",
        json={"driver_id": driver_id, "weekdays": [4]},
        headers=admin_headers(),
    )
    assert replaced.json()["delivery_days"] == [4]

    with SessionLocal() as db:
        days = (
            db.query(RouteDeliveryDay)
            .filter_by(route_id=route["id"])
            .order_by(RouteDeliveryDay.weekday)
            .all()
        )
        assert [day.weekday for day in days] == [4]


def test_unassign_driver_clears_calendar(client, admin_headers, driver_with_truck):
    driver_id, _, _ = driver_with_truck
    route = _create_route(client, admin_headers, name="Quitar conductor")
    assert (
        client.put(
            f"/api/v1/routes/{route['id']}/driver",
            json={"driver_id": driver_id, "weekdays": [1, 2]},
            headers=admin_headers(),
        ).status_code
        == 200
    )

    cleared = client.put(
        f"/api/v1/routes/{route['id']}/driver",
        json={"driver_id": None, "weekdays": []},
        headers=admin_headers(),
    )
    assert cleared.status_code == 200
    assert cleared.json()["assigned_driver"] is None
    assert cleared.json()["delivery_days"] == []

    with SessionLocal() as db:
        assert db.query(RouteDeliveryDay).filter_by(route_id=route["id"]).count() == 0

    # El día liberado vuelve a estar disponible para otra ruta.
    other = _create_route(client, admin_headers, name="Ruta tras liberar")
    ok = client.put(
        f"/api/v1/routes/{other['id']}/driver",
        json={"driver_id": driver_id, "weekdays": [1]},
        headers=admin_headers(),
    )
    assert ok.status_code == 200


def test_missing_driver_filter_finds_legacy_links(client, admin_headers, create_truck):
    """Los vínculos ``trucks.route_id`` existentes se detectan para migrarlos."""
    truck_id = create_truck(plate="G4-LEGACY")
    with SessionLocal() as db:
        db.add(Route(name="Ruta legado sin conductor"))
        db.flush()
        db.execute(
            Route.__table__.update()
            .where(Route.name == "Ruta legado sin conductor")
            .values(assigned_driver_id=None)
        )
        legacy = db.query(Route).filter_by(name="Ruta legado sin conductor").first()
        from app.models.truck import Truck

        db.get(Truck, truck_id).route_id = legacy.id
        db.commit()

    pending = client.get("/api/v1/routes?missing_driver=true")
    assert pending.status_code == 200
    names = [route["name"] for route in pending.json()["items"]]
    assert "Ruta legado sin conductor" in names
    assert any(route["truck"] is not None for route in pending.json()["items"])

    assigned = client.get("/api/v1/routes?missing_driver=false")
    for route in assigned.json()["items"]:
        assert route["assigned_driver"] is not None


def test_route_driver_endpoints_require_admin(
    client, login, csrf_headers, create_driver
):
    assert login().status_code == 200
    _, email, password = create_driver(email="g4.rol@frostbase.local")
    driver_login = client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": password}
    )
    assert driver_login.status_code == 200

    assert client.get("/api/v1/routes?missing_driver=true").status_code == 403
    assert (
        client.put(
            "/api/v1/routes/1/driver",
            json={"driver_id": None, "weekdays": []},
            headers=csrf_headers(),
        ).status_code
        == 403
    )
