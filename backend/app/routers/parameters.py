from fastapi import APIRouter, Depends, HTTPException

from ..db import execute, fetch_one, get_conn
from ..responses import ok
from ..schemas import ParameterIn

router = APIRouter(prefix="/parameters", tags=["parameters"])


def _dto(row):
    return {
        "maxTemperature": float(row["max_temperature"]),
        "minTemperature": float(row["min_temperature"]),
        "maxHumidity": int(row["max_humidity"]),
        "minHumidity": int(row["min_humidity"]),
    }


@router.get("")
def get_parameters(conn=Depends(get_conn)):
    row = fetch_one(conn, "SELECT * FROM parameters WHERE id = 1")
    if not row:
        raise HTTPException(status_code=404, detail="Parámetros no configurados")
    return ok(_dto(row))


@router.put("")
def update_parameters(payload: ParameterIn, conn=Depends(get_conn)):
    if not (0 <= payload.min_humidity <= 100 and 0 <= payload.max_humidity <= 100):
        raise HTTPException(status_code=400, detail="La humedad debe estar entre 0 y 100")
    if payload.min_temperature > payload.max_temperature:
        raise HTTPException(status_code=400, detail="La temperatura mínima no puede superar la máxima")
    if payload.min_humidity > payload.max_humidity:
        raise HTTPException(status_code=400, detail="La humedad mínima no puede superar la máxima")
    execute(
        conn,
        """
        INSERT INTO parameters(id, max_temperature, min_temperature, max_humidity, min_humidity)
        VALUES (1, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            max_temperature = EXCLUDED.max_temperature,
            min_temperature = EXCLUDED.min_temperature,
            max_humidity = EXCLUDED.max_humidity,
            min_humidity = EXCLUDED.min_humidity
        """,
        (
            payload.max_temperature,
            payload.min_temperature,
            payload.max_humidity,
            payload.min_humidity,
        ),
    )
    row = fetch_one(conn, "SELECT * FROM parameters WHERE id = 1")
    return ok(_dto(row))
