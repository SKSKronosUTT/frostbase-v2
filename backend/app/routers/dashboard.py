from fastapi import APIRouter, Depends

from ..db import fetch_all, fetch_one, get_conn
from ..responses import ok
from ..serializers import alert_dto, reading_dto, route_dto, truck_dto

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(conn=Depends(get_conn)):
    params = fetch_one(conn, "SELECT * FROM parameters WHERE id = 1") or {}
    min_temp = float(params.get("min_temperature") or -2)
    max_temp = float(params.get("max_temperature") or 4)
    min_humidity = int(params.get("min_humidity") or 75)
    max_humidity = int(params.get("max_humidity") or 85)

    fleet_rows = fetch_all(
        conn,
        """
        SELECT s.code, s.message, count(t.id)::int AS total
        FROM state_trucks s
        LEFT JOIN trucks t ON t.id_state_truck = s.code
        GROUP BY s.code, s.message
        ORDER BY s.code
        """,
    )
    fleet = {row["code"]: row["total"] for row in fleet_rows}

    orders_today = fetch_one(
        conn, "SELECT count(*)::int AS total FROM orders WHERE date::date = CURRENT_DATE"
    )["total"]
    delivered_today = fetch_one(
        conn,
        "SELECT count(*)::int AS total FROM orders WHERE delivered::date = CURRENT_DATE",
    )["total"]
    pending = fetch_one(
        conn,
        "SELECT count(*)::int AS total FROM orders WHERE id_state_order IN ('PO', 'LO')",
    )["total"]
    cancelled_today = fetch_one(
        conn,
        "SELECT count(*)::int AS total FROM orders WHERE date::date = CURRENT_DATE AND id_state_order = 'CO'",
    )["total"]

    alerts_active = fetch_one(
        conn, "SELECT count(*)::int AS total FROM alerts WHERE state = true"
    )["total"]
    alerts_by_type = fetch_all(
        conn,
        """
        SELECT a.id_alert_type, t.message, count(*)::int AS total
        FROM alerts a JOIN alert_types t ON t.code = a.id_alert_type
        WHERE a.state = true GROUP BY a.id_alert_type, t.message
        """,
    )
    alert_map = {row["id_alert_type"]: row["total"] for row in alerts_by_type}

    latest_window = fetch_one(
        conn,
        "SELECT coalesce(max(date), now()) - interval '24 hours' AS since FROM readings",
    )["since"]
    env = fetch_one(
        conn,
        """
        SELECT count(*)::int AS total,
               coalesce(avg(temp), 0) AS avg_temp,
               coalesce(avg(perc_humidity), 0) AS avg_humidity,
               count(*) FILTER (WHERE temp BETWEEN %s AND %s)::int AS temp_in,
               count(*) FILTER (WHERE perc_humidity BETWEEN %s AND %s)::int AS humidity_in
        FROM readings WHERE date >= %s
        """,
        (min_temp, max_temp, min_humidity, max_humidity, latest_window),
    )
    total_env = env["total"] or 0
    trend_rows = fetch_all(
        conn,
        """
        SELECT date_trunc('hour', date) AS bucket,
               avg(temp) AS temperature,
               avg(perc_humidity) AS humidity
        FROM readings
        WHERE date >= %s
        GROUP BY 1 ORDER BY 1
        """,
        (latest_window,),
    )
    trend = [
        {
            "time": row["bucket"].isoformat(),
            "temperature": round(float(row["temperature"]), 2),
            "humidity": round(float(row["humidity"]), 1),
        }
        for row in trend_rows
    ]

    latest_rows = fetch_all(
        conn,
        """
        SELECT DISTINCT ON (t.id) t.id AS truck_id, r.id AS reading_id
        FROM trucks t JOIN readings r ON r.id_truck = t.id
        ORDER BY t.id, r.date DESC
        """,
    )
    latest = []
    for row in latest_rows:
        truck = fetch_one(conn, "SELECT * FROM trucks WHERE id = %s", (row["truck_id"],))
        reading = fetch_one(conn, "SELECT * FROM readings WHERE id = %s", (row["reading_id"],))
        latest.append(
            {
                "truck": truck_dto(conn, truck),
                "reading": reading_dto(conn, reading, include_truck=False),
            }
        )

    alerts = fetch_all(conn, "SELECT * FROM alerts ORDER BY date DESC LIMIT 6")
    routes_today = fetch_all(
        conn,
        """
        SELECT * FROM routes
        WHERE active = true AND EXTRACT(DOW FROM CURRENT_DATE)::int = ANY(deliver_days)
        ORDER BY name
        """,
    )
    all_routes = fetch_all(conn, "SELECT * FROM routes WHERE active = true ORDER BY name")
    routes_today_payload = []
    for row in routes_today:
        dto = route_dto(conn, row, include_waypoints=False)
        stats = fetch_one(
            conn,
            """
            SELECT count(o.id)::int AS total,
                   count(o.id) FILTER (WHERE o.id_state_order = 'DO')::int AS delivered
            FROM orders o
            JOIN route_stores rs ON rs.store_id = o.id_store
            WHERE rs.route_id = %s AND o.date::date = CURRENT_DATE
            """,
            (row["id"],),
        )
        dto["ordersTotal"] = stats["total"] if stats else 0
        dto["ordersDelivered"] = stats["delivered"] if stats else 0
        routes_today_payload.append(dto)
    active_trips = fetch_one(
        conn, "SELECT count(*)::int AS total FROM trips WHERE id_state_trip = 'IP'"
    )["total"]
    completed_trips_today = fetch_one(
        conn,
        "SELECT count(*)::int AS total FROM trips WHERE end_time::date = CURRENT_DATE",
    )["total"]

    return ok(
        {
            "kpis": {
                "trucks": {
                    "total": sum(fleet.values()),
                    "available": fleet.get("AV", 0),
                    "inRoute": fleet.get("IR", 0),
                    "maintenance": fleet.get("IM", 0),
                    "outOfService": fleet.get("OS", 0),
                },
                "orders": {
                    "today": orders_today,
                    "delivered": delivered_today,
                    "pending": pending,
                    "cancelled": cancelled_today,
                },
                "alerts": {
                    "active": alerts_active,
                    "temperature": alert_map.get("HT", 0) + alert_map.get("LT", 0),
                    "humidity": alert_map.get("HH", 0) + alert_map.get("LH", 0),
                    "door": alert_map.get("OD", 0),
                },
                "environment": {
                    "readings": total_env,
                    "avgTemperature": round(float(env["avg_temp"]), 2),
                    "avgHumidity": round(float(env["avg_humidity"]), 1),
                    "temperatureCompliance": round((env["temp_in"] / total_env) * 100, 1)
                    if total_env
                    else 0,
                    "humidityCompliance": round((env["humidity_in"] / total_env) * 100, 1)
                    if total_env
                    else 0,
                },
                "routes": {"today": len(routes_today), "active": len(all_routes)},
                "trips": {
                    "active": active_trips,
                    "completedToday": completed_trips_today,
                },
            },
            "fleet": [
                {"id": row["code"], "label": row["message"], "count": row["total"]}
                for row in fleet_rows
            ],
            "trend": trend,
            "latestReadings": latest,
            "recentAlerts": [alert_dto(conn, row) for row in alerts],
            "routesToday": routes_today_payload,
            "parameters": {
                "maxTemperature": float(params.get("max_temperature") or 4),
                "minTemperature": float(params.get("min_temperature") or -2),
                "maxHumidity": int(params.get("max_humidity") or 85),
                "minHumidity": int(params.get("min_humidity") or 75),
            },
            "windowSince": latest_window.isoformat(),
        }
    )
