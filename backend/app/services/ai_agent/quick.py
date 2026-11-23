"""Respuestas rápidas deterministas del asistente (A2).

Se calculan con datos del panel, sin llamar al agente ni consumir cuota.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.alert import Alert
from app.models.route import Route, RouteDeliveryDay
from app.models.trip import Trip, TripOrder
from app.models.truck import Truck
from app.services import agent_read
from app.services.ai_agent.context import collect_snapshot
from app.services.route_links import today_weekday
from app.utils.time import ensure_utc, utcnow

QUICK_PROMPTS: dict[str, str] = {
    "fleet-summary": "Resumen de la flota",
    "active-alerts": "Alertas activas",
    "today-alerts": "Alertas de hoy",
    "active-trips": "Viajes en curso",
    "critical-containers": "Contenedores críticos",
    "today-routes": "Rutas de hoy",
}


class UnknownQuickError(Exception):
    pass


def list_quick() -> list[dict[str, str]]:
    return [{"id": key, "title": title} for key, title in QUICK_PROMPTS.items()]


def _stamp() -> str:
    now = datetime.now(settings.tz)
    return f"Datos del sistema · {now:%Y-%m-%d %H:%M} {settings.app_timezone}"


def _fleet_summary(db: Session) -> str:
    snapshot = collect_snapshot(db)
    statuses = snapshot.get("truck_statuses", {})
    status_text = (
        ", ".join(f"{value} {key}" for key, value in sorted(statuses.items()))
        if statuses
        else "sin camiones"
    )
    counts = snapshot["alert_counts"]
    alerts_text = (
        ", ".join(f"{key}: {value}" for key, value in sorted(counts.items()))
        if counts
        else "ninguna"
    )
    return "\n".join(
        [
            f"Flota: {snapshot['trucks_total']} camiones ({status_text}).",
            f"Alertas activas: {snapshot['alerts_active']} ({alerts_text}).",
            (
                f"Viajes en curso: {snapshot['active_trips']} · "
                f"entregas pendientes: {snapshot['pending_orders']} · "
                f"rutas hoy: {snapshot['routes_today']}."
            ),
            _stamp(),
        ]
    )


def _active_alerts(db: Session) -> str:
    rows = list(
        db.scalars(
            select(Alert)
            .where(Alert.status == "activa")
            .order_by(Alert.started_at.desc())
            .limit(10)
        )
    )
    if not rows:
        return f"No hay alertas activas.\n{_stamp()}"
    plates = {
        truck.id: truck.plate
        for truck in db.scalars(
            select(Truck).where(
                Truck.id.in_({row.truck_id for row in rows if row.truck_id})
            )
        )
    }
    lines = [f"Alertas activas ({len(rows)}):"]
    for row in rows:
        plate = plates.get(row.truck_id) if row.truck_id else "sin camión"
        value = f" · {row.value:g}" if row.value is not None else ""
        acked = " · reconocida" if row.acknowledged_at else ""
        age = max(
            0,
            int(
                (utcnow() - (ensure_utc(row.started_at) or utcnow())).total_seconds()
                // 60
            ),
        )
        lines.append(f"- {plate} · {row.alert_type}{value} · hace {age} min{acked}")
    lines.append(_stamp())
    return "\n".join(lines)


def _today_alerts(db: Session) -> str:
    counts = agent_read.alerts_today(db, limit=5)
    created = (
        ", ".join(
            f"{key}: {value}" for key, value in sorted(counts.created_by_type.items())
        )
        if counts.created_by_type
        else "ninguna"
    )
    lines = [
        f"Alertas de hoy ({settings.app_timezone}):",
        f"- Creadas: {counts.created_total} ({created}).",
        f"- Resueltas: {counts.resolved_total}.",
        f"- Activas ahora: {counts.active_total}.",
    ]
    if counts.items:
        lines.append("Últimas creadas hoy:")
        for item in counts.items[:5]:
            plate = item.truck_plate or "sin camión"
            hour = item.started_at[11:16]
            lines.append(f"- {plate} · {item.alert_type} · {item.status} · {hour}")
    lines.append(_stamp())
    return "\n".join(lines)


def _active_trips(db: Session) -> str:
    rows = list(
        db.scalars(
            select(Trip)
            .where(Trip.state == "in_progress")
            .order_by(Trip.started_at.desc())
            .limit(5)
        )
    )
    if not rows:
        return f"No hay viajes en curso.\n{_stamp()}"
    plates = {
        truck.id: truck.plate
        for truck in db.scalars(
            select(Truck).where(Truck.id.in_({trip.truck_id for trip in rows}))
        )
    }
    lines = [f"Viajes en curso ({len(rows)}):"]
    for trip in rows:
        orders = list(trip.orders)
        delivered = sum(1 for order in orders if order.state == "delivered")
        failed = sum(1 for order in orders if order.state == "failed")
        pending = sum(
            1 for order in orders if order.state in ("pending", "in_delivery")
        )
        lines.append(
            f"- Conductor {trip.driver_id} · {plates.get(trip.truck_id, '')} · "
            f"{delivered}/{len(orders)} entregadas, {failed} fallidas, "
            f"{pending} pendientes"
        )
    lines.append(_stamp())
    return "\n".join(lines)


def _critical_containers(db: Session) -> str:
    snapshot = collect_snapshot(db)
    critical = snapshot["critical"][:8]
    if not critical:
        return f"No hay contenedores en estado crítico.\n{_stamp()}"
    labels = {
        "out_of_range": "fuera de rango",
        "door_open": "puerta abierta",
        "no_signal": "sin señal",
        "no_data": "sin datos",
        "ok": "ok",
    }
    lines = [f"Contenedores críticos ({len(critical)}):"]
    for entry in critical:
        details = [labels.get(entry["status"], entry["status"])]
        if entry["temperature"] is not None:
            details.append(f"{entry['temperature']:.1f} °C / {entry['humidity']:.1f} %")
        if entry["age_minutes"] is not None:
            details.append(f"lectura hace {entry['age_minutes']} min")
        lines.append(f"- {entry['plate']} · " + " · ".join(details))
    lines.append(_stamp())
    return "\n".join(lines)


def _today_routes(db: Session) -> str:
    today = today_weekday()
    routes = list(
        db.scalars(
            select(Route)
            .where(
                Route.status == "activa",
                Route.id.in_(
                    select(RouteDeliveryDay.route_id).where(
                        RouteDeliveryDay.weekday == today
                    )
                ),
            )
            .order_by(Route.name)
            .limit(8)
        )
    )
    if not routes:
        return f"No hay rutas programadas para hoy.\n{_stamp()}"
    lines = [f"Rutas de hoy ({len(routes)}):"]
    for route in routes:
        pending = int(
            db.scalar(
                select(func.count(TripOrder.id))
                .join(Trip, Trip.id == TripOrder.trip_id)
                .where(
                    Trip.route_id == route.id,
                    Trip.state == "in_progress",
                    TripOrder.state.in_(("pending", "in_delivery")),
                )
            )
            or 0
        )
        lines.append(
            f"- {route.name} · Conductor {route.assigned_driver_id} · "
            f"{len(route.points)} puntos · {pending} entregas pendientes"
        )
    lines.append(_stamp())
    return "\n".join(lines)


def quick_answer(db: Session, key: str) -> tuple[str, str]:
    """Devuelve ``(título, texto)`` para una sugerencia rápida."""
    title = QUICK_PROMPTS.get(key)
    if title is None:
        raise UnknownQuickError("Sugerencia no encontrada")
    builders = {
        "fleet-summary": _fleet_summary,
        "active-alerts": _active_alerts,
        "today-alerts": _today_alerts,
        "active-trips": _active_trips,
        "critical-containers": _critical_containers,
        "today-routes": _today_routes,
    }
    return title, builders[key](db)
