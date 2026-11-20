def _truck_payload(plate: str = "REUSE-001") -> dict:
    return {
        "brand": "Test",
        "model": "Reuse",
        "year": 2024,
        "plate": plate,
        "status": "disponible",
    }


def test_plate_can_be_reused_after_soft_delete(client, login, csrf_headers):
    assert login().status_code == 200
    headers = csrf_headers()

    created = client.post("/api/v1/trucks", json=_truck_payload(), headers=headers)
    assert created.status_code == 201
    truck_id = created.json()["id"]

    deleted = client.delete(f"/api/v1/trucks/{truck_id}", headers=headers)
    assert deleted.status_code == 204

    reused = client.post("/api/v1/trucks", json=_truck_payload(), headers=headers)
    assert reused.status_code == 201
    assert reused.json()["plate"] == "REUSE-001"


def test_page_above_cap_is_rejected(client, login):
    assert login().status_code == 200
    response = client.get("/api/v1/trucks?page=99999999")
    assert response.status_code == 422
