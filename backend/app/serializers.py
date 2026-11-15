from typing import Any

from .config import BASE_LOCATION
from .db import fetch_all, fetch_one


def iso(value):
    return value.isoformat() if value is not None else None


def state_dto(code: str | None, message: str | None):
    if not code:
        return None
    return {"id": code, "description": message}


def truck_dto(conn, truck: dict | str | None):
    if isinstance(truck, str):
        truck = fetch_one(
            conn,
            """
            SELECT t.*, s.message AS state_message
            FROM trucks t JOIN state_trucks s ON s.code = t.id_state_truck
            WHERE t.id = %s
            """,
            (truck,),
        )
    if not truck:
        return None
    return {
        "id": truck["id"],
        "brand": truck["brand"],
        "model": truck["model"],
        "licensePlate": truck["license_plate"],
        "state": state_dto(truck.get("id_state_truck"), truck.get("state_message")),
        "createdAt": iso(truck.get("created_at")),
    }


def user_dto(conn, user: dict | str | None, include_active: bool = True):
    if isinstance(user, str):
        user = fetch_one(conn, "SELECT * FROM users WHERE id = %s", (user,))
    if not user:
        return None
    name = {
        "firstName": user["first_name"],
        "lastName": user["last_name"],
        "middleName": user.get("middle_name") or "",
    }
    name["fullName"] = " ".join(
        part for part in (name["firstName"], name["lastName"], name["middleName"]) if part
    ).strip()
    dto = {
        "id": user["id"],
        "name": name,
        "email": user["email"],
        "phone": user.get("phone"),
        "birthDate": iso(user.get("birthdate")),
        "isAdmin": user.get("is_admin", False),
        "truckDefault": truck_dto(conn, user.get("id_truck_default"))
        if user.get("id_truck_default")
        else None,
    }
    if include_active:
        dto["active"] = user.get("active", True)
    return dto


def admin_dto(conn, user):
    dto = user_dto(conn, user, include_active=False)
    if dto:
        dto.pop("truckDefault", None)
        dto.pop("isAdmin", None)
    return dto


def driver_dto(conn, user):
    return user_dto(conn, user)


def store_dto(store: dict | None):
    if not store:
        return None
    return {
        "id": store["id"],
        "name": store["name"],
        "phone": store.get("phone"),
        "location": {
            "address": store["location"],
            "latitude": float(store["latitude"]),
            "longitude": float(store["longitude"]),
        },
        "active": store.get("active", True),
    }


def order_dto(conn, order: dict | str | None):
    if isinstance(order, str):
        order = fetch_one(conn, "SELECT * FROM orders WHERE id = %s", (order,))
    if not order:
        return None
    return {
        "id": order["id"],
        "date": iso(order["date"]),
        "deliverDate": iso(order.get("delivered") or order["date"].date()),
        "createdBy": admin_dto(conn, order.get("id_created_by_user"))
        if order.get("id_created_by_user")
        else None,
        "store": store_dto(
            fetch_one(conn, "SELECT * FROM stores WHERE id = %s", (order["id_store"],))
        ),
        "state": state_dto(
            order["id_state_order"],
            (
                fetch_one(
                    conn,
                    "SELECT message FROM state_orders WHERE code = %s",
                    (order["id_state_order"],),
                )
                or {}
            ).get("message"),
        ),
    }


def reading_dto(conn, reading: dict | str | None, include_truck: bool = True):
    if isinstance(reading, str):
        reading = fetch_one(conn, "SELECT * FROM readings WHERE id = %s", (reading,))
    if not reading:
        return None
    dto = {
        "id": reading["id"],
        "date": iso(reading["date"]),
        "doorState": reading["door_state"],
        "temp": float(reading["temp"]),
        "percHumidity": int(reading["perc_humidity"]),
        "location": {
            "latitude": float(reading["latitude"]),
            "longitude": float(reading["longitude"]),
        },
    }
    if include_truck:
        dto["truck"] = truck_dto(conn, reading.get("id_truck"))
        dto["idTruck"] = reading.get("id_truck")
    return dto


def alert_dto(conn, alert: dict | str | None):
    if isinstance(alert, str):
        alert = fetch_one(conn, "SELECT * FROM alerts WHERE id = %s", (alert,))
    if not alert:
        return None
    alert_type = fetch_one(
        conn, "SELECT * FROM alert_types WHERE code = %s", (alert["id_alert_type"],)
    )
    return {
        "id": alert["id"],
        "date": iso(alert["date"]),
        "state": alert["state"],
        "reading": reading_dto(conn, alert.get("id_reading")),
        "alertType": state_dto(
            alert["id_alert_type"], alert_type.get("message") if alert_type else None
        ),
    }


def _route_waypoints(conn, stores: list[dict]) -> list[dict]:
    point = dict(BASE_LOCATION)
    points = [dict(point)]
    for store in stores:
        end = {
            "latitude": float(store["latitude"]),
            "longitude": float(store["longitude"]),
        }
        match = fetch_one(
            conn,
            """
            SELECT geometry FROM osrm_routes
            WHERE abs(start_latitude - %s) < 0.00001
              AND abs(start_longitude - %s) < 0.00001
              AND abs(end_latitude - %s) < 0.00001
              AND abs(end_longitude - %s) < 0.00001
            LIMIT 1
            """,
            (
                point["latitude"],
                point["longitude"],
                end["latitude"],
                end["longitude"],
            ),
        )
        geometry = (match or {}).get("geometry") or []
        if geometry:
            points.extend(
                {
                    "latitude": float(p["latitude"]),
                    "longitude": float(p["longitude"]),
                }
                for p in geometry[1:]
            )
        else:
            points.append(end)
        point = end
    base = dict(BASE_LOCATION)
    match = fetch_one(
        conn,
        """
        SELECT geometry FROM osrm_routes
        WHERE abs(start_latitude - %s) < 0.00001
          AND abs(start_longitude - %s) < 0.00001
          AND abs(end_latitude - %s) < 0.00001
          AND abs(end_longitude - %s) < 0.00001
        LIMIT 1
        """,
        (point["latitude"], point["longitude"], base["latitude"], base["longitude"]),
    )
    geometry = (match or {}).get("geometry") or []
    if geometry:
        points.extend(
            {"latitude": float(p["latitude"]), "longitude": float(p["longitude"])}
            for p in geometry[1:]
        )
    else:
        points.append(base)
    return points


def route_dto(conn, route: dict | str | None, include_waypoints: bool = True):
    if isinstance(route, str):
        route = fetch_one(conn, "SELECT * FROM routes WHERE id = %s", (route,))
    if not route:
        return None
    store_rows = fetch_all(
        conn,
        """
        SELECT s.*, rs.sequence
        FROM route_stores rs
        JOIN stores s ON s.id = rs.store_id
        WHERE rs.route_id = %s
        ORDER BY rs.sequence
        """,
        (route["id"],),
    )
    dto = {
        "id": route["id"],
        "name": route["name"],
        "deliverDays": route.get("deliver_days") or [],
        "driver": driver_dto(conn, route.get("id_assigned_user"))
        if route.get("id_assigned_user")
        else None,
        "stores": [
            {"store": store_dto(store), "sequence": store["sequence"]}
            for store in store_rows
        ],
        "active": route.get("active", True),
    }
    if include_waypoints:
        dto["waypoints"] = _route_waypoints(conn, store_rows)
    return dto


def trip_order_dto(conn, trip_order: dict):
    dto = order_dto(conn, trip_order["order_id"]) or {}
    dto["orderTime"] = {
        "startTime": iso(trip_order.get("start_time")),
        "endTime": iso(trip_order.get("end_time")),
    }
    return dto


def trip_dto(conn, trip: dict | str | None):
    if isinstance(trip, str):
        trip = fetch_one(conn, "SELECT * FROM trips WHERE id = %s", (trip,))
    if not trip:
        return None
    state = fetch_one(
        conn, "SELECT * FROM state_trips WHERE code = %s", (trip["id_state_trip"],)
    )
    route = fetch_one(conn, "SELECT * FROM routes WHERE id = %s", (trip["id_route"],))
    orders = fetch_all(
        conn,
        "SELECT * FROM trip_orders WHERE trip_id = %s ORDER BY sequence, id",
        (trip["id"],),
    )
    return {
        "id": trip["id"],
        "tripTime": {
            "startTime": iso(trip["start_time"]),
            "endTime": iso(trip.get("end_time")),
        },
        "state": state_dto(trip["id_state_trip"], state.get("message") if state else None),
        "truck": truck_dto(conn, trip["id_truck"]),
        "driver": user_dto(conn, trip["id_user_driver"]),
        "route": {
            "id": route["id"],
            "name": route["name"],
            "deliverDays": route.get("deliver_days") or [],
        }
        if route
        else None,
        "orders": [trip_order_dto(conn, row) for row in orders],
    }
