"""CRUD administrativo de conductores (G3).

Cubre el ciclo completo: alta con y sin contraseña, detalle, edición, baja
lógica con liberación de camión y revocación de sesión, restauración, reset
de contraseña y reglas de asignación de camión.
"""

from datetime import date

import pytest

from app.core.database import SessionLocal
from app.models.driver import DriverTruckAssignment
from app.models.route import Route


def _payload(**overrides) -> dict:
    base = {
        "first_name": "María",
        "last_name": "López",
        "email": "maria.lopez@frostbase.local",
        "phone": "6641234567",
        "birthdate": "1988-07-22",
    }
    base.update(overrides)
    return base


@pytest.fixture
def admin_headers(client, login, csrf_headers):
    assert login().status_code == 200
    return csrf_headers


def test_create_driver_generates_temporary_password(
    client, admin_headers, create_truck
):
    truck_id = create_truck(plate="G3-001")
    response = client.post(
        "/api/v1/drivers",
        json=_payload(truck_id=truck_id),
        headers=admin_headers(),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["temporary_password"]
    assert body["truck"]["id"] == truck_id
    assert body["must_change_password"] is True

    # La contraseña temporal solo aparece en esta respuesta.
    detail = client.get(f"/api/v1/drivers/{body['id']}")
    assert detail.status_code == 200
    assert "temporary_password" not in detail.json()


def test_create_driver_with_password_requires_policy(client, admin_headers):
    weak = client.post(
        "/api/v1/drivers", json=_payload(password="corta"), headers=admin_headers()
    )
    assert weak.status_code == 422

    with_email = client.post(
        "/api/v1/drivers",
        json=_payload(password="Maria.lopez123!"),
        headers=admin_headers(),
    )
    assert with_email.status_code == 422

    ok = client.post(
        "/api/v1/drivers",
        json=_payload(password="Segura123!xyz"),
        headers=admin_headers(),
    )
    assert ok.status_code == 201
    assert ok.json()["temporary_password"] is None


def test_create_driver_validates_age_phone_and_email(client, admin_headers):
    minor = client.post(
        "/api/v1/drivers",
        json=_payload(
            email="menor@frostbase.local", birthdate=date.today().isoformat()
        ),
        headers=admin_headers(),
    )
    assert minor.status_code == 422

    bad_phone = client.post(
        "/api/v1/drivers",
        json=_payload(email="tel@frostbase.local", phone="123"),
        headers=admin_headers(),
    )
    assert bad_phone.status_code == 422

    bad_email = client.post(
        "/api/v1/drivers",
        json=_payload(email="no-es-correo"),
        headers=admin_headers(),
    )
    assert bad_email.status_code == 422


def test_driver_email_cannot_collide_with_admin_or_driver(client, admin_headers):
    import os

    admin_email = os.environ["ADMIN_EMAIL"]
    response = client.post(
        "/api/v1/drivers",
        json=_payload(email=admin_email),
        headers=admin_headers(),
    )
    assert response.status_code == 409
    assert "ya está registrado" in response.json()["detail"]

    created = client.post(
        "/api/v1/drivers",
        json=_payload(email="unico@frostbase.local"),
        headers=admin_headers(),
    )
    assert created.status_code == 201

    duplicate = client.post(
        "/api/v1/drivers",
        json=_payload(email="UNICO@frostbase.local"),
        headers=admin_headers(),
    )
    assert duplicate.status_code == 409


def test_list_search_and_filters(client, admin_headers):
    created = client.post("/api/v1/drivers", json=_payload(), headers=admin_headers())
    assert created.status_code == 201

    listed = client.get("/api/v1/drivers?search=maría")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    inactive_only = client.get("/api/v1/drivers?active=false")
    assert inactive_only.status_code == 200
    assert inactive_only.json()["total"] == 0

    all_rows = client.get("/api/v1/drivers?active=all")
    assert all_rows.json()["total"] >= 1

    without_truck = client.get("/api/v1/drivers?has_truck=false")
    assert without_truck.json()["total"] >= 1

    with_truck = client.get("/api/v1/drivers?has_truck=true")
    assert with_truck.json()["total"] == 0


def test_update_driver_and_email_rotation_revokes_sessions(
    client, login, csrf_headers, create_driver
):
    assert login().status_code == 200
    driver_id, email, password = create_driver(email="editar@frostbase.local")
    driver_login = client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": password}
    )
    assert driver_login.status_code == 200

    assert login().status_code == 200
    updated = client.patch(
        f"/api/v1/drivers/{driver_id}",
        json={"phone": "6649990000", "email": "nuevo.correo@frostbase.local"},
        headers=csrf_headers(),
    )
    assert updated.status_code == 200
    assert updated.json()["email"] == "nuevo.correo@frostbase.local"

    # El correo anterior ya no existe como acceso y el nuevo sí funciona.
    old_login = client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": password}
    )
    assert old_login.status_code == 401
    relogin = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": "nuevo.correo@frostbase.local",
            "password": password,
        },
    )
    assert relogin.status_code == 200


def test_deactivate_driver_releases_truck_and_revokes_session(
    client, login, csrf_headers, create_driver, create_truck
):
    assert login().status_code == 200
    driver_id, email, password = create_driver(email="baja@frostbase.local")
    truck_id = create_truck(plate="G3-002")
    assigned = client.put(
        f"/api/v1/drivers/{driver_id}/truck",
        json={"truck_id": truck_id},
        headers=csrf_headers(),
    )
    assert assigned.status_code == 200

    assert (
        client.post(
            "/api/v1/auth/login", json={"identifier": email, "password": password}
        ).status_code
        == 200
    )

    assert login().status_code == 200
    deactivated = client.delete(f"/api/v1/drivers/{driver_id}", headers=csrf_headers())
    assert deactivated.status_code == 200
    assert deactivated.json()["id"] == driver_id

    # La sesión del conductor murió y el camión quedó liberado.
    blocked = client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": password}
    )
    assert blocked.status_code == 401
    with SessionLocal() as db:
        active = (
            db.query(DriverTruckAssignment)
            .filter_by(driver_id=driver_id, unassigned_at=None)
            .count()
        )
        assert active == 0

    # El correo sigue reservado aunque el conductor esté inactivo.
    duplicate = client.post(
        "/api/v1/drivers", json=_payload(email=email), headers=csrf_headers()
    )
    assert duplicate.status_code == 409

    # Tras restaurar, el conductor vuelve a poder iniciar sesión.
    restored = client.post(
        f"/api/v1/drivers/{driver_id}/restore", headers=csrf_headers()
    )
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True
    assert (
        client.post(
            "/api/v1/auth/login", json={"identifier": email, "password": password}
        ).status_code
        == 200
    )


def test_deactivate_reports_affected_routes(client, admin_headers, create_driver):
    driver_id, email, _ = create_driver(email="rutas@frostbase.local")
    with SessionLocal() as db:
        db.add(Route(name="Ruta del conductor", assigned_driver_id=driver_id))
        db.commit()

    deactivated = client.delete(f"/api/v1/drivers/{driver_id}", headers=admin_headers())
    assert deactivated.status_code == 200
    assert deactivated.json()["affected_routes"][0]["name"] == "Ruta del conductor"


def test_reset_password_returns_temporary_once(client, admin_headers, create_driver):
    driver_id, email, password = create_driver(email="reset@frostbase.local")
    response = client.post(
        f"/api/v1/drivers/{driver_id}/reset-password", headers=admin_headers()
    )
    assert response.status_code == 200
    temporary = response.json()["temporary_password"]
    assert temporary and temporary != password

    relogin = client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": temporary}
    )
    assert relogin.status_code == 200
    me = client.get("/api/v1/driver/me")
    assert me.json()["must_change_password"] is True


def test_truck_assignment_rules(client, admin_headers, create_driver, create_truck):
    driver_id, _, _ = create_driver(email="asigna@frostbase.local")
    other_id, _, _ = create_driver(email="otro@frostbase.local")
    truck_a = create_truck(plate="G3-A")
    truck_b = create_truck(plate="G3-B")
    maintenance = create_truck(plate="G3-M", status="mantenimiento")

    conflict_maintenance = client.put(
        f"/api/v1/drivers/{driver_id}/truck",
        json={"truck_id": maintenance},
        headers=admin_headers(),
    )
    assert conflict_maintenance.status_code == 422

    assigned = client.put(
        f"/api/v1/drivers/{driver_id}/truck",
        json={"truck_id": truck_a},
        headers=admin_headers(),
    )
    assert assigned.status_code == 200

    # Camión ocupado por otro conductor.
    taken = client.put(
        f"/api/v1/drivers/{other_id}/truck",
        json={"truck_id": truck_a},
        headers=admin_headers(),
    )
    assert taken.status_code == 409

    # Relevo: la asignación anterior se cierra y se abre la nueva.
    reassigned = client.put(
        f"/api/v1/drivers/{driver_id}/truck",
        json={"truck_id": truck_b},
        headers=admin_headers(),
    )
    assert reassigned.status_code == 200
    assert reassigned.json()["truck"]["id"] == truck_b

    removed = client.delete(
        f"/api/v1/drivers/{driver_id}/truck", headers=admin_headers()
    )
    assert removed.status_code == 200
    assert removed.json()["truck"] is None


def test_deactivate_with_active_trip_is_blocked(
    client, admin_headers, create_driver, create_truck
):
    driver_id, email, _ = create_driver(email="enviaje@frostbase.local")
    truck_id = create_truck(plate="G3-T")
    assert (
        client.put(
            f"/api/v1/drivers/{driver_id}/truck",
            json={"truck_id": truck_id},
            headers=admin_headers(),
        ).status_code
        == 200
    )

    from datetime import UTC, datetime

    from app.models.trip import Trip

    with SessionLocal() as db:
        db.add(
            Trip(
                driver_id=driver_id,
                truck_id=truck_id,
                state="in_progress",
                started_at=datetime.now(UTC),
            )
        )
        db.commit()

    denied = client.delete(f"/api/v1/drivers/{driver_id}", headers=admin_headers())
    assert denied.status_code == 409
    assert "viaje en curso" in denied.json()["detail"]


def test_driver_endpoints_require_admin(client, login, csrf_headers, create_driver):
    _, email, password = create_driver(email="solo.conductor@frostbase.local")
    driver_login = client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": password}
    )
    assert driver_login.status_code == 200
    assert driver_login.json()["role"] == "driver"

    assert client.get("/api/v1/drivers").status_code == 403
    assert client.get("/api/v1/drivers/options").status_code == 403
    assert (
        client.post(
            "/api/v1/drivers", json=_payload(), headers=csrf_headers()
        ).status_code
        == 403
    )


def test_driver_options_list_active_with_truck(
    client, admin_headers, create_driver, create_truck
):
    driver_id, _, _ = create_driver(email="opcion@frostbase.local")
    truck_id = create_truck(plate="G3-O")

    empty = client.get("/api/v1/drivers/options")
    assert empty.json() == []

    assert (
        client.put(
            f"/api/v1/drivers/{driver_id}/truck",
            json={"truck_id": truck_id},
            headers=admin_headers(),
        ).status_code
        == 200
    )
    options = client.get("/api/v1/drivers/options")
    assert options.json() == [{"id": driver_id, "label": "Carlos Rivera"}]


def test_driver_trips_history_endpoint(client, admin_headers, create_driver):
    driver_id, _, _ = create_driver(email="historial@frostbase.local")
    response = client.get(f"/api/v1/drivers/{driver_id}/trips")
    assert response.status_code == 200
    assert response.json()["total"] == 0
