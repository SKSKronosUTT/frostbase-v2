from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.alert import Alert
from app.models.reading import Reading
from app.services import reading_service


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _payload(
    device_id: str,
    *,
    timestamp: datetime | None = None,
    temperature: float = -2.0,
    humidity: float = 80.0,
) -> dict:
    return {
        "device_id": device_id,
        "temperature": temperature,
        "humidity": humidity,
        "latitude": 32.5149,
        "longitude": -117.0382,
        "timestamp": _iso(timestamp or datetime.now(UTC)),
    }


def _count(model) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model)) or 0


def test_ingest_creates_reading_and_alert(client, create_truck, create_device):
    truck_id = create_truck(status="disponible")
    _, device_id, device_key = create_device(truck_id)

    response = client.post(
        "/api/v1/iot/readings",
        headers={"X-Device-Key": device_key},
        json=_payload(device_id, temperature=10.0),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["duplicate"] is False
    assert body["reading_id"] is not None
    assert body["truck_id"] == truck_id
    assert len(body["alerts"]) == 1
    assert body["alerts"][0]["alert_type"] == "temperatura"

    assert _count(Reading) == 1
    assert _count(Alert) == 1


def test_reingest_is_idempotent(client, create_truck, create_device):
    truck_id = create_truck()
    _, device_id, device_key = create_device(truck_id)
    payload = _payload(device_id)

    responses = [
        client.post(
            "/api/v1/iot/readings",
            headers={"X-Device-Key": device_key},
            json=payload,
        )
        for _ in range(5)
    ]

    assert all(response.status_code == 200 for response in responses)
    bodies = [response.json() for response in responses]
    assert bodies[0]["duplicate"] is False
    assert all(body["duplicate"] is True for body in bodies[1:])
    assert len({body["reading_id"] for body in bodies}) == 1
    assert _count(Reading) == 1


def test_timestamp_outside_window_is_rejected(client, create_truck, create_device):
    truck_id = create_truck()
    _, device_id, device_key = create_device(truck_id)

    future = _payload(
        device_id,
        timestamp=datetime.now(UTC) + timedelta(days=365),
    )
    past = _payload(
        device_id,
        timestamp=datetime.now(UTC) - timedelta(days=8),
    )

    assert (
        client.post(
            "/api/v1/iot/readings",
            headers={"X-Device-Key": device_key},
            json=future,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/iot/readings",
            headers={"X-Device-Key": device_key},
            json=past,
        ).status_code
        == 422
    )
    assert _count(Reading) == 0


def test_alert_failure_rolls_back_reading(
    client, create_truck, create_device, monkeypatch
):
    truck_id = create_truck()
    _, device_id, device_key = create_device(truck_id)

    def fail(*args, **kwargs):
        raise RuntimeError("fallo simulado en evaluación de alertas")

    monkeypatch.setattr(reading_service.alert_service, "evaluate_reading", fail)

    response = client.post(
        "/api/v1/iot/readings",
        headers={"X-Device-Key": device_key},
        json=_payload(device_id),
    )

    assert response.status_code == 500
    assert _count(Reading) == 0
    assert _count(Alert) == 0


def test_rotated_key_authenticates_and_old_key_fails(
    client, login, create_truck, create_device, csrf_headers
):
    assert login().status_code == 200
    truck_id = create_truck()
    device_pk, device_id, old_key = create_device(truck_id)

    rotated = client.post(
        f"/api/v1/devices/{device_pk}/rotate-key", headers=csrf_headers()
    )
    assert rotated.status_code == 200
    new_key = rotated.json()["device_key"]
    assert new_key != old_key

    old_response = client.post(
        "/api/v1/iot/readings",
        headers={"X-Device-Key": old_key},
        json=_payload(device_id),
    )
    assert old_response.status_code == 401

    new_response = client.post(
        "/api/v1/iot/readings",
        headers={"X-Device-Key": new_key},
        json=_payload(
            device_id,
            timestamp=datetime.now(UTC) + timedelta(seconds=1),
        ),
    )
    assert new_response.status_code == 200


def test_iot_config_requires_valid_key(client, create_truck, create_device):
    truck_id = create_truck()
    _, device_id, device_key = create_device(truck_id)

    rejected = client.get(
        "/api/v1/iot/config",
        headers={"X-Device-Id": device_id, "X-Device-Key": "clave-incorrecta"},
    )
    assert rejected.status_code == 401

    accepted = client.get(
        "/api/v1/iot/config",
        headers={"X-Device-Id": device_id, "X-Device-Key": device_key},
    )
    assert accepted.status_code == 200
    assert accepted.json()["device_id"] == device_id


def test_csrf_is_required_for_cookie_mutations(
    client, login, create_truck, create_device, csrf_headers
):
    assert login().status_code == 200
    device_pk, _, _ = create_device(create_truck())

    denied = client.post(f"/api/v1/devices/{device_pk}/rotate-key")
    assert denied.status_code == 403
    assert "CSRF" in denied.json()["detail"]

    allowed = client.post(
        f"/api/v1/devices/{device_pk}/rotate-key", headers=csrf_headers()
    )
    assert allowed.status_code == 200


def test_iot_rate_limit_applies_before_hash(client, create_truck, create_device):
    truck_id = create_truck()
    _, device_id, _ = create_device(truck_id)
    payload = _payload(device_id)

    statuses = [
        client.post(
            "/api/v1/iot/readings",
            headers={"X-Device-Key": "clave-incorrecta"},
            json=payload,
        ).status_code
        for _ in range(31)
    ]

    assert statuses[:30] == [401] * 30
    assert statuses[30] == 429
