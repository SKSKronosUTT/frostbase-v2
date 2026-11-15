from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..db import execute, fetch_all, fetch_one, get_conn, new_id
from ..responses import ok
from ..schemas import AlertIn, AlertUpdate
from ..serializers import alert_dto, state_dto

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    truck_id: str | None = None,
    state: bool | None = None,
    limit: int = 250,
    conn=Depends(get_conn),
):
    filters = []
    params = []
    if truck_id:
        filters.append(
            "EXISTS (SELECT 1 FROM readings r WHERE r.id = a.id_reading AND r.id_truck = %s)"
        )
        params.append(truck_id)
    if state is not None:
        filters.append("a.state = %s")
        params.append(state)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(limit)
    rows = fetch_all(
        conn,
        f"SELECT a.* FROM alerts a {where} ORDER BY a.date DESC LIMIT %s",
        params,
    )
    return ok([alert_dto(conn, row) for row in rows])


@router.get("/types")
def alert_types(conn=Depends(get_conn)):
    rows = fetch_all(conn, "SELECT * FROM alert_types ORDER BY code")
    return ok([state_dto(row["code"], row["message"]) for row in rows])


@router.get("/{alert_id}")
def get_alert(alert_id: str, conn=Depends(get_conn)):
    row = fetch_one(conn, "SELECT * FROM alerts WHERE id = %s", (alert_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    return ok(alert_dto(conn, row))


@router.post("")
def create_alert(payload: AlertIn, conn=Depends(get_conn)):
    alert_type = fetch_one(
        conn, "SELECT * FROM alert_types WHERE code = %s", (payload.alert_type,)
    )
    if not alert_type:
        raise HTTPException(status_code=400, detail="Tipo de alerta desconocido")
    if payload.reading:
        reading = fetch_one(conn, "SELECT * FROM readings WHERE id = %s", (payload.reading,))
        if not reading:
            raise HTTPException(status_code=404, detail="Lectura no encontrada")
    alert_id = new_id()
    execute(
        conn,
        """
        INSERT INTO alerts(id, date, state, id_reading, id_alert_type)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            alert_id,
            payload.date or datetime.now(),
            payload.state,
            payload.reading or None,
            payload.alert_type,
        ),
    )
    row = fetch_one(conn, "SELECT * FROM alerts WHERE id = %s", (alert_id,))
    return ok(alert_dto(conn, row))


@router.put("/{alert_id}")
def update_alert(alert_id: str, payload: AlertUpdate, conn=Depends(get_conn)):
    existing = fetch_one(conn, "SELECT * FROM alerts WHERE id = %s", (alert_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    changes = payload.model_dump(exclude_unset=True)
    mapping = {"alert_type": "id_alert_type", "reading": "id_reading"}
    if not changes:
        return ok(alert_dto(conn, existing))
    assignments = []
    values = []
    for field, value in changes.items():
        assignments.append(f"{mapping.get(field, field)} = %s")
        values.append(value)
    values.append(alert_id)
    execute(conn, f"UPDATE alerts SET {', '.join(assignments)} WHERE id = %s", values)
    row = fetch_one(conn, "SELECT * FROM alerts WHERE id = %s", (alert_id,))
    return ok(alert_dto(conn, row))


@router.delete("/{alert_id}")
def acknowledge_alert(alert_id: str, conn=Depends(get_conn)):
    row = fetch_one(conn, "SELECT * FROM alerts WHERE id = %s", (alert_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    execute(conn, "UPDATE alerts SET state = false WHERE id = %s", (alert_id,))
    row["state"] = False
    return ok(alert_dto(conn, row))
