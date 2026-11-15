from fastapi import APIRouter, Depends, HTTPException

from ..db import execute, fetch_all, fetch_one, get_conn, new_id
from ..responses import ok
from ..schemas import RouteIn
from ..serializers import order_dto, route_dto

router = APIRouter(prefix="/routes", tags=["routes"])


def _store_rows(conn, route_id: str):
    return fetch_all(
        conn,
        "SELECT * FROM route_stores WHERE route_id = %s ORDER BY sequence",
        (route_id,),
    )


def _replace_stores(conn, route_id: str, stores):
    execute(conn, "DELETE FROM route_stores WHERE route_id = %s", (route_id,))
    for item in stores:
        store = fetch_one(conn, "SELECT id FROM stores WHERE id = %s", (item.store_id,))
        if not store:
            raise HTTPException(status_code=404, detail=f"Tienda {item.store_id} no encontrada")
        execute(
            conn,
            "INSERT INTO route_stores(route_id, store_id, sequence) VALUES (%s, %s, %s)",
            (route_id, item.store_id, item.sequence),
        )


@router.get("")
def list_routes(include_inactive: bool = False, conn=Depends(get_conn)):
    where = "" if include_inactive else "WHERE active = true"
    rows = fetch_all(conn, f"SELECT * FROM routes {where} ORDER BY name")
    return ok([route_dto(conn, row) for row in rows])


@router.get("/today")
def today_routes(conn=Depends(get_conn)):
    rows = fetch_all(
        conn,
        """
        SELECT * FROM routes
        WHERE active = true
          AND EXTRACT(DOW FROM CURRENT_DATE)::int = ANY(deliver_days)
        ORDER BY name
        """,
    )
    return ok([route_dto(conn, row) for row in rows])


@router.get("/days/{day}")
def routes_by_day(day: int, conn=Depends(get_conn)):
    if day < 0 or day > 6:
        raise HTTPException(status_code=400, detail="El día debe estar entre 0 y 6")
    rows = fetch_all(
        conn,
        "SELECT * FROM routes WHERE active = true AND %s = ANY(deliver_days) ORDER BY name",
        (day,),
    )
    return ok([route_dto(conn, row) for row in rows])


@router.get("/{route_id}/pending")
def pending_orders(route_id: str, conn=Depends(get_conn)):
    rows = fetch_all(
        conn,
        """
        SELECT DISTINCT o.* FROM orders o
        JOIN route_stores rs ON rs.store_id = o.id_store
        WHERE rs.route_id = %s AND o.id_state_order IN ('PO', 'LO')
        ORDER BY o.date
        """,
        (route_id,),
    )
    return ok([order_dto(conn, row) for row in rows])


@router.get("/{route_id}")
def get_route(route_id: str, conn=Depends(get_conn)):
    row = fetch_one(conn, "SELECT * FROM routes WHERE id = %s", (route_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    return ok(route_dto(conn, row))


@router.post("")
def create_route(payload: RouteIn, conn=Depends(get_conn)):
    for day in payload.deliver_days:
        if day < 0 or day > 6:
            raise HTTPException(status_code=400, detail="Los días de entrega deben estar entre 0 y 6")
    route_id = new_id()
    execute(
        conn,
        """
        INSERT INTO routes(id, name, deliver_days, id_assigned_user, active)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            route_id,
            payload.name,
            payload.deliver_days,
            payload.id_assigned_user or None,
            payload.active,
        ),
    )
    _replace_stores(conn, route_id, payload.stores)
    row = fetch_one(conn, "SELECT * FROM routes WHERE id = %s", (route_id,))
    return ok(route_dto(conn, row))


@router.put("/{route_id}")
def update_route(route_id: str, payload: RouteIn, conn=Depends(get_conn)):
    existing = fetch_one(conn, "SELECT * FROM routes WHERE id = %s", (route_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    for day in payload.deliver_days:
        if day < 0 or day > 6:
            raise HTTPException(status_code=400, detail="Los días de entrega deben estar entre 0 y 6")
    execute(
        conn,
        """
        UPDATE routes SET name = %s, deliver_days = %s, id_assigned_user = %s,
            active = %s WHERE id = %s
        """,
        (
            payload.name,
            payload.deliver_days,
            payload.id_assigned_user or None,
            payload.active,
            route_id,
        ),
    )
    _replace_stores(conn, route_id, payload.stores)
    row = fetch_one(conn, "SELECT * FROM routes WHERE id = %s", (route_id,))
    return ok(route_dto(conn, row))


@router.delete("/{route_id}")
def delete_route(route_id: str, conn=Depends(get_conn)):
    row = fetch_one(conn, "SELECT * FROM routes WHERE id = %s", (route_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    execute(conn, "UPDATE routes SET active = false WHERE id = %s", (route_id,))
    row["active"] = False
    return ok(route_dto(conn, row))
