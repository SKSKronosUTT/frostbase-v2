import statistics
import time

import pytest

from app.core.database import SessionLocal
from app.services import auth_service


def test_login_ok(client, admin_credentials):
    username, password = admin_credentials
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": password},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["admin"]["username"] == username
    assert "frostbase_token" in client.cookies

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == username


def test_login_wrong_password_is_generic(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": "admin", "password": "definitely-wrong"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Usuario o contraseña incorrectos"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_login_rate_limit_returns_429(client):
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            json={"identifier": "admin", "password": "wrong-password"},
        )
        assert response.status_code == 401

    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": "admin", "password": "wrong-password"},
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_login_constant_time_smoke():
    def measure(identifier: str, samples: int = 12) -> float:
        durations: list[float] = []
        for _ in range(samples):
            with SessionLocal() as db:
                started = time.perf_counter()
                with pytest.raises(auth_service.AuthenticationError):
                    auth_service.authenticate(db, identifier, "WrongPassword123!")
                durations.append(time.perf_counter() - started)
        return statistics.median(durations)

    unknown_user = measure("nobody@example.com")
    existing_user = measure("admin")

    # Ambos casos deben ejecutar Argon2 y no diferenciarse de forma evidente.
    assert unknown_user > 0.002
    assert existing_user > 0.002
    ratio = max(unknown_user, existing_user) / min(unknown_user, existing_user)
    assert ratio < 2.0
