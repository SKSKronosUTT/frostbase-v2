"""Asignación efectiva camión ↔ ruta derivada del conductor (G4.1).

Valida la regla única: el camión de una ruta es el camión activo de su dueño;
la ruta de un camión es la de hoy (o la única) de su conductor. También cubre
el reporte de conciliación del vínculo legado y la deprecación de los
escritores legados.
"""

import pytest

from app.core.database import SessionLocal
from app.models.route import Route, RouteDeliveryDay
from app.services import route_links


def _route_payload(name: str = "G41 A") -> dict:
    return {
        "description": "Ruta derivada",
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


def _setup(db, *, owner=None, weekdays=(), legacy_truck=None):
    """Crea una ruta con dueño, calendario y vínculo legado opcionales."""
    route = Route(name="Ruta G4.1", status="activa")
    if owner is not None:
        route.assigned_driver_id = owner
    db.add(route)
    db.flush()
    for weekday in weekdays:
        db.add(
            RouteDeliveryDay(route_id=route.id, driver_id=owner or 0, weekday=weekday)
        )
    if legacy_truck is not None:
        legacy_truck.route_id = route.id
        db.add(legacy_truck)
    db.commit()
    return route


def test_effective_truck_follows_owner(
    client, admin_headers, create_driver, create_truck
):
    """Escenario A/B resueltos por construcción."""
    driver_id, _, _ = create_driver(email="efectivo@frostbase.local")
    truck_id = create_truck(plate="G41-T1")

    created = client.post(
        "/api/v1/routes", json=_route_payload(), headers=admin_headers()
    )
    route_id = created.json()["id"]

    # Sin dueño → sin camión aunque exista el legado.
    assert created.json()["truck"] is None

    assigned = client.put(
        f"/api/v1/routes/{route_id}/driver",
        json={"driver_id": driver_id, "weekdays": [1]},
        headers=admin_headers(),
    )
    # Dueño sin camión → la ruta sigue sin camión.
    assert assigned.json()["truck"] is None

    # El conductor recibe un camión → la ruta lo muestra sola.
    truck_assigned = client.put(
        f"/api/v1/drivers/{driver_id}/truck",
        json={"truck_id": truck_id},
        headers=admin_headers(),
    )
    assert truck_assigned.status_code == 200

    detail = client.get(f"/api/v1/routes/{route_id}")
    assert detail.json()["truck"]["id"] == truck_id

    # Y a la inversa: el camión muestra la ruta de su conductor.
    truck_detail = client.get(f"/api/v1/trucks/{truck_id}")
    assert truck_detail.json()["route"]["id"] == route_id


def test_effective_truck_ignores_legacy_link(
    client, admin_headers, create_driver, create_truck
):
    """El legado deja de leerse: dueño con T1, legado T2 → se muestra T1."""
    driver_id, _, _ = create_driver(email="legado@frostbase.local")
    t1 = create_truck(plate="G41-T1")
    t2 = create_truck(plate="G41-T2")
    client.put(
        f"/api/v1/drivers/{driver_id}/truck",
        json={"truck_id": t1},
        headers=admin_headers(),
    )

    created = client.post(
        "/api/v1/routes", json=_route_payload(), headers=admin_headers()
    )
    route_id = created.json()["id"]
    client.put(
        f"/api/v1/routes/{route_id}/driver",
        json={"driver_id": driver_id, "weekdays": [2]},
        headers=admin_headers(),
    )

    # Vínculo legado manual (simula datos históricos).
    from app.models.truck import Truck

    with SessionLocal() as db:
        db.get(Truck, t2).route_id = route_id
        db.commit()

    detail = client.get(f"/api/v1/routes/{route_id}")
    assert detail.json()["truck"]["id"] == t1  # derivado, no el legado

    # El camión legado T2 NO muestra la ruta (no es el del conductor).
    t2_detail = client.get(f"/api/v1/trucks/{t2}")
    assert t2_detail.json()["route"] is None


def test_truck_route_prefers_today_and_single_fallback(
    client, admin_headers, create_driver, create_truck
):
    driver_id, _, _ = create_driver(email="hoy@frostbase.local")
    truck_id = create_truck(plate="G41-H")
    client.put(
        f"/api/v1/drivers/{driver_id}/truck",
        json={"truck_id": truck_id},
        headers=admin_headers(),
    )

    only = client.post(
        "/api/v1/routes", json=_route_payload("Unica"), headers=admin_headers()
    )
    only_id = only.json()["id"]
    client.put(
        f"/api/v1/routes/{only_id}/driver",
        json={"driver_id": driver_id, "weekdays": [3]},
        headers=admin_headers(),
    )
    # Una sola ruta: fallback aunque hoy no sea su día.
    detail = client.get(f"/api/v1/trucks/{truck_id}")
    assert detail.json()["route"]["id"] == only_id

    other = client.post(
        "/api/v1/routes", json=_route_payload("Segunda"), headers=admin_headers()
    )
    other_id = other.json()["id"]
    today = route_links.today_weekday()
    client.put(
        f"/api/v1/routes/{other_id}/driver",
        json={"driver_id": driver_id, "weekdays": [today]},
        headers=admin_headers(),
    )
    # Varias rutas: gana la de hoy.
    detail = client.get(f"/api/v1/trucks/{truck_id}")
    assert detail.json()["route"]["id"] == other_id


def test_legacy_mismatch_report_classifies_all_cases(
    client, admin_headers, create_driver, create_truck
):
    no_owner_id, _, _ = create_driver(email="sin.dueno@frostbase.local")
    owner_id, _, _ = create_driver(email="con.dueno@frostbase.local")
    owner_no_truck_id, _, _ = create_driver(email="dueno.sin.camion@frostbase.local")
    owner_diff_id, _, _ = create_driver(email="dueno.difiere@frostbase.local")
    truck_a = create_truck(plate="G41-RA")
    truck_b = create_truck(plate="G41-RB")
    truck_c = create_truck(plate="G41-RC")
    truck_d = create_truck(plate="G41-RD")

    # Dueños con camión: owner usa A; owner_diff usa D.
    client.put(
        f"/api/v1/drivers/{owner_id}/truck",
        json={"truck_id": truck_a},
        headers=admin_headers(),
    )
    client.put(
        f"/api/v1/drivers/{owner_diff_id}/truck",
        json={"truck_id": truck_d},
        headers=admin_headers(),
    )

    from app.models.truck import Truck

    with SessionLocal() as db:
        r1 = Route(name="Caso sin dueño", status="activa")
        r2 = Route(name="Caso convertible", status="activa")
        r2.assigned_driver_id = owner_no_truck_id
        r3 = Route(name="Caso difiere", status="activa")
        r3.assigned_driver_id = owner_diff_id
        db.add_all([r1, r2, r3])
        db.flush()
        db.get(Truck, truck_b).route_id = r1.id
        db.get(Truck, truck_c).route_id = r2.id
        # r3: legado será el camión C también (ya ocupado) — usar truck_a
        # ligado a r3 no es posible (único por camión), usamos otro camión
        # disponible: creamos uno nuevo para el legado de r3.
        db.commit()

    extra = create_truck(plate="G41-RE")
    with SessionLocal() as db:
        from app.models.truck import Truck as TruckModel

        db.get(TruckModel, extra).route_id = r3.id
        db.commit()

    report = {
        row["route_name"]: row
        for row in client.get("/api/v1/routes/legacy-mismatch").json()
    }

    assert "Caso sin dueño" in report
    assert report["Caso sin dueño"]["case"] == route_links.CASE_NO_OWNER
    assert report["Caso sin dueño"]["legacy_truck"]["plate"] == "G41-RB"

    assert "Caso convertible" in report
    row = report["Caso convertible"]
    assert row["case"] == route_links.CASE_OWNER_WITHOUT_TRUCK
    assert row["convertible"] is True
    assert row["target_driver_id"] == owner_no_truck_id

    assert "Caso difiere" in report
    row = report["Caso difiere"]
    assert row["case"] == route_links.CASE_OWNER_TRUCK_DIFFERS
    assert row["convertible"] is False
    assert row["effective_truck"]["plate"] == "G41-RD"
    assert row["legacy_truck"]["plate"] == "G41-RE"


def test_legacy_assign_endpoint_is_deprecated(client, admin_headers, create_truck):
    truck_id = create_truck(plate="G41-DEP")
    created = client.post(
        "/api/v1/routes", json=_route_payload(), headers=admin_headers()
    )
    route_id = created.json()["id"]

    denied = client.post(
        f"/api/v1/routes/{route_id}/assign",
        json={"truck_id": truck_id},
        headers=admin_headers(),
    )
    assert denied.status_code == 409
    assert "asigne el camión al conductor" in denied.json()["detail"]


def test_truck_update_rejects_route_id(client, admin_headers, create_truck):
    """El formulario de camiones ya no asigna rutas (legado congelado)."""
    truck_id = create_truck(plate="G41-NO")
    denied = client.put(
        f"/api/v1/trucks/{truck_id}",
        json={"route_id": 123},
        headers=admin_headers(),
    )
    assert denied.status_code in (409, 422)
    detail = denied.json()["detail"]
    assert "asigne" in detail.lower() or "no se asigna" in detail.lower()


def test_iot_config_route_is_derived(
    client, admin_headers, create_driver, create_truck, create_device
):
    driver_id, _, _ = create_driver(email="iot.route@frostbase.local")
    truck_id = create_truck(plate="G41-IOT")
    _, device_id, device_key = create_device(truck_id, device_id="ESP32-G41")
    client.put(
        f"/api/v1/drivers/{driver_id}/truck",
        json={"truck_id": truck_id},
        headers=admin_headers(),
    )
    created = client.post(
        "/api/v1/routes", json=_route_payload("IoT"), headers=admin_headers()
    )
    route_id = created.json()["id"]
    client.put(
        f"/api/v1/routes/{route_id}/driver",
        json={"driver_id": driver_id, "weekdays": [route_links.today_weekday()]},
        headers=admin_headers(),
    )

    response = client.get(
        "/api/v1/iot/config",
        headers={"X-Device-Id": device_id, "X-Device-Key": device_key},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["truck_id"] == truck_id
    assert body["route"]["name"].startswith("IoT")
