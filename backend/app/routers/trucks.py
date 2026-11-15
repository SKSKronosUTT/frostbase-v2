from fastapi import APIRouter, Depends, HTTPException

import psycopg

from ..db import execute, fetch_all, fetch_one, get_conn, new_id
from ..responses import ok
from ..schemas import TruckIn
from ..serializers import state_dto, truck_dto

router = APIRouter(prefix="/trucks", tags=["trucks"])


@router.get("")
def list_trucks(conn=Depends(get_conn)):
    rows = fetch_all(
        conn,
        """
        SELECT t.*, s.message AS state_message
        FROM trucks t JOIN state_trucks s ON s.code = t.id_state_truck
        ORDER BY t.license_plate
        """,
    )
    return ok([truck_dto(conn, row) for row in rows])


@router.get("/states")
def list_states(conn=Depends(get_conn)):
    rows = fetch_all(conn, "SELECT * FROM state_trucks ORDER BY code")
    return ok([state_dto(row["code"], row["message"]) for row in rows])


@router.get("/{truck_id}")
def get_truck(truck_id: str, conn=Depends(get_conn)):
    row = fetch_one(
        conn,
        """
        SELECT t.*, s.message AS state_message
        FROM trucks t JOIN state_trucks s ON s.code = t.id_state_truck
        WHERE t.id = %s
        """,
        (truck_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Camión no encontrado")
    return ok(truck_dto(conn, row))


@router.post("")
def create_truck(payload: TruckIn, conn=Depends(get_conn)):
    truck_id = new_id()
    try:
        execute(
            conn,
            """
            INSERT INTO trucks(id, brand, model, license_plate, id_state_truck)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (truck_id, payload.brand, payload.model, payload.license_plate, payload.id_state_truck),
        )
    except psycopg.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="La placa ya existe")
    execute(
        conn,
        "INSERT INTO truck_logs(id, date, id_truck, id_state_truck) VALUES (%s, now(), %s, %s)",
        (new_id(), truck_id, payload.id_state_truck),
    )
    row = fetch_one(
        conn,
        """
        SELECT t.*, s.message AS state_message
        FROM trucks t JOIN state_trucks s ON s.code = t.id_state_truck
        WHERE t.id = %s
        """,
        (truck_id,),
    )
    return ok(truck_dto(conn, row))


@router.put("/{truck_id}")
def update_truck(truck_id: str, payload: TruckIn, conn=Depends(get_conn)):
    existing = fetch_one(conn, "SELECT * FROM trucks WHERE id = %s", (truck_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Camión no encontrado")
    try:
        execute(
            conn,
            """
            UPDATE trucks SET brand = %s, model = %s, license_plate = %s,
                id_state_truck = %s WHERE id = %s
            """,
            (
                payload.brand,
                payload.model,
                payload.license_plate,
                payload.id_state_truck,
                truck_id,
            ),
        )
    except psycopg.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="La placa ya existe")
    execute(
        conn,
        "INSERT INTO truck_logs(id, date, id_truck, id_state_truck) VALUES (%s, now(), %s, %s)",
        (new_id(), truck_id, payload.id_state_truck),
    )
    row = fetch_one(
        conn,
        """
        SELECT t.*, s.message AS state_message
        FROM trucks t JOIN state_trucks s ON s.code = t.id_state_truck
        WHERE t.id = %s
        """,
        (truck_id,),
    )
    return ok(truck_dto(conn, row))


@router.delete("/{truck_id}")
def delete_truck(truck_id: str, conn=Depends(get_conn)):
    row = fetch_one(conn, "SELECT * FROM trucks WHERE id = %s", (truck_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Camión no encontrado")
    execute(conn, "UPDATE trucks SET id_state_truck = 'OS' WHERE id = %s", (truck_id,))
    execute(
        conn,
        "INSERT INTO truck_logs(id, date, id_truck, id_state_truck) VALUES (%s, now(), %s, 'OS')",
        (new_id(), truck_id),
    )
    updated = fetch_one(
        conn,
        """
        SELECT t.*, s.message AS state_message
        FROM trucks t JOIN state_trucks s ON s.code = t.id_state_truck
        WHERE t.id = %s
        """,
        (truck_id,),
    )
    return ok(truck_dto(conn, updated))
