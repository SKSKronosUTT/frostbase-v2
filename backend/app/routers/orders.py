from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import execute, fetch_all, fetch_one, get_conn, new_id
from ..responses import ok
from ..schemas import OrderIn, OrderUpdate
from ..serializers import order_dto

router = APIRouter(prefix="/orders", tags=["orders"])


def calculate_deliver_date(conn, store_id: str, base_date: datetime) -> datetime:
    route = fetch_one(
        conn,
        """
        SELECT * FROM routes
        WHERE active = true AND EXISTS (
            SELECT 1 FROM route_stores rs WHERE rs.route_id = routes.id AND rs.store_id = %s
        )
        ORDER BY id LIMIT 1
        """,
        (store_id,),
    )
    deliver_days = route["deliver_days"] if route and route.get("deliver_days") else None
    if not deliver_days:
        return datetime.combine(
            (base_date + timedelta(days=1)).date(), time.min, tzinfo=timezone.utc
        )
    js_day = (base_date.weekday() + 1) % 7
    candidates = sorted(day for day in deliver_days if day >= js_day)
    target_day = candidates[0] if candidates else min(deliver_days)
    cursor = base_date.date() + timedelta(days=1)
    while (cursor.weekday() + 1) % 7 != target_day:
        cursor += timedelta(days=1)
    return datetime.combine(cursor, time.min, tzinfo=timezone.utc)


@router.get("")
def list_orders(
    start: str | None = None,
    end: str | None = None,
    state: str | None = None,
    store_id: str | None = None,
    route_id: str | None = None,
    limit: int = Query(default=250, ge=1, le=2000),
    conn=Depends(get_conn),
):
    filters = []
    params = []
    if start:
        filters.append("o.date >= %s")
        params.append(datetime.fromisoformat(start))
    if end:
        filters.append("o.date < %s")
        end_dt = datetime.fromisoformat(end)
        params.append(end_dt + timedelta(days=1) if len(end) == 10 else end_dt)
    if state:
        filters.append("o.id_state_order = %s")
        params.append(state)
    if store_id:
        filters.append("o.id_store = %s")
        params.append(store_id)
    if route_id:
        filters.append(
            "EXISTS (SELECT 1 FROM route_stores rs WHERE rs.route_id = %s AND rs.store_id = o.id_store)"
        )
        params.append(route_id)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(limit)
    rows = fetch_all(
        conn,
        f"SELECT o.* FROM orders o {where} ORDER BY o.date DESC LIMIT %s",
        params,
    )
    return ok([order_dto(conn, row) for row in rows])


@router.get("/pending")
def pending_orders(conn=Depends(get_conn)):
    rows = fetch_all(
        conn,
        "SELECT * FROM orders WHERE id_state_order IN ('PO', 'LO') ORDER BY date",
    )
    return ok([order_dto(conn, row) for row in rows])


@router.get("/by-route/{route_id}")
def orders_by_route(
    route_id: str,
    pending_only: bool = False,
    conn=Depends(get_conn),
):
    extra = "AND o.id_state_order IN ('PO', 'LO')" if pending_only else ""
    rows = fetch_all(
        conn,
        f"""
        SELECT DISTINCT o.* FROM orders o
        JOIN route_stores rs ON rs.store_id = o.id_store
        WHERE rs.route_id = %s {extra}
        ORDER BY o.date
        """,
        (route_id,),
    )
    return ok([order_dto(conn, row) for row in rows])


@router.get("/{order_id}")
def get_order(order_id: str, conn=Depends(get_conn)):
    row = fetch_one(conn, "SELECT * FROM orders WHERE id = %s", (order_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return ok(order_dto(conn, row))


@router.post("")
def create_order(payload: OrderIn, conn=Depends(get_conn)):
    store = fetch_one(conn, "SELECT * FROM stores WHERE id = %s", (payload.id_store,))
    if not store:
        raise HTTPException(status_code=404, detail="Tienda no encontrada")
    created = payload.date or datetime.now(timezone.utc)
    created_by = payload.id_created_by_user
    if not created_by:
        admin = fetch_one(
            conn,
            "SELECT id FROM users WHERE is_admin = true AND active = true ORDER BY id LIMIT 1",
        )
        created_by = admin["id"] if admin else None
    if not created_by:
        raise HTTPException(status_code=400, detail="No hay usuarios administradores disponibles")
    deliver_date = calculate_deliver_date(conn, payload.id_store, created)
    order_id = new_id()
    execute(
        conn,
        """
        INSERT INTO orders(id, date, delivered, id_created_by_user, id_store, id_state_order)
        VALUES (%s, %s, %s, %s, %s, 'PO')
        """,
        (order_id, created, deliver_date, created_by, payload.id_store),
    )
    execute(
        conn,
        "INSERT INTO order_logs(id, date, id_order, id_state_order) VALUES (%s, %s, %s, 'PO')",
        (new_id(), created, order_id),
    )
    row = fetch_one(conn, "SELECT * FROM orders WHERE id = %s", (order_id,))
    return ok(order_dto(conn, row))


@router.put("/{order_id}")
def update_order(order_id: str, payload: OrderUpdate, conn=Depends(get_conn)):
    existing = fetch_one(conn, "SELECT * FROM orders WHERE id = %s", (order_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("id_state_order") == "DO" and not changes.get("delivered"):
        changes["delivered"] = datetime.now(timezone.utc)
    if not changes:
        return ok(order_dto(conn, existing))
    assignments = [f"{field} = %s" for field in changes]
    values = list(changes.values()) + [order_id]
    execute(conn, f"UPDATE orders SET {', '.join(assignments)} WHERE id = %s", values)
    if changes.get("id_state_order"):
        execute(
            conn,
            "INSERT INTO order_logs(id, date, id_order, id_state_order) VALUES (%s, now(), %s, %s)",
            (new_id(), order_id, changes["id_state_order"]),
        )
    row = fetch_one(conn, "SELECT * FROM orders WHERE id = %s", (order_id,))
    return ok(order_dto(conn, row))


@router.delete("/{order_id}")
def cancel_order(order_id: str, conn=Depends(get_conn)):
    row = fetch_one(conn, "SELECT * FROM orders WHERE id = %s", (order_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    execute(conn, "UPDATE orders SET id_state_order = 'CO' WHERE id = %s", (order_id,))
    execute(
        conn,
        "INSERT INTO order_logs(id, date, id_order, id_state_order) VALUES (%s, now(), %s, 'CO')",
        (new_id(), order_id),
    )
    row = fetch_one(conn, "SELECT * FROM orders WHERE id = %s", (order_id,))
    return ok(order_dto(conn, row))
