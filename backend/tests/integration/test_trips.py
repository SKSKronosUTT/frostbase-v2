"""Viajes y entregas (G6A + G6B).

Cubre el ciclo completo: ``can_start_trip`` en cada caso de bloqueo, iniciar
viaje (idempotente), órdenes congeladas desde la ruta, iniciar/entregar/fallar
órdenes, finalizar con y sin pendientes, historial y detalle. Valida que los
recursos ajenos dan ``404`` y que las transiciones escriben bitácora.
"""

import pytest

from app.core.database import SessionLocal
from app.models.driver import DriverTruckAssignment
from app.models.route import Route, RouteDeliveryDay
from app.models.trip import TripLog
from app.services.route_links import today_weekday


def _login(client, email, password):
    return client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": password}
    )


def _csrf(client) -> dict[str, str]:
    token = client.cookies.get("frostbase_csrf")
    return {"X-CSRF-Token": token} if token else {}


@pytest.fixture
def driver_setup(create_driver, create_truck, create_device):
    """Conductor activo con camión, ruta de hoy y puntos de entrega."""
    driver_id, email, password = create_driver(email="viajero@frostbase.local")
    truck_id = create_truck(plate="G6-TRUCK")
    device_pk, _, _ = create_device(truck_id, device_id="ESP32-G6-001")
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


def _create_route_with_points(db, driver_id, today, name="Ruta G6"):
    from app.models.route import DeliveryPoint

    route = Route(name=name, assigned_driver_id=driver_id, status="activa")
    db.add(route)
    db.flush()
    db.add(RouteDeliveryDay(route_id=route.id, driver_id=driver_id, weekday=today))
    for i in range(3):
        db.add(
            DeliveryPoint(
                route_id=route.id,
                name=f"Punto {i + 1}",
                address=f"Dirección {i + 1}",
                latitude=32.5 + i * 0.01,
                longitude=-117.0 - i * 0.01,
                order_index=i,
            )
        )
    db.commit()
    return route.id


def test_can_start_without_truck(client, login, create_driver):
    assert login().status_code == 200
    _, email, password = create_driver(email="sin.camion.g6@frostbase.local")
    assert _login(client, email, password).status_code == 200

    response = client.get("/api/v1/driver/trips/can-start")
    assert response.status_code == 200
    body = response.json()
    assert body["can_start"] is False
    assert body["blocking_reason"] == "NO_TRUCK"


def test_can_start_without_route_today(client, driver_session):
    response = client.get("/api/v1/driver/trips/can-start")
    assert response.status_code == 200
    assert response.json()["blocking_reason"] == "NO_ROUTE_TODAY"


def test_start_trip_creates_orders_from_route(client, driver_session, driver_setup):
    driver_id, _, _, truck_id, _ = driver_setup
    today = today_weekday()

    with SessionLocal() as db:
        route_id = _create_route_with_points(db, driver_id, today)

    can = client.get("/api/v1/driver/trips/can-start")
    assert can.json()["can_start"] is True
    assert can.json()["route_id"] == route_id

    response = client.post(
        "/api/v1/driver/trips/start", json={"route_id": route_id}, headers=_csrf(client)
    )
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "in_progress"
    assert len(body["orders"]) == 3
    assert body["orders"][0]["name"] == "Punto 1"
    assert body["orders"][0]["state"] == "pending"
    assert body["route_name"].startswith("Ruta G6")

    # El camión pasa a en_ruta.
    with SessionLocal() as db:
        from app.models.truck import Truck

        assert db.get(Truck, truck_id).status == "en_ruta"


def test_start_trip_is_idempotent(client, driver_session, driver_setup):
    driver_id, _, _, _, _ = driver_setup
    today = today_weekday()
    with SessionLocal() as db:
        route_id = _create_route_with_points(db, driver_id, today)

    first = client.post(
        "/api/v1/driver/trips/start", json={"route_id": route_id}, headers=_csrf(client)
    )
    assert first.status_code == 201

    # Reintento: devuelve el mismo viaje, no crea otro.
    second = client.post(
        "/api/v1/driver/trips/start", json={"route_id": route_id}, headers=_csrf(client)
    )
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]

    current = client.get("/api/v1/driver/trips/current")
    assert current.json()["id"] == first.json()["id"]


def test_start_trip_with_wrong_route_is_rejected(client, driver_session, driver_setup):
    driver_id, _, _, _, _ = driver_setup
    today = today_weekday()
    # Crear una ruta válida para hoy (necesaria para que can_start pase)
    with SessionLocal() as db:
        _create_route_with_points(db, driver_id, today, "Ruta válida")
        other = Route(name="Ruta ajena", status="activa")
        db.add(other)
        db.commit()

    denied = client.post(
        "/api/v1/driver/trips/start",
        json={"route_id": other.id},
        headers=_csrf(client),
    )
    # 409 porque la ruta ajena no es la de hoy del conductor
    assert denied.status_code in (409, 422)


def test_order_lifecycle_start_deliver(client, driver_session, driver_setup):
    driver_id, _, _, _, _ = driver_setup
    today = today_weekday()
    with SessionLocal() as db:
        route_id = _create_route_with_points(db, driver_id, today)

    trip = client.post(
        "/api/v1/driver/trips/start", json={"route_id": route_id}, headers=_csrf(client)
    )
    trip_id = trip.json()["id"]
    order_id = trip.json()["orders"][0]["id"]

    # Iniciar la entrega
    started = client.post(
        f"/api/v1/driver/trips/{trip_id}/orders/{order_id}/start", headers=_csrf(client)
    )
    assert started.status_code == 200
    assert started.json()["state"] == "in_delivery"

    # Solo una orden en in_delivery a la vez
    other_id = trip.json()["orders"][1]["id"]
    denied = client.post(
        f"/api/v1/driver/trips/{trip_id}/orders/{other_id}/start", headers=_csrf(client)
    )
    assert denied.status_code == 409

    # Entregar
    delivered = client.post(
        f"/api/v1/driver/trips/{trip_id}/orders/{order_id}/deliver",
        headers=_csrf(client),
    )
    assert delivered.status_code == 200
    assert delivered.json()["state"] == "delivered"


def test_order_fail_requires_reason(client, driver_session, driver_setup):
    driver_id, _, _, _, _ = driver_setup
    today = today_weekday()
    with SessionLocal() as db:
        route_id = _create_route_with_points(db, driver_id, today)

    trip = client.post(
        "/api/v1/driver/trips/start", json={"route_id": route_id}, headers=_csrf(client)
    )
    trip_id = trip.json()["id"]
    order_id = trip.json()["orders"][0]["id"]

    denied = client.post(
        f"/api/v1/driver/trips/{trip_id}/orders/{order_id}/fail",
        json={"reason": "   "},
        headers=_csrf(client),
    )
    assert denied.status_code == 422

    failed = client.post(
        f"/api/v1/driver/trips/{trip_id}/orders/{order_id}/fail",
        json={"reason": "Cliente cerrado"},
        headers=_csrf(client),
    )
    assert failed.status_code == 200
    assert failed.json()["state"] == "failed"
    assert failed.json()["failure_reason"] == "Cliente cerrado"


def test_end_trip_with_pending_requires_confirmation(
    client, driver_session, driver_setup
):
    driver_id, _, _, truck_id, _ = driver_setup
    today = today_weekday()
    with SessionLocal() as db:
        route_id = _create_route_with_points(db, driver_id, today)

    trip = client.post(
        "/api/v1/driver/trips/start", json={"route_id": route_id}, headers=_csrf(client)
    )
    trip_id = trip.json()["id"]

    # Intentar finalizar sin confirmar → 409
    denied = client.post(
        f"/api/v1/driver/trips/{trip_id}/end",
        json={},
        headers=_csrf(client),
    )
    assert denied.status_code == 409
    assert "3 orden(es)" in denied.json()["detail"]

    # Confirmar → pendientes pasan a failed
    ended = client.post(
        f"/api/v1/driver/trips/{trip_id}/end",
        json={"confirm_pending": True, "failure_reason": "Sin tiempo"},
        headers=_csrf(client),
    )
    assert ended.status_code == 200
    body = ended.json()
    assert body["state"] == "completed"
    assert body["orders_failed"] == 3
    assert body["orders_pending"] == 0
    assert all(order["failure_reason"] == "Sin tiempo" for order in body["orders"])

    # El camión vuelve a disponible
    with SessionLocal() as db:
        from app.models.truck import Truck

        assert db.get(Truck, truck_id).status == "disponible"


def test_end_trip_all_delivered_no_confirmation_needed(
    client, driver_session, driver_setup
):
    driver_id, _, _, _, _ = driver_setup
    today = today_weekday()
    with SessionLocal() as db:
        route_id = _create_route_with_points(db, driver_id, today)

    trip = client.post(
        "/api/v1/driver/trips/start", json={"route_id": route_id}, headers=_csrf(client)
    )
    trip_id = trip.json()["id"]
    orders = trip.json()["orders"]

    for order in orders:
        client.post(
            f"/api/v1/driver/trips/{trip_id}/orders/{order['id']}/start",
            headers=_csrf(client),
        )
        client.post(
            f"/api/v1/driver/trips/{trip_id}/orders/{order['id']}/deliver",
            headers=_csrf(client),
        )

    ended = client.post(
        f"/api/v1/driver/trips/{trip_id}/end",
        json={},
        headers=_csrf(client),
    )
    assert ended.status_code == 200
    assert ended.json()["orders_delivered"] == 3
    assert ended.json()["orders_failed"] == 0


def test_trip_history_and_detail(client, driver_session, driver_setup):
    driver_id, _, _, _, _ = driver_setup
    today = today_weekday()
    with SessionLocal() as db:
        route_id = _create_route_with_points(db, driver_id, today)

    trip = client.post(
        "/api/v1/driver/trips/start", json={"route_id": route_id}, headers=_csrf(client)
    )
    trip_id = trip.json()["id"]
    client.post(
        f"/api/v1/driver/trips/{trip_id}/end",
        json={"confirm_pending": True},
        headers=_csrf(client),
    )

    history = client.get("/api/v1/driver/trips")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["id"] == trip_id

    detail = client.get(f"/api/v1/driver/trips/{trip_id}")
    assert detail.status_code == 200
    assert detail.json()["route_name"].startswith("Ruta G6")


def test_foreign_trip_gives_404(client, driver_session, driver_setup, create_driver):
    driver_id = driver_setup[0]
    today = today_weekday()
    with SessionLocal() as db:
        route_id = _create_route_with_points(db, driver_id, today)

    # Crear un viaje como el conductor principal
    trip = client.post(
        "/api/v1/driver/trips/start",
        json={"route_id": route_id},
        headers=_csrf(client),
    )
    assert trip.status_code == 201
    trip_id = trip.json()["id"]

    # Iniciar sesión como OTRO conductor
    other_id, other_email, other_pw = create_driver(email="otro.g6@frostbase.local")
    other_login = _login(client, other_email, other_pw)
    assert other_login.status_code == 200

    # El otro conductor pide el viaje del principal → 404
    foreign = client.get(f"/api/v1/driver/trips/{trip_id}")
    assert foreign.status_code == 404


def test_trip_logs_written(client, driver_session, driver_setup):
    driver_id, _, _, _, _ = driver_setup
    today = today_weekday()
    with SessionLocal() as db:
        route_id = _create_route_with_points(db, driver_id, today)

    trip = client.post(
        "/api/v1/driver/trips/start", json={"route_id": route_id}, headers=_csrf(client)
    )
    trip_id = trip.json()["id"]
    order_id = trip.json()["orders"][0]["id"]
    client.post(
        f"/api/v1/driver/trips/{trip_id}/orders/{order_id}/start", headers=_csrf(client)
    )
    client.post(
        f"/api/v1/driver/trips/{trip_id}/orders/{order_id}/deliver",
        headers=_csrf(client),
    )
    client.post(
        f"/api/v1/driver/trips/{trip_id}/end",
        json={"confirm_pending": True},
        headers=_csrf(client),
    )

    with SessionLocal() as db:
        logs = (
            db.query(TripLog)
            .filter_by(trip_id=trip_id)
            .order_by(TripLog.created_at)
            .all()
        )
        events = [log.event for log in logs]
        assert "trip_started" in events
        assert "order_started" in events
        assert "order_delivered" in events
        assert "trip_ended" in events


def test_concurrent_trip_start_creates_only_one(client, driver_setup):
    """G8: dos inicios simultaneos -> una sola fila de viaje.

    Se usa el servicio con dos sesiones de BD independientes y una barrera
    para maximizar la carrera; el indice unico parcial decide el ganador y
    el perdedor devuelve el viaje existente.
    """
    import threading

    from app.models.driver import Driver
    from app.models.route import DeliveryPoint
    from app.services import trip_service

    driver_id, _, _, truck_id, _ = driver_setup
    today = today_weekday()
    with SessionLocal() as db:
        route = Route(
            name="Ruta G8 concurrencia", assigned_driver_id=driver_id, status="activa"
        )
        db.add(route)
        db.flush()
        db.add(RouteDeliveryDay(route_id=route.id, driver_id=driver_id, weekday=today))
        for i in range(2):
            db.add(
                DeliveryPoint(
                    route_id=route.id,
                    name=f"Punto {i}",
                    address=f"Calle {i}",
                    latitude=32.5,
                    longitude=-117.0,
                    order_index=i,
                )
            )
        db.commit()
        route_id = route.id

    barrier = threading.Barrier(2)
    results: list[int] = []
    errors: list[Exception] = []

    def attempt():
        try:
            with SessionLocal() as db:
                driver = db.get(Driver, driver_id)
                barrier.wait(timeout=5)
                trip = trip_service.start_trip(db, driver, route_id)
                db.commit()
                results.append(trip.id)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert not errors, errors
    assert len(results) == 2
    assert len(set(results)) == 1, "Se crearon dos viajes distintos"

    from app.models.trip import Trip

    with SessionLocal() as db:
        trips = db.query(Trip).filter(Trip.driver_id == driver_id).all()
        assert len(trips) == 1
