from app.schemas.dashboard import WeatherOut
from app.services import routing, weather_service


def _truck_payload(plate: str = "API-001") -> dict:
    return {
        "brand": "Test",
        "model": "API",
        "year": 2024,
        "plate": plate,
        "status": "disponible",
    }


def _route_payload(name: str = "Punto A") -> dict:
    return {
        "description": "Ruta de prueba",
        "status": "activa",
        "points": [
            {"name": name, "latitude": 32.5, "longitude": -117.0},
            {"name": "Punto B", "latitude": 32.6, "longitude": -117.1},
        ],
    }


async def _fake_geometry(points):
    return [[point[0], point[1]] for point in points]


def test_trucks_crud(client, login, csrf_headers):
    assert login().status_code == 200
    headers = csrf_headers()

    created = client.post("/api/v1/trucks", json=_truck_payload(), headers=headers)
    assert created.status_code == 201
    truck_id = created.json()["id"]

    detail = client.get(f"/api/v1/trucks/{truck_id}")
    assert detail.status_code == 200
    assert detail.json()["plate"] == "API-001"

    updated = client.put(
        f"/api/v1/trucks/{truck_id}",
        json={"status": "mantenimiento"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "mantenimiento"

    listed = client.get("/api/v1/trucks?search=API")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    deleted = client.delete(f"/api/v1/trucks/{truck_id}", headers=headers)
    assert deleted.status_code == 204


def test_routes_crud(client, login, csrf_headers, monkeypatch):
    assert login().status_code == 200
    headers = csrf_headers()
    monkeypatch.setattr(routing, "calculate_geometry_async", _fake_geometry)

    created = client.post("/api/v1/routes", json=_route_payload(), headers=headers)
    assert created.status_code == 201
    route = created.json()
    route_id = route["id"]
    assert route["geometry_status"] == "ready"
    assert route["geometry"]

    listed = client.get("/api/v1/routes")
    assert listed.status_code == 200

    detail = client.get(f"/api/v1/routes/{route_id}")
    assert detail.status_code == 200

    updated = client.put(
        f"/api/v1/routes/{route_id}",
        json=_route_payload("Punto C"),
        headers=headers,
    )
    assert updated.status_code == 200

    recalculated = client.post(f"/api/v1/routes/{route_id}/calculate", headers=headers)
    assert recalculated.status_code == 200

    truck = client.post(
        "/api/v1/trucks", json=_truck_payload("ROUTE-TRUCK"), headers=headers
    )
    truck_id = truck.json()["id"]
    assigned = client.post(
        f"/api/v1/routes/{route_id}/assign",
        json={"truck_id": truck_id},
        headers=headers,
    )
    assert assigned.status_code == 200

    deleted = client.delete(f"/api/v1/routes/{route_id}", headers=headers)
    assert deleted.status_code == 204


def test_dashboard_endpoints(client, login, create_truck, monkeypatch):
    assert login().status_code == 200
    create_truck(plate="DASH-001")

    summary = client.get("/api/v1/dashboard/summary")
    assert summary.status_code == 200
    assert summary.json()["total_trucks"] >= 1

    trucks = client.get("/api/v1/dashboard/trucks")
    assert trucks.status_code == 200

    alerts = client.get("/api/v1/dashboard/alerts")
    assert alerts.status_code == 200

    async def fake_weather(db):
        return WeatherOut(available=True, city="Tijuana")

    monkeypatch.setattr(weather_service, "get_weather", fake_weather)
    weather = client.get("/api/v1/dashboard/weather")
    assert weather.status_code == 200
    assert weather.json()["available"] is True


def test_route_geometry_async_flag(client, login, csrf_headers, monkeypatch):
    from app.core.config import settings

    assert login().status_code == 200
    headers = csrf_headers()
    monkeypatch.setattr(settings, "route_geometry_async", True)
    monkeypatch.setattr(routing, "calculate_geometry_async", _fake_geometry)

    created = client.post("/api/v1/routes", json=_route_payload(), headers=headers)
    assert created.status_code == 201
    route_id = created.json()["id"]
    assert created.json()["geometry_status"] == "pending"

    detail = client.get(f"/api/v1/routes/{route_id}")
    assert detail.status_code == 200
    assert detail.json()["geometry_status"] in {"ready", "pending"}
