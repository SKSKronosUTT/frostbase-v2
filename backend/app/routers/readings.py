from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import execute, fetch_all, fetch_one, get_conn, new_id
from ..responses import ok
from ..schemas import ReadingIn
from ..serializers import reading_dto, truck_dto

router = APIRouter(prefix="/readings", tags=["readings"])


@router.get("")
def list_readings(
    truck_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
    conn=Depends(get_conn),
):
    filters = []
    params = []
    if truck_id:
        filters.append("r.id_truck = %s")
        params.append(truck_id)
    if start:
        filters.append("r.date >= %s")
        params.append(datetime.fromisoformat(start))
    if end:
        filters.append("r.date <= %s")
        params.append(datetime.fromisoformat(end))
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(limit)
    rows = fetch_all(
        conn,
        f"SELECT r.* FROM readings r {where} ORDER BY r.date DESC LIMIT %s",
        params,
    )
    return ok([reading_dto(conn, row) for row in rows])


@router.get("/by-truck")
def readings_by_truck(conn=Depends(get_conn)):
    trucks = fetch_all(
        conn,
        """
        SELECT t.*, s.message AS state_message
        FROM trucks t JOIN state_trucks s ON s.code = t.id_state_truck
        ORDER BY t.license_plate
        """,
    )
    result = []
    for truck in trucks:
        readings = fetch_all(
            conn,
            "SELECT * FROM readings WHERE id_truck = %s ORDER BY date DESC",
            (truck["id"],),
        )
        result.append(
            {
                "truck": truck_dto(conn, truck),
                "readings": [reading_dto(conn, row, include_truck=False) for row in readings],
            }
        )
    return ok(result)


@router.get("/by-truck/{truck_id}")
def readings_for_truck(truck_id: str, conn=Depends(get_conn)):
    rows = fetch_all(
        conn,
        "SELECT * FROM readings WHERE id_truck = %s ORDER BY date DESC",
        (truck_id,),
    )
    return ok([reading_dto(conn, row) for row in rows])


@router.get("/latest")
def latest_readings(conn=Depends(get_conn)):
    rows = fetch_all(
        conn,
        """
        SELECT DISTINCT ON (t.id) t.*, s.message AS state_message, r.id AS reading_id
        FROM trucks t
        JOIN state_trucks s ON s.code = t.id_state_truck
        JOIN readings r ON r.id_truck = t.id
        ORDER BY t.id, r.date DESC
        """,
    )
    result = []
    for row in rows:
        reading = fetch_one(conn, "SELECT * FROM readings WHERE id = %s", (row["reading_id"],))
        result.append(
            {
                "truck": truck_dto(conn, row),
                "reading": reading_dto(conn, reading, include_truck=False),
            }
        )
    return ok(result)


@router.get("/latest/{truck_id}")
def latest_for_truck(truck_id: str, conn=Depends(get_conn)):
    row = fetch_one(
        conn,
        "SELECT * FROM readings WHERE id_truck = %s ORDER BY date DESC LIMIT 1",
        (truck_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="No hay lecturas para este camión")
    return ok(reading_dto(conn, row))


@router.get("/stats")
def reading_stats(
    truck_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    conn=Depends(get_conn),
):
    filters = []
    params = []
    if truck_id:
        filters.append("id_truck = %s")
        params.append(truck_id)
    if start:
        filters.append("date >= %s")
        params.append(datetime.fromisoformat(start))
    if end:
        filters.append("date <= %s")
        params.append(datetime.fromisoformat(end))
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = fetch_all(conn, f"SELECT * FROM readings {where} ORDER BY date", params)
    params_row = fetch_one(conn, "SELECT * FROM parameters WHERE id = 1") or {}
    temps = [float(row["temp"]) for row in rows]
    humidities = [int(row["perc_humidity"]) for row in rows]
    min_temp = float(params_row.get("min_temperature") or -2)
    max_temp = float(params_row.get("max_temperature") or 4)
    min_humidity = int(params_row.get("min_humidity") or 75)
    max_humidity = int(params_row.get("max_humidity") or 85)
    temp_in = sum(1 for value in temps if min_temp <= value <= max_temp)
    humidity_in = sum(1 for value in humidities if min_humidity <= value <= max_humidity)
    return ok(
        {
            "totalReadings": len(rows),
            "temperature": {
                "avg": round(sum(temps) / len(temps), 2) if temps else 0,
                "min": min(temps) if temps else 0,
                "max": max(temps) if temps else 0,
                "inRange": temp_in,
                "outOfRange": len(temps) - temp_in,
            },
            "humidity": {
                "avg": round(sum(humidities) / len(humidities), 1) if humidities else 0,
                "min": min(humidities) if humidities else 0,
                "max": max(humidities) if humidities else 0,
                "inRange": humidity_in,
                "outOfRange": len(humidities) - humidity_in,
            },
            "series": [
                {
                    "date": row["date"].isoformat(),
                    "temp": float(row["temp"]),
                    "humidity": int(row["perc_humidity"]),
                    "truckId": row["id_truck"],
                }
                for row in rows
            ],
        }
    )


@router.get("/truck/{truck_id}")
def readings_for_truck_legacy(truck_id: str, conn=Depends(get_conn)):
    return readings_for_truck(truck_id, conn)


@router.get("/{reading_id}")
def get_reading(reading_id: str, conn=Depends(get_conn)):
    row = fetch_one(conn, "SELECT * FROM readings WHERE id = %s", (reading_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Lectura no encontrada")
    return ok(reading_dto(conn, row))


def _create_reading(payload: ReadingIn, truck_id: str, conn):
    truck = fetch_one(conn, "SELECT * FROM trucks WHERE id = %s", (truck_id,))
    if not truck:
        raise HTTPException(status_code=404, detail="Camión no encontrado")
    reading_id = new_id()
    execute(
        conn,
        """
        INSERT INTO readings(id, date, door_state, temp, perc_humidity, latitude, longitude, id_truck)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            reading_id,
            payload.date or datetime.now(),
            payload.door_state,
            payload.temp,
            payload.humidity,
            payload.latitude,
            payload.longitude,
            truck_id,
        ),
    )
    row = fetch_one(conn, "SELECT * FROM readings WHERE id = %s", (reading_id,))
    return ok(reading_dto(conn, row))


@router.post("")
def create_reading(payload: ReadingIn, conn=Depends(get_conn)):
    if not payload.truck_id:
        raise HTTPException(status_code=400, detail="El ID del camión es obligatorio")
    return _create_reading(payload, payload.truck_id, conn)


@router.post("/truck/{truck_id}")
def create_reading_for_truck(truck_id: str, payload: ReadingIn, conn=Depends(get_conn)):
    return _create_reading(payload, truck_id, conn)
