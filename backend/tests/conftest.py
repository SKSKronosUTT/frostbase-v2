"""Fixtures de integración contra PostgreSQL real.

Las variables de entorno se fijan **antes** de importar ``app`` porque
``Settings`` se instancia al importar el módulo.
"""

import os
import time
from pathlib import Path

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://frostbase:test-password@localhost:55432/frostbase_test",
)

os.environ.update(
    {
        "DATABASE_URL": TEST_DATABASE_URL,
        "SECRET_KEY": "test-secret-" + "a" * 64,
        "DEVICE_KEY_PEPPER": "test-pepper-" + "b" * 64,
        "ADMIN_USERNAME": "admin",
        "ADMIN_EMAIL": "admin@test.local",
        "ADMIN_PASSWORD": "TestPassword123!",
        "ENVIRONMENT": "development",
        "COOKIE_SECURE": "false",
        "AUTO_CREATE_TABLES": "false",
        "RATE_LIMIT_BACKEND": "memory",
        "DISCONNECT_CHECK_SECONDS": "3600",
        "WEATHER_CACHE_SECONDS": "600",
    }
)

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.ratelimit import reset_rate_limits  # noqa: E402
from app.core.security import clear_device_cache  # noqa: E402
from app.main import app  # noqa: E402
from app.models.truck import Truck  # noqa: E402
from app.schemas.device import DeviceCreate  # noqa: E402
from app.services import auth_service, device_service  # noqa: E402
from app.services.bootstrap import bootstrap_database  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    connection = None
    last_error: OperationalError | None = None
    for _ in range(30):
        try:
            connection = engine.connect()
            break
        except OperationalError as exc:
            last_error = exc
            time.sleep(1)
    if connection is None:
        raise AssertionError(
            "No se pudo conectar a la base de pruebas. "
            "Ejecute: docker compose -f compose.test.yml up -d --wait"
        ) from last_error

    with connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.commit()

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_database():
    with SessionLocal() as db:
        db.execute(
            text(
                "TRUNCATE TABLE admins, alerts, readings, devices, trucks, "
                "delivery_points, routes, settings RESTART IDENTITY CASCADE"
            )
        )
        db.commit()
        bootstrap_database(db)

    reset_rate_limits()
    auth_service.reset_login_throttle()
    clear_device_cache()
    yield


@pytest.fixture
def client(_clean_database):
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def admin_credentials() -> tuple[str, str]:
    return os.environ["ADMIN_USERNAME"], os.environ["ADMIN_PASSWORD"]


@pytest.fixture
def login(client, admin_credentials):
    username, password = admin_credentials

    def _login(identifier: str = username, secret: str = password):
        return client.post(
            "/api/v1/auth/login",
            json={"identifier": identifier, "password": secret},
        )

    return _login


@pytest.fixture
def create_truck():
    def _create(plate: str = "TEST-001", status: str = "disponible") -> int:
        with SessionLocal() as db:
            truck = Truck(
                brand="Test",
                model="T-1",
                year=2024,
                plate=plate,
                status=status,
            )
            db.add(truck)
            db.commit()
            db.refresh(truck)
            return truck.id

    return _create


@pytest.fixture
def create_device():
    def _create(truck_id: int, device_id: str = "ESP32-TEST-001"):
        with SessionLocal() as db:
            created = device_service.create_device(
                db, DeviceCreate(device_id=device_id, truck_id=truck_id)
            )
            db.commit()
            return created.id, created.device_id, created.device_key

    return _create
