import random
from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException

from ..db import execute, fetch_all, fetch_one, new_id
from ..serializers import order_dto, trip_dto
from ..routers.orders import calculate_deliver_date


def _target(value):
    return value or date.today()


def generate_orders(conn, target_date=None):
    target = _target(target_date)
    admins = fetch_all(conn, "SELECT * FROM users WHERE is_admin = true AND active = true ORDER BY id")
    if not admins:
        raise HTTPException(status_code=400, detail="No hay usuarios administradores activos")
    stores = fetch_all(
        conn,
        """
        SELECT * FROM stores s WHERE active = true
          AND NOT EXISTS (
              SELECT 1 FROM orders o WHERE o.id_store = s.id AND o.date::date = %s
          )
        ORDER BY s.id
        """,
        (target,),
    )
    if not stores:
        raise HTTPException(status_code=400, detail="Todas las tiendas activas ya tienen un pedido para esta fecha")
    rng = random.Random(target.toordinal())
    created = []
    for index, store in enumerate(stores):
        hour = rng.choice([7, 8, 9, 10, 11, 14, 15, 16, 17])
        order_date = datetime.combine(target, time(hour, index % 60), tzinfo=timezone.utc)
        deliver = calculate_deliver_date(conn, store["id"], order_date)
        order_id = new_id()
        execute(
            conn,
            """
            INSERT INTO orders(id, date, delivered, id_created_by_user, id_store, id_state_order)
            VALUES (%s, %s, %s, %s, %s, 'PO')
            """,
            (
                order_id,
                order_date,
                deliver,
                admins[index % len(admins)]["id"],
                store["id"],
            ),
        )
        execute(
            conn,
            "INSERT INTO order_logs(id, date, id_order, id_state_order) VALUES (%s, %s, %s, 'PO')",
            (new_id(), order_date, order_id),
        )
        created.append(fetch_one(conn, "SELECT * FROM orders WHERE id = %s", (order_id,)))
    return [order_dto(conn, row) for row in created]


def _pending_route_orders(conn, route_id: str, target: date):
    return fetch_all(
        conn,
        """
        SELECT DISTINCT o.* FROM orders o
        JOIN route_stores rs ON rs.store_id = o.id_store
        WHERE rs.route_id = %s
          AND o.id_state_order IN ('PO', 'LO')
          AND o.date::date <= %s
        ORDER BY o.date
        """,
        (route_id, target),
    )


def generate_trips(conn, target_date=None):
    target = _target(target_date)
    day = (target.weekday() + 1) % 7
    routes = fetch_all(
        conn,
        "SELECT * FROM routes WHERE active = true AND %s = ANY(deliver_days) ORDER BY name",
        (day,),
    )
    if not routes:
        raise HTTPException(status_code=400, detail="No hay rutas activas programadas para este día")
    created = []
    rng = random.Random(target.toordinal() + 99)
    for route in routes:
        existing = fetch_one(
            conn, "SELECT id FROM trips WHERE id_route = %s AND start_time::date = %s", (route["id"], target)
        )
        if existing:
            continue
        driver = fetch_one(conn, "SELECT * FROM users WHERE id = %s", (route["id_assigned_user"],))
        if not driver:
            continue
        truck_id = driver.get("id_truck_default")
        if not truck_id:
            truck = fetch_one(
                conn, "SELECT id FROM trucks WHERE id_state_truck = 'AV' ORDER BY id LIMIT 1"
            )
            if not truck:
                continue
            truck_id = truck["id"]
        orders = _pending_route_orders(conn, route["id"], target)
        if not orders:
            continue
        start = datetime.combine(target, time(8, 0), tzinfo=timezone.utc)
        current = start
        slots = []
        for order in orders:
            end = current + timedelta(minutes=25 + rng.randint(0, 15))
            slots.append((order, current, end))
            current = end + timedelta(minutes=18 + rng.randint(0, 12))
        trip_end = current + timedelta(minutes=20)
        completed = target < date.today()
        trip_id = new_id()
        execute(
            conn,
            """
            INSERT INTO trips(id, start_time, end_time, id_truck, id_user_driver, id_route, id_state_trip)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                trip_id,
                start,
                trip_end if completed else None,
                truck_id,
                driver["id"],
                route["id"],
                "CP" if completed else "IP",
            ),
        )
        for sequence, (order, slot_start, slot_end) in enumerate(slots, start=1):
            execute(
                conn,
                """
                INSERT INTO trip_orders(trip_id, order_id, start_time, end_time, sequence)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (trip_id, order_id) DO UPDATE
                SET start_time = EXCLUDED.start_time, end_time = EXCLUDED.end_time,
                    sequence = EXCLUDED.sequence
                """,
                (trip_id, order["id"], slot_start, slot_end, sequence),
            )
            store = fetch_one(conn, "SELECT * FROM stores WHERE id = %s", (order["id_store"],))
            for offset in (0, 12):
                execute(
                    conn,
                    """
                    INSERT INTO readings(id, date, door_state, temp, perc_humidity, latitude, longitude, id_truck)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        new_id(),
                        slot_end + timedelta(minutes=offset),
                        offset == 0,
                        round(2.0 + rng.random() * 4.5, 1),
                        rng.randint(76, 94),
                        store["latitude"],
                        store["longitude"],
                        truck_id,
                    ),
                )
            if completed:
                execute(
                    conn,
                    "UPDATE orders SET id_state_order = 'DO', delivered = %s WHERE id = %s",
                    (slot_end, order["id"]),
                )
                execute(
                    conn,
                    "INSERT INTO order_logs(id, date, id_order, id_state_order) VALUES (%s, %s, %s, 'DO')",
                    (new_id(), slot_end, order["id"]),
                )
        execute(
            conn,
            """
            INSERT INTO trip_logs(id, date, id_trip, id_state_trip, orders)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (
                new_id(),
                trip_end,
                trip_id,
                "CP" if completed else "IP",
                __import__("json").dumps(
                    [
                        {
                            "orderId": order["id"],
                            "startTime": slot_start.isoformat(),
                            "endTime": slot_end.isoformat(),
                        }
                        for order, slot_start, slot_end in slots
                    ]
                ),
            ),
        )
        execute(
            conn,
            "UPDATE trucks SET id_state_truck = %s WHERE id = %s",
            ("AV" if completed else "IR", truck_id),
        )
        execute(
            conn,
            "INSERT INTO truck_logs(id, date, id_truck, id_state_truck) VALUES (%s, now(), %s, %s)",
            (new_id(), truck_id, "AV" if completed else "IR"),
        )
        created.append(fetch_one(conn, "SELECT * FROM trips WHERE id = %s", (trip_id,)))
    if not created:
        raise HTTPException(status_code=400, detail="No se pudieron generar viajes para esta fecha")
    return [trip_dto(conn, row) for row in created]


def check_simulated_trips(conn):
    rows = fetch_all(
        conn,
        """
        UPDATE orders SET id_state_order = 'LO'
        WHERE id_state_order = 'PO' AND coalesce(delivered, date)::date < CURRENT_DATE
        RETURNING *
        """,
    )
    for row in rows:
        execute(
            conn,
            "INSERT INTO order_logs(id, date, id_order, id_state_order) VALUES (%s, now(), %s, 'LO')",
            (new_id(), row["id"]),
        )
    return [order_dto(conn, row) for row in rows]
