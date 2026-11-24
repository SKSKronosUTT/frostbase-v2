"""Endpoints de solo lectura para el agente (A2)."""

from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.ai import AiAudit
from app.models.alert import Alert
from app.models.door_event import DoorEvent
from app.models.driver import DriverTruckAssignment
from app.models.reading import Reading
from app.models.route import DeliveryPoint, Route, RouteDeliveryDay
from app.models.trip import Trip, TripOrder
from app.models.truck import Truck, TruckThresholdOverride
from app.services.route_links import today_weekday
from app.utils.time import utcnow

TOKEN = "ro-secret-test"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def read_token(monkeypatch):
    monkeypatch.setattr(settings, "ai_agent_enabled", True)
    monkeypatch.setattr(settings, "ai_agent_read_token", TOKEN)
    return HEADERS


@pytest.fixture
def agent_data(create_truck, create_device, create_driver):
    truck_id = create_truck(plate="AR-001")
    device_pk, _, _ = create_device(truck_id, device_id="ESP32-AR-001")
    driver_id, _, _ = create_driver(email="ar.driver@frostbase.local")
    now = utcnow()
    with SessionLocal() as db:
        db.add(
            Reading(
                device_id=device_pk,
                truck_id=truck_id,
                temperature=-2.0,
                humidity=80.0,
                received_at=now,
                reading_timestamp=now,
            )
        )
        db.add(
            DoorEvent(
                device_id=device_pk,
                truck_id=truck_id,
                is_open=False,
                event_time=now,
                received_at=now,
                evaluated_at=now,
            )
        )
        db.add(
            Alert(
                truck_id=truck_id,
                device_id=device_pk,
                alert_type="temperatura",
                status="activa",
                value=3.5,
                min_value=-5,
                max_value=1,
            )
        )
        db.add(
            Alert(
                truck_id=truck_id,
                device_id=device_pk,
                alert_type="humedad",
                status="resuelta",
                started_at=now - timedelta(hours=1),
                resolved_at=now - timedelta(minutes=30),
            )
        )
        db.add(
            Alert(
                truck_id=truck_id,
                device_id=device_pk,
                alert_type="desconexion",
                status="resuelta",
                started_at=now - timedelta(days=3),
                resolved_at=now - timedelta(days=3),
            )
        )
        db.add(DriverTruckAssignment(driver_id=driver_id, truck_id=truck_id))
        db.add(
            TruckThresholdOverride(
                truck_id=truck_id,
                temperature_ideal=0.0,
                temperature_tolerance=1.0,
            )
        )

        route = Route(name="AR Ruta hoy", assigned_driver_id=driver_id, status="activa")
        db.add(route)
        db.flush()
        db.add(
            RouteDeliveryDay(
                route_id=route.id, driver_id=driver_id, weekday=today_weekday()
            )
        )
        points = [
            DeliveryPoint(
                route_id=route.id,
                name=f"P{i}",
                address=f"Calle {i}",
                latitude=32.5 + i * 0.01,
                longitude=-117.0 - i * 0.01,
                order_index=i,
            )
            for i in range(2)
        ]
        db.add_all(points)
        db.flush()

        trip = Trip(
            driver_id=driver_id,
            truck_id=truck_id,
            route_id=route.id,
            state="in_progress",
            started_at=now - timedelta(hours=1),
        )
        db.add(trip)
        db.flush()
        db.add_all(
            [
                TripOrder(
                    trip_id=trip.id,
                    delivery_point_id=points[0].id,
                    order_index=0,
                    name="P0",
                    latitude=points[0].latitude,
                    longitude=points[0].longitude,
                    state="delivered",
                    delivered_at=now,
                ),
                TripOrder(
                    trip_id=trip.id,
                    delivery_point_id=points[1].id,
                    order_index=1,
                    name="P1",
                    latitude=points[1].latitude,
                    longitude=points[1].longitude,
                    state="pending",
                ),
            ]
        )

        # Ruta en otro día (no debe aparecer en /routes/today)
        other = Route(
            name="AR Ruta otro día", assigned_driver_id=driver_id, status="activa"
        )
        db.add(other)
        db.flush()
        db.add(
            RouteDeliveryDay(
                route_id=other.id,
                driver_id=driver_id,
                weekday=(today_weekday() + 1) % 7,
            )
        )
        db.add(
            DeliveryPoint(
                route_id=other.id,
                name="P otro",
                address="Calle otra",
                latitude=32.6,
                longitude=-117.1,
                order_index=0,
            )
        )

        # Segundo camión sin lecturas
        db.add(
            Truck(
                brand="Isuzu",
                model="NPR",
                year=2021,
                plate="AR-002",
                status="disponible",
            )
        )
        db.commit()
        return {"truck_id": truck_id, "driver_id": driver_id}


def test_requires_read_token(client, read_token, agent_data):
    assert client.get("/api/v1/agent-read/fleet-summary").status_code == 401
    wrong = {"Authorization": "Bearer nope"}
    response = client.get("/api/v1/agent-read/fleet-summary", headers=wrong)
    assert response.status_code == 401


def test_disabled_returns_404(client, monkeypatch, agent_data):
    monkeypatch.setattr(settings, "ai_agent_enabled", False)
    monkeypatch.setattr(settings, "ai_agent_read_token", TOKEN)
    response = client.get("/api/v1/agent-read/fleet-summary", headers=HEADERS)
    assert response.status_code == 404

    monkeypatch.setattr(settings, "ai_agent_enabled", True)
    monkeypatch.setattr(settings, "ai_agent_read_token", "")
    assert (
        client.get("/api/v1/agent-read/fleet-summary", headers=HEADERS).status_code
        == 404
    )


def test_fleet_summary(client, read_token, agent_data):
    response = client.get("/api/v1/agent-read/fleet-summary", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["trucks_total"] == 2
    assert body["alerts_active"] == 1
    assert body["alerts_by_type"] == {"temperatura": 1}
    assert body["alerts_created_today"] == 2
    assert body["alerts_created_today_by_type"] == {
        "temperatura": 1,
        "humedad": 1,
    }
    assert body["alerts_resolved_today"] == 1
    assert body["window_start"].startswith(datetime.now(settings.tz).date().isoformat())
    assert body["trips_active"] == 1
    assert body["pending_orders"] == 1
    assert body["routes_today"] == 1
    assert body["timezone"] == "America/Tijuana"
    assert len(response.content) < 4096


def test_alerts_are_compact_and_without_pii(client, read_token, agent_data):
    response = client.get(
        "/api/v1/agent-read/alerts", params={"limit": 5}, headers=HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["alert_type"] == "temperatura"
    assert item["truck_plate"] == "AR-001"
    assert item["acknowledged"] is False
    assert "@" not in response.text
    assert "664" not in response.text
    assert len(response.content) < 4096


def test_truck_status(client, read_token, agent_data):
    response = client.get(
        f"/api/v1/agent-read/trucks/{agent_data['truck_id']}/status",
        headers=HEADERS,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["plate"] == "AR-001"
    assert body["status"] == "out_of_range"
    assert body["temperature_min"] == -1.0
    assert body["temperature_max"] == 1.0
    assert body["active_alerts"] == ["temperatura"]
    assert body["door_open"] is False

    missing = client.get("/api/v1/agent-read/trucks/999999/status", headers=HEADERS)
    assert missing.status_code == 404


def test_active_trips_use_alias(client, read_token, agent_data):
    response = client.get("/api/v1/agent-read/trips/active", headers=HEADERS)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    trip = items[0]
    assert trip["driver_alias"] == f"Conductor {agent_data['driver_id']}"
    assert trip["truck_plate"] == "AR-001"
    assert trip["orders_total"] == 2
    assert trip["orders_delivered"] == 1
    assert trip["orders_pending"] == 1
    assert "ar.driver" not in response.text


def test_routes_today_and_limit(client, read_token, agent_data):
    response = client.get(
        "/api/v1/agent-read/routes/today", params={"limit": 1}, headers=HEADERS
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "AR Ruta hoy"
    assert items[0]["driver_alias"] == f"Conductor {agent_data['driver_id']}"
    assert items[0]["points"] == 2
    assert items[0]["pending_orders"] == 1


def test_thresholds(client, read_token, agent_data):
    response = client.get("/api/v1/agent-read/thresholds", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["overrides"][0]["plate"] == "AR-001"
    assert body["overrides"][0]["temperature_min"] == -1.0
    assert body["overrides"][0]["temperature_max"] == 1.0


def test_agent_read_is_get_only(client, read_token, agent_data):
    response = client.post("/api/v1/agent-read/fleet-summary", headers=HEADERS)
    assert response.status_code == 405


def test_alerts_today_endpoint(client, read_token, agent_data):
    response = client.get(
        "/api/v1/agent-read/alerts/today", params={"limit": 5}, headers=HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert body["created_total"] == 2
    assert body["resolved_total"] == 1
    assert body["active_total"] == 1
    assert body["created_by_type"] == {"temperatura": 1, "humedad": 1}
    assert body["resolved_by_type"] == {"humedad": 1}
    assert len(body["items"]) == 2
    assert body["items"][0]["status"] in {"activa", "resuelta"}
    assert "@" not in response.text
    assert len(response.content) < 4096


def test_alerts_today_respects_local_midnight(client, read_token):
    now_local = datetime.now(settings.tz)
    start_local = datetime.combine(now_local.date(), time.min, tzinfo=settings.tz)
    elapsed = now_local - start_local
    after = start_local + min(timedelta(minutes=1), elapsed / 2)
    before = start_local - timedelta(minutes=1)
    with SessionLocal() as db:
        db.add(
            Alert(
                alert_type="humedad",
                status="resuelta",
                started_at=before.astimezone(UTC),
                resolved_at=before.astimezone(UTC),
            )
        )
        db.add(
            Alert(
                alert_type="temperatura",
                status="resuelta",
                started_at=after.astimezone(UTC),
                resolved_at=after.astimezone(UTC),
            )
        )
        db.commit()

    response = client.get("/api/v1/agent-read/fleet-summary", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["alerts_created_today"] == 1
    assert body["alerts_resolved_today"] == 1


def test_agent_read_is_audited_for_pull_health(client, read_token, agent_data, login):
    response = client.get("/api/v1/agent-read/fleet-summary", headers=HEADERS)
    assert response.status_code == 200

    with SessionLocal() as db:
        row = db.scalar(select(AiAudit).where(AiAudit.action == "read"))
        assert row is not None
        assert row.admin_id is None
        assert row.status == "ok"
        assert "fleet-summary" in (row.detail or "")
        assert TOKEN not in (row.detail or "")

    assert login().status_code == 200
    status = client.get("/api/v1/ai/status")
    assert status.status_code == 200
    assert status.json()["last_agent_read_at"] is not None
