import json
import math
import random
from datetime import date, datetime, time, timedelta, timezone

from ..config import AUTO_SEED, SEED_FILE
from ..db import connect, new_id
from ..security import hash_password


def _dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _date(value):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def _executemany(conn, query, rows):
    with conn.cursor() as cur:
        cur.executemany(query, rows)


def load_seed():
    return json.loads(SEED_FILE.read_text())


def ensure_reference_data(conn, data):
    _executemany(conn, 
        "INSERT INTO state_trucks(code, message) VALUES (%s, %s) "
        "ON CONFLICT (code) DO UPDATE SET message = EXCLUDED.message",
        [(row["_id"], row["message"]) for row in data["state_truck"]],
    )
    _executemany(conn, 
        "INSERT INTO state_orders(code, message) VALUES (%s, %s) "
        "ON CONFLICT (code) DO UPDATE SET message = EXCLUDED.message",
        [(row["_id"], row["message"]) for row in data["state_order"]],
    )
    _executemany(conn, 
        "INSERT INTO state_trips(code, message) VALUES (%s, %s) "
        "ON CONFLICT (code) DO UPDATE SET message = EXCLUDED.message",
        [(row["_id"], row["message"]) for row in data["state_trip"]],
    )
    _executemany(conn, 
        "INSERT INTO alert_types(code, message) VALUES (%s, %s) "
        "ON CONFLICT (code) DO UPDATE SET message = EXCLUDED.message",
        [(row["_id"], row["message"]) for row in data["alert_types"]],
    )
    for row in data["parameters"]:
        conn.execute(
            """
            INSERT INTO parameters(id, max_temperature, min_temperature, max_humidity, min_humidity)
            VALUES (1, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                row["max_temperature"],
                row["min_temperature"],
                row["max_humidity"],
                row["min_humidity"],
            ),
        )


def import_seed_data(conn, data):
    _executemany(conn, 
        "INSERT INTO trucks(id, brand, model, license_plate, id_state_truck) "
        "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
        [
            (row["_id"], row["brand"], row["model"], row["license_plate"], row["IDStateTruck"])
            for row in data["trucks"]
        ],
    )

    _executemany(conn, 
        """
        INSERT INTO users(
            id, first_name, last_name, middle_name, email, phone, birthdate,
            password_hash, is_admin, id_truck_default, active
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        [
            (
                row["_id"],
                row["first_name"],
                row["last_name"],
                row.get("middle_name"),
                row["email"].lower(),
                row.get("phone"),
                _date(row.get("birthdate")),
                hash_password(row.get("password") or "frostbase"),
                row.get("is_admin", False),
                row.get("IDTruckDefault"),
                row.get("active", True),
            )
            for row in data["users"]
        ],
    )

    _executemany(conn, 
        """
        INSERT INTO stores(id, name, phone, location, latitude, longitude, active)
        VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
        """,
        [
            (
                row["_id"],
                row["name"],
                row.get("phone"),
                row["location"],
                row["latitude"],
                row["longitude"],
                row.get("active", True),
            )
            for row in data["stores"]
        ],
    )

    for row in data["routes"]:
        conn.execute(
            """
            INSERT INTO routes(id, name, deliver_days, id_assigned_user, active)
            VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
            """,
            (
                row["_id"],
                row["name"],
                row.get("deliverDays") or [],
                row.get("IDAssignedUser"),
                row.get("active", True),
            ),
        )
        _executemany(conn, 
            """
            INSERT INTO route_stores(route_id, store_id, sequence)
            VALUES (%s, %s, %s) ON CONFLICT (route_id, store_id) DO UPDATE
            SET sequence = EXCLUDED.sequence
            """,
            [(row["_id"], store["IDStore"], store["sequence"]) for store in row.get("stores", [])],
        )

    _executemany(conn, 
        """
        INSERT INTO orders(id, date, delivered, id_created_by_user, id_store, id_state_order)
        VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
        """,
        [
            (
                row["_id"],
                _dt(row["date"]),
                _dt(row.get("delivered")),
                row.get("IDCreatedByUser"),
                row["IDStore"],
                row["IDStateOrder"],
            )
            for row in data["orders"]
        ],
    )

    _executemany(conn, 
        """
        INSERT INTO order_logs(id, date, id_order, id_state_order)
        VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
        """,
        [
            (row["_id"], _dt(row["date"]), row.get("IDOrder"), row.get("IDStateOrder"))
            for row in data["order_logs"]
        ],
    )

    _executemany(conn, 
        """
        INSERT INTO truck_logs(id, date, id_truck, id_state_truck)
        VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
        """,
        [
            (row["_id"], _dt(row["date"]), row["IDTruck"], row["IDStateTruck"])
            for row in data["truck_logs"]
        ],
    )

    for row in data["trips"]:
        conn.execute(
            """
            INSERT INTO trips(id, start_time, end_time, id_truck, id_user_driver, id_route, id_state_trip)
            VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
            """,
            (
                row["_id"],
                _dt(row["start_time"]),
                _dt(row.get("end_time")),
                row["IDTruck"],
                row["IDUserDriver"],
                row["IDRoute"],
                row["IDStateTrip"],
            ),
        )
        for sequence, trip_order in enumerate(row.get("orders") or [], start=1):
            conn.execute(
                """
                INSERT INTO trip_orders(trip_id, order_id, start_time, end_time, sequence)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (trip_id, order_id) DO UPDATE
                SET start_time = EXCLUDED.start_time, end_time = EXCLUDED.end_time,
                    sequence = EXCLUDED.sequence
                """,
                (
                    row["_id"],
                    trip_order["IDOrder"],
                    _dt(trip_order.get("start_time")),
                    _dt(trip_order.get("end_time")),
                    sequence,
                ),
            )

    _executemany(conn, 
        """
        INSERT INTO trip_logs(id, date, id_trip, id_state_trip, orders)
        VALUES (%s, %s, %s, %s, %s::jsonb) ON CONFLICT (id) DO NOTHING
        """,
        [
            (
                row["_id"],
                _dt(row["date"]),
                row.get("IDTrip"),
                "IP" if row.get("IDStateTrip") == "IR" else row.get("IDStateTrip"),
                json.dumps(row.get("orders") or []),
            )
            for row in data["trip_logs"]
        ],
    )

    _executemany(conn, 
        """
        INSERT INTO readings(id, date, door_state, temp, perc_humidity, latitude, longitude, id_truck)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
        """,
        [
            (
                row["_id"],
                _dt(row["date"]),
                row.get("door_state", False),
                row["temp"],
                row["perc_humidity"],
                row["latitude"],
                row["longitude"],
                row["IDTruck"],
            )
            for row in data["readings"]
        ],
    )

    reading_ids = {row["_id"] for row in data["readings"]}
    _executemany(conn, 
        """
        INSERT INTO alerts(id, date, state, id_reading, id_alert_type)
        VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
        """,
        [
            (
                row["_id"],
                _dt(row["date"]),
                row.get("state", True),
                row.get("IDReading") if row.get("IDReading") in reading_ids else None,
                row["IDAlertTypes"],
            )
            for row in data["alerts"]
        ],
    )

    _executemany(conn, 
        """
        INSERT INTO door_events(id, state, time_opened, id_truck)
        VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
        """,
        [
            (row["_id"], row["state"], _dt(row["time_opened"]), row["IDTruck"])
            for row in data["door_events"]
        ],
    )

    _executemany(conn, 
        """
        INSERT INTO osrm_routes(
            id, start_latitude, start_longitude, end_latitude, end_longitude,
            distance, duration, geometry
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb) ON CONFLICT (id) DO NOTHING
        """,
        [
            (
                row["_id"],
                row["startLatitude"],
                row["startLongitude"],
                row["endLatitude"],
                row["endLongitude"],
                row.get("distance") or 0,
                row.get("duration") or 0,
                json.dumps(
                    [
                        {
                            "latitude": point.get("Latitude", point.get("latitude")),
                            "longitude": point.get("Longitude", point.get("longitude")),
                        }
                        for point in row.get("geometry") or []
                    ]
                ),
            )
            for row in data["osrm_routes"]
        ],
    )


def ensure_recent_demo_activity(conn):
    now = datetime.now(timezone.utc)
    recent = conn.execute(
        "SELECT count(*) AS total FROM readings WHERE date >= %s",
        (now - timedelta(days=2),),
    ).fetchone()["total"]
    if recent:
        return

    trucks = conn.execute("SELECT id FROM trucks ORDER BY id").fetchall()
    rng = random.Random(42)
    recent_ids = []
    for truck in trucks:
        for hour in range(24):
            stamp = now - timedelta(hours=23 - hour, minutes=rng.randint(0, 50))
            angle = hour / 24 * 6.28318
            reading_id = new_id()
            recent_ids.append(reading_id)
            conn.execute(
                """
                INSERT INTO readings(id, date, door_state, temp, perc_humidity, latitude, longitude, id_truck)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    reading_id,
                    stamp,
                    rng.random() < 0.08,
                    round(0.4 + 2.6 * (0.5 + 0.5 * random.Random(hour).random()), 1),
                    int(78 + 6 * (0.5 + 0.5 * random.Random(hour + 7).random())),
                    32.4590 + 0.028 * (0.5 + 0.5 * math.sin(angle)),
                    -116.9796 + 0.030 * math.cos(angle),
                    truck["id"],
                ),
            )

    orders_today = conn.execute(
        "SELECT count(*) AS total FROM orders WHERE date::date = CURRENT_DATE"
    ).fetchone()["total"]
    if not orders_today:
        admins = conn.execute(
            "SELECT id FROM users WHERE is_admin = true ORDER BY id LIMIT 3"
        ).fetchall()
        stores = conn.execute(
            "SELECT id FROM stores WHERE active = true ORDER BY id LIMIT 10"
        ).fetchall()
        if admins and stores:
            for index, store in enumerate(stores):
                created = now.replace(hour=7 + index % 5, minute=15, second=0, microsecond=0)
                delivered = (
                    created.replace(hour=13 + index % 4)
                    if index % 2 == 0
                    else None
                )
                state = "DO" if delivered else "PO"
                order_id = new_id()
                conn.execute(
                    """
                    INSERT INTO orders(id, date, delivered, id_created_by_user, id_store, id_state_order)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (order_id, created, delivered, admins[index % len(admins)]["id"], store["id"], state),
                )
                conn.execute(
                    "INSERT INTO order_logs(id, date, id_order, id_state_order) VALUES (%s, %s, %s, %s)",
                    (new_id(), created, order_id, state),
                )

    recent_alerts = conn.execute(
        "SELECT count(*) AS total FROM alerts WHERE date >= %s",
        (now - timedelta(days=2),),
    ).fetchone()["total"]
    if not recent_alerts and recent_ids:
        for index, alert_type in enumerate(("HT", "LH", "OD")):
            conn.execute(
                "INSERT INTO alerts(id, date, state, id_reading, id_alert_type) VALUES (%s, %s, %s, %s, %s)",
                (
                    new_id(),
                    now - timedelta(hours=2 + index * 3),
                    True,
                    recent_ids[-1 - index * 17],
                    alert_type,
                ),
            )


def seed_database(force: bool = False) -> dict:
    data = load_seed()
    with connect() as conn:
        ensure_reference_data(conn, data)
        user_count = conn.execute("SELECT count(*) AS total FROM users").fetchone()["total"]
        if user_count and not force:
            return {"seeded": False, "reason": "database already has users"}
        if force:
            tables = (
                "trip_logs",
                "trip_orders",
                "alerts",
                "door_events",
                "readings",
                "truck_logs",
                "order_logs",
                "trips",
                "orders",
                "route_stores",
                "routes",
                "users",
                "trucks",
                "stores",
                "osrm_routes",
            )
            for table in tables:
                conn.execute(f"DELETE FROM {table}")
        import_seed_data(conn, data)
        ensure_recent_demo_activity(conn)
        conn.commit()
        return {"seeded": True, "users": len(data["users"]), "stores": len(data["stores"])}


def seed_if_enabled() -> dict:
    if not AUTO_SEED:
        return {"seeded": False, "reason": "AUTO_SEED disabled"}
    return seed_database()
