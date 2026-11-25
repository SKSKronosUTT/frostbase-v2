"""Nuevas respuestas rápidas del asistente (B4): deterministas y sin cuota."""

from datetime import timedelta

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.ai import AiAudit, AiUsage
from app.models.alert import Alert
from app.models.reading import Reading
from app.models.trip import Trip, TripOrder
from app.models.truck import TruckThresholdOverride
from app.utils.time import utcnow


def _seed_truck(create_truck, create_device, *, plate: str = "QK-001"):
    truck_id = create_truck(plate=plate)
    device_pk, _, _ = create_device(truck_id, device_id=f"ESP32-{plate}")
    now = utcnow()
    with SessionLocal() as db:
        db.add(
            Reading(
                device_id=device_pk,
                truck_id=truck_id,
                temperature=4.0,
                humidity=80.0,
                received_at=now,
                reading_timestamp=now,
            )
        )
        db.add(
            Alert(
                truck_id=truck_id,
                device_id=device_pk,
                alert_type="temperatura",
                status="activa",
                value=4.0,
            )
        )
        db.commit()
    return truck_id, device_pk


def test_quick_list_includes_new_answers(client, login):
    assert login().status_code == 200
    response = client.get("/api/v1/ai/quick")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert {
        "truck-status",
        "truck-thresholds",
        "trips-history",
        "alerts-by-type",
    } <= ids


def test_truck_status_quick_requires_and_reports_truck(
    client, login, csrf_headers, create_truck, create_device
):
    truck_id, _ = _seed_truck(create_truck, create_device)
    assert login().status_code == 200

    missing = client.post("/api/v1/ai/quick/truck-status", headers=csrf_headers())
    assert missing.status_code == 422
    assert "camión" in missing.json()["detail"].lower()

    response = client.post(
        f"/api/v1/ai/quick/truck-status?truck_id={truck_id}",
        headers=csrf_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Estado del camión"
    assert "QK-001" in body["text"]
    assert "fuera de rango" in body["text"]
    assert "4.0 °C" in body["text"]
    assert "temperatura" in body["text"]

    unknown = client.post(
        "/api/v1/ai/quick/truck-status?truck_id=999999",
        headers=csrf_headers(),
    )
    assert unknown.status_code == 404

    with SessionLocal() as db:
        assert db.scalar(select(AiUsage)) is None
        row = db.scalar(
            select(AiAudit).where(AiAudit.action == "quick", AiAudit.status == "ok")
        )
        assert row is not None
        assert row.detail == f"truck-status:{truck_id}"


def test_truck_thresholds_quick_uses_override(
    client, login, csrf_headers, create_truck, create_device
):
    truck_id, _ = _seed_truck(create_truck, create_device, plate="QK-002")
    with SessionLocal() as db:
        db.add(
            TruckThresholdOverride(
                truck_id=truck_id,
                temperature_ideal=0.0,
                temperature_tolerance=1.0,
            )
        )
        db.commit()
    assert login().status_code == 200

    response = client.post(
        f"/api/v1/ai/quick/truck-thresholds?truck_id={truck_id}",
        headers=csrf_headers(),
    )
    assert response.status_code == 200
    text = response.json()["text"]
    assert "QK-002" in text
    assert "-1 a 1 °C" in text
    assert "valores efectivos" in text


def test_trips_history_quick_sanitizes_failure_reason(
    client, login, csrf_headers, create_truck, create_device, create_driver
):
    truck_id, _ = _seed_truck(create_truck, create_device, plate="QK-003")
    driver_id, _, _ = create_driver(email="quick.history@frostbase.local")
    now = utcnow()
    with SessionLocal() as db:
        trip = Trip(
            driver_id=driver_id,
            truck_id=truck_id,
            state="completed",
            started_at=now - timedelta(hours=2),
            ended_at=now - timedelta(hours=1),
        )
        db.add(trip)
        db.flush()
        db.add_all(
            [
                TripOrder(
                    trip_id=trip.id,
                    order_index=0,
                    name="P0",
                    latitude=32.5,
                    longitude=-117.0,
                    state="delivered",
                    delivered_at=now - timedelta(minutes=70),
                ),
                TripOrder(
                    trip_id=trip.id,
                    order_index=1,
                    name="P1",
                    latitude=32.51,
                    longitude=-117.01,
                    state="failed",
                    failure_reason="\u0001 motivo con\nsalto " + "x" * 200,
                ),
            ]
        )
        db.commit()
    assert login().status_code == 200

    response = client.post("/api/v1/ai/quick/trips-history", headers=csrf_headers())
    assert response.status_code == 200
    text = response.json()["text"]
    assert "Historial reciente" in text
    assert "QK-003" in text
    assert "1 fallidas" in text
    assert "Parada 2" in text
    assert "motivo con salto" in text
    assert "\u0001" not in text
    assert "x" * 150 not in text


def test_alerts_by_type_quick_summarizes_active_alerts(
    client, login, csrf_headers, create_truck, create_device
):
    truck_id, device_pk = _seed_truck(create_truck, create_device, plate="QK-004")
    now = utcnow()
    with SessionLocal() as db:
        db.add(
            Alert(
                truck_id=truck_id,
                device_id=device_pk,
                alert_type="desconexion",
                status="activa",
                started_at=now - timedelta(minutes=5),
            )
        )
        db.commit()
    assert login().status_code == 200

    response = client.post("/api/v1/ai/quick/alerts-by-type", headers=csrf_headers())
    assert response.status_code == 200
    text = response.json()["text"]
    assert "Alertas activas por tipo (2)" in text
    assert "temperatura: 1" in text
    assert "desconexion: 1" in text
    assert "QK-004" in text
