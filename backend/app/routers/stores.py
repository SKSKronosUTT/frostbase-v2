from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..db import execute, fetch_all, fetch_one, get_conn, new_id
from ..responses import ok
from ..schemas import StoreIn
from ..serializers import store_dto

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("")
def list_stores(include_inactive: bool = False, search: str | None = None, conn=Depends(get_conn)):
    filters = []
    params = []
    if not include_inactive:
        filters.append("active = true")
    if search:
        filters.append("(name ILIKE %s OR location ILIKE %s OR phone ILIKE %s)")
        term = f"%{search}%"
        params.extend([term, term, term])
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = fetch_all(conn, f"SELECT * FROM stores {where} ORDER BY name", params)
    return ok([store_dto(row) for row in rows])


@router.get("/without-orders")
def stores_without_orders(date: str | None = None, conn=Depends(get_conn)):
    target = datetime.fromisoformat(date) if date else datetime.now()
    rows = fetch_all(
        conn,
        """
        SELECT s.* FROM stores s
        WHERE s.active = true
          AND NOT EXISTS (
              SELECT 1 FROM orders o
              WHERE o.id_store = s.id
                AND o.date::date <= %s::date
                AND coalesce(o.delivered, o.date)::date >= %s::date
          )
        ORDER BY s.name
        """,
        (target, target),
    )
    return ok([store_dto(row) for row in rows])


@router.get("/{store_id}")
def get_store(store_id: str, conn=Depends(get_conn)):
    row = fetch_one(conn, "SELECT * FROM stores WHERE id = %s", (store_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Tienda no encontrada")
    return ok(store_dto(row))


@router.post("")
def create_store(payload: StoreIn, conn=Depends(get_conn)):
    store_id = new_id()
    execute(
        conn,
        """
        INSERT INTO stores(id, name, phone, location, latitude, longitude, active)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            store_id,
            payload.name,
            payload.phone,
            payload.location.address,
            payload.location.latitude,
            payload.location.longitude,
            payload.active,
        ),
    )
    row = fetch_one(conn, "SELECT * FROM stores WHERE id = %s", (store_id,))
    return ok(store_dto(row))


@router.put("/{store_id}")
def update_store(store_id: str, payload: StoreIn, conn=Depends(get_conn)):
    existing = fetch_one(conn, "SELECT * FROM stores WHERE id = %s", (store_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Tienda no encontrada")
    execute(
        conn,
        """
        UPDATE stores SET name = %s, phone = %s, location = %s, latitude = %s,
            longitude = %s, active = %s WHERE id = %s
        """,
        (
            payload.name,
            payload.phone,
            payload.location.address,
            payload.location.latitude,
            payload.location.longitude,
            payload.active,
            store_id,
        ),
    )
    row = fetch_one(conn, "SELECT * FROM stores WHERE id = %s", (store_id,))
    return ok(store_dto(row))


@router.delete("/{store_id}")
def delete_store(store_id: str, conn=Depends(get_conn)):
    row = fetch_one(conn, "SELECT * FROM stores WHERE id = %s", (store_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Tienda no encontrada")
    execute(conn, "UPDATE stores SET active = false WHERE id = %s", (store_id,))
    row["active"] = False
    return ok(store_dto(row))
