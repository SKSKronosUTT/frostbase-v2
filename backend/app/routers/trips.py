import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..db import execute, fetch_all, fetch_one, get_conn, new_id
from ..responses import ok
from ..schemas import TripCreateIn, TripStartIn
from ..serializers import trip_dto

router = APIRouter(prefix="/trips", tags=["trips"])


def _log_trip(conn, trip_id: str, state: str, date: datetime, orders):
    execute(
        conn,
        """
        INSERT INTO trip_logs(id, date, id_trip, id_state_trip, orders)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        """,
        (new_id(), date, trip_id, state, json.dumps(orders, default=str)),
    )


def _set_truck_state(conn, truck_id: str, state: str):
    execute(conn, "UPDATE trucks SET id_state_truck = %s WHERE id = %s", (state, truck_id))
    execute(
        conn,
        "INSERT INTO truck_logs(id, date, id_truck, id_state_truck) VALUES (%s, now(), %s, %s)",
        (new_id(), truck_id, state),
    )


def _validate_refs(conn, truck_id: str, driver_id: str, route_id: str):
    if not fetch_one(conn, "SELECT id FROM trucks WHERE id = %s", (truck_id,)):
        raise HTTPException(status_code=404, detail="Camión no encontrado")
    if not fetch_one(conn, "SELECT id FROM users WHERE id = %s", (driver_id,)):
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    if not fetch_one(conn, "SELECT id FROM routes WHERE id = %s", (route_id,)):
        raise HTTPException(status_code=404, detail="Ruta no encontrada")


@router.get("")
def list_trips(date: str | None = None, conn=Depends(get_conn)):
    params = []
    where = ""
    if date:
        where = "WHERE start_time::date = %s"
        params.append(datetime.fromisoformat(date).date())
    rows = fetch_all(conn, f"SELECT * FROM trips {where} ORDER BY start_time DESC", params)
    return ok([trip_dto(conn, row) for row in rows])


@router.post("")
def create_trip(payload: TripCreateIn, conn=Depends(get_conn)):
    _validate_refs(conn, payload.id_truck, payload.id_driver, payload.id_route)
    trip_id = new_id()
    execute(
        conn,
        """
        INSERT INTO trips(id, start_time, end_time, id_truck, id_user_driver, id_route, id_state_trip)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            trip_id,
            payload.start_time,
            payload.end_time,
            payload.id_truck,
            payload.id_driver,
            payload.id_route,
            payload.id_state,
        ),
    )
    _log_trip(conn, trip_id, payload.id_state, payload.start_time, [])
    if payload.id_state == "IP":
        _set_truck_state(conn, payload.id_truck, "IR")
    row = fetch_one(conn, "SELECT * FROM trips WHERE id = %s", (trip_id,))
    return ok(trip_dto(conn, row))


@router.post("/start")
def start_trip(payload: TripStartIn, conn=Depends(get_conn)):
    _validate_refs(conn, payload.truck_id, payload.driver_id, payload.route_id)
    start = payload.start_date or datetime.now(timezone.utc)
    trip_id = new_id()
    execute(
        conn,
        """
        INSERT INTO trips(id, start_time, id_truck, id_user_driver, id_route, id_state_trip)
        VALUES (%s, %s, %s, %s, %s, 'IP')
        """,
        (trip_id, start, payload.truck_id, payload.driver_id, payload.route_id),
    )
    _log_trip(conn, trip_id, "IP", start, [])
    _set_truck_state(conn, payload.truck_id, "IR")
    row = fetch_one(conn, "SELECT * FROM trips WHERE id = %s", (trip_id,))
    return ok(trip_dto(conn, row))


@router.post("/{trip_id}/end")
def end_trip(trip_id: str, conn=Depends(get_conn)):
    trip = fetch_one(conn, "SELECT * FROM trips WHERE id = %s", (trip_id,))
    if not trip:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    now = datetime.now(timezone.utc)
    execute(
        conn,
        "UPDATE trips SET end_time = %s, id_state_trip = 'CP' WHERE id = %s",
        (now, trip_id),
    )
    trip_orders = fetch_all(conn, "SELECT * FROM trip_orders WHERE trip_id = %s", (trip_id,))
    order_ids = [row["order_id"] for row in trip_orders]
    if order_ids:
        execute(
            conn,
            """
            UPDATE orders SET id_state_order = 'DO', delivered = %s
            WHERE id = ANY(%s)
            """,
            (now, order_ids),
        )
        for order_id in order_ids:
            execute(
                conn,
                "INSERT INTO order_logs(id, date, id_order, id_state_order) VALUES (%s, %s, %s, 'DO')",
                (new_id(), now, order_id),
            )
    _log_trip(
        conn,
        trip_id,
        "CP",
        now,
        [{"orderId": row["order_id"], "startTime": row["start_time"], "endTime": row["end_time"]} for row in trip_orders],
    )
    _set_truck_state(conn, trip["id_truck"], "AV")
    row = fetch_one(conn, "SELECT * FROM trips WHERE id = %s", (trip_id,))
    return ok(trip_dto(conn, row))


@router.post("/{trip_id}/orders/{order_id}/start")
def start_order(trip_id: str, order_id: str, conn=Depends(get_conn)):
    trip = fetch_one(conn, "SELECT * FROM trips WHERE id = %s", (trip_id,))
    if not trip:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    if not fetch_one(conn, "SELECT id FROM orders WHERE id = %s", (order_id,)):
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    existing = fetch_one(
        conn, "SELECT * FROM trip_orders WHERE trip_id = %s AND order_id = %s", (trip_id, order_id)
    )
    now = datetime.now(timezone.utc)
    if existing:
        execute(
            conn,
            "UPDATE trip_orders SET start_time = %s, end_time = NULL WHERE id = %s",
            (now, existing["id"]),
        )
    else:
        sequence = fetch_one(
            conn, "SELECT coalesce(max(sequence), 0) + 1 AS next FROM trip_orders WHERE trip_id = %s", (trip_id,)
        )["next"]
        execute(
            conn,
            """
            INSERT INTO trip_orders(trip_id, order_id, start_time, sequence)
            VALUES (%s, %s, %s, %s)
            """,
            (trip_id, order_id, now, sequence),
        )
    _log_trip(conn, trip_id, trip["id_state_trip"], now, [{"orderId": order_id, "startTime": now}])
    row = fetch_one(conn, "SELECT * FROM trips WHERE id = %s", (trip_id,))
    return ok(trip_dto(conn, row))


@router.post("/{trip_id}/orders/{order_id}/end")
def end_order(trip_id: str, order_id: str, conn=Depends(get_conn)):
    existing = fetch_one(
        conn, "SELECT * FROM trip_orders WHERE trip_id = %s AND order_id = %s", (trip_id, order_id)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="El pedido no forma parte de este viaje")
    now = datetime.now(timezone.utc)
    execute(conn, "UPDATE trip_orders SET end_time = %s WHERE id = %s", (now, existing["id"]))
    row = fetch_one(conn, "SELECT * FROM trips WHERE id = %s", (trip_id,))
    return ok(trip_dto(conn, row))
