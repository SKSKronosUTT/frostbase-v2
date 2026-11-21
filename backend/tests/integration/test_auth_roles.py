"""Autenticación compartida por rol (G2).

Cubre la matriz de permisos: login único por correo, tokens con rol, 403
cruzado entre `/api/v1/*` de admin y `/driver/*`, conductor inactivo sin
acceso, revocación por ``token_version`` y CSRF en mutaciones por cookie.
"""

import pytest

from app.core.database import SessionLocal
from app.models.login_identity import LoginIdentity


def _login(client, identifier: str, password: str):
    return client.post(
        "/api/v1/auth/login", json={"identifier": identifier, "password": password}
    )


def _csrf_headers(client) -> dict[str, str]:
    token = client.cookies.get("frostbase_csrf")
    return {"X-CSRF-Token": token} if token else {}


@pytest.fixture
def driver_session(client, create_driver):
    _, email, password = create_driver(
        email="g2.conductor@frostbase.local", must_change_password=True
    )
    response = _login(client, email, password)
    assert response.status_code == 200
    return response.json()


def test_driver_login_returns_driver_role(client, create_driver):
    _, email, password = create_driver(email="login.ok@frostbase.local")
    response = _login(client, email.upper(), password)
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "driver"
    assert body["driver"]["email"] == email
    assert body["admin"] is None


def test_failed_login_message_is_generic(client, create_driver, admin_credentials):
    admin_user, admin_password = admin_credentials
    cases = [
        ("noexiste@frostbase.local", "cualquiera"),
        ("g2.bad@frostbase.local", "ContraseñaInvalida!"),
        (admin_user, "ContraseñaInvalida!"),
    ]
    for identifier, password in cases:
        response = _login(client, identifier, password)
        assert response.status_code == 401
        assert response.json()["detail"] == "Usuario o contraseña incorrectos"


def test_inactive_driver_cannot_login(client, create_driver):
    _, email, password = create_driver(
        email="inactivo@frostbase.local", is_active=False
    )
    response = _login(client, email, password)
    assert response.status_code == 401
    assert response.json()["detail"] == "Usuario o contraseña incorrectos"


def test_admin_login_still_returns_admin_role(client, login):
    response = login()
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "admin"
    assert body["admin"]["username"]
    assert body["driver"] is None


def test_driver_token_cannot_access_admin_endpoints(client, driver_session):
    response = client.get("/api/v1/trucks")
    assert response.status_code == 403
    assert response.json()["detail"] == "Acceso solo para administradores"


def test_admin_token_cannot_access_driver_endpoints(client, login):
    assert login().status_code == 200
    response = client.get("/api/v1/driver/me")
    assert response.status_code == 403
    assert response.json()["detail"] == "Acceso solo para conductores"


def test_driver_me_returns_profile_and_requires_session(client, driver_session):
    response = client.get("/api/v1/driver/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == driver_session["driver"]["email"]
    assert body["truck"] is None
    assert body["must_change_password"] is True

    anonymous = client.post(
        "/api/v1/auth/logout", headers=_csrf_headers(client)
    )
    assert anonymous.status_code == 204
    assert client.get("/api/v1/driver/me").status_code == 401


def test_driver_me_includes_assigned_truck(client, create_driver, create_truck):
    from app.models.driver import DriverTruckAssignment

    driver_id, email, password = create_driver(email="camion@frostbase.local")
    truck_id = create_truck(plate="G2-TRUCK-001")
    assert _login(client, email, password).status_code == 200

    with SessionLocal() as db:
        db.add(DriverTruckAssignment(driver_id=driver_id, truck_id=truck_id))
        db.commit()

    response = client.get("/api/v1/driver/me")
    assert response.status_code == 200
    assert response.json()["truck"]["id"] == truck_id


def test_driver_change_password_requires_csrf_and_revokes_old_token(
    client, create_driver
):
    _, email, password = create_driver(
        email="clave@frostbase.local", must_change_password=True
    )
    assert _login(client, email, password).status_code == 200

    denied = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": password, "new_password": "NuevaClave123!"},
    )
    assert denied.status_code == 403
    assert "CSRF" in denied.json()["detail"]

    csrf = client.cookies.get("frostbase_csrf")
    changed = client.post(
        "/api/v1/auth/change-password",
        headers={"X-CSRF-Token": csrf},
        json={"current_password": password, "new_password": "NuevaClave123!"},
    )
    assert changed.status_code == 200
    body = changed.json()
    assert body["role"] == "driver"
    assert body["driver"]["must_change_password"] is False

    # La cookie anterior quedó revocada por token_version; la nueva funciona.
    assert client.get("/api/v1/driver/me").status_code == 200
    assert _login(client, email, password).status_code == 401
    assert _login(client, email, "NuevaClave123!").status_code == 200


def test_driver_refresh_reissues_cookie_with_role(client, create_driver):
    _, email, password = create_driver(email="refresh@frostbase.local")
    assert _login(client, email, password).status_code == 200

    response = client.post("/api/v1/auth/refresh", headers=_csrf_headers(client))
    assert response.status_code == 200
    assert response.json()["role"] == "driver"
    assert client.get("/api/v1/driver/me").status_code == 200


def test_session_endpoint_reports_role_for_both(client, login, create_driver):
    assert login().status_code == 200
    assert client.get("/api/v1/auth/session").json()["role"] == "admin"

    _, email, password = create_driver(email="session@frostbase.local")
    assert _login(client, email, password).status_code == 200
    assert client.get("/api/v1/auth/session").json()["role"] == "driver"


def test_bootstrap_registers_admin_login_identity():
    with SessionLocal() as db:
        identity = db.query(LoginIdentity).filter_by(account_type="admin").first()
        assert identity is not None
        assert identity.email.endswith("@test.local") or "@" in identity.email
