"""Viajes y entregas (G6A + G6B).

Reglas de negocio (decisiones G0):

- ``can_start_trip`` con ``blocking_reason`` evita que el frontend replique
  reglas: el backend dice si el botón está habilitado y por qué no.
- Iniciar viaje exige: conductor activo, camión asignado, ruta propia
  programada para hoy (o única ruta activa), sin otro viaje en curso.
- Las órdenes se congelan desde los puntos de la ruta (snapshot).
- Finalizar con órdenes pendientes exige ``confirm_pending: true``; las
  pendientes pasan a ``failed`` con motivo de texto libre obligatorio.
- Solo una orden en ``in_delivery`` a la vez.
- Toda transición escribe en ``trip_logs``.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.driver import Driver
from app.models.route import Route
from app.models.trip import (
    TRIP_STATE_COMPLETED,
    TRIP_STATE_IN_PROGRESS,
    Trip,
    TripLog,
    TripOrder,
)
from app.models.truck import Truck
from app.repositories import driver as driver_repo
from app.services.route_links import (
    effective_route_for_truck,
)
from app.utils.time import utcnow

logger = logging.getLogger("frostbase.trips")

BLOCKING_NO_TRUCK = "NO_TRUCK"
BLOCKING_NO_ROUTE_TODAY = "NO_ROUTE_TODAY"
BLOCKING_TRUCK_UNAVAILABLE = "TRUCK_UNAVAILABLE"
BLOCKING_TRIP_IN_PROGRESS = "TRIP_IN_PROGRESS"


class TripNotFoundError(Exception):
    pass


class TripConflictError(Exception):
    """Conflicto de estado: ya hay viaje, la orden no está en el estado correcto…"""


class TripValidationError(Exception):
    pass


def _get_truck(db: Session, driver: Driver) -> Truck | None:
    assignment = driver_repo.active_assignment(db, driver.id)
    if assignment is None:
        return None
    return driver_repo.truck_by_id(db, assignment.truck_id)


def _today_route(db: Session, driver: Driver) -> Route | None:
    return effective_route_for_truck(db, _get_truck(db, driver))


def can_start_trip(db: Session, driver: Driver) -> dict:
    """Dice si el conductor puede iniciar viaje y por qué no."""
    truck = _get_truck(db, driver)
    if truck is None:
        return {"can_start": False, "blocking_reason": BLOCKING_NO_TRUCK}

    active = db.scalar(
        select(Trip).where(
            Trip.driver_id == driver.id,
            Trip.state == TRIP_STATE_IN_PROGRESS,
        )
    )
    if active is not None:
        return {
            "can_start": False,
            "blocking_reason": BLOCKING_TRIP_IN_PROGRESS,
            "current_trip_id": active.id,
        }

    if truck.status not in ("disponible", "en_ruta"):
        return {
            "can_start": False,
            "blocking_reason": BLOCKING_TRUCK_UNAVAILABLE,
        }

    route = _today_route(db, driver)
    if route is None:
        return {
            "can_start": False,
            "blocking_reason": BLOCKING_NO_ROUTE_TODAY,
        }

    return {"can_start": True, "blocking_reason": None, "route_id": route.id}


def start_trip(db: Session, driver: Driver, route_id: int) -> Trip:
    """Inicia un viaje: crea las órdenes desde los puntos de la ruta.

    Todo en **una transacción**: validar, crear viaje, congelar órdenes y
    escribir bitácora. Si el conductor reintenta, devuelve el viaje en curso.
    """
    status = can_start_trip(db, driver)
    if not status["can_start"]:
        if status["blocking_reason"] == BLOCKING_TRIP_IN_PROGRESS:
            existing = db.scalar(
                select(Trip).where(
                    Trip.driver_id == driver.id,
                    Trip.state == TRIP_STATE_IN_PROGRESS,
                )
            )
            if existing is not None:
                return existing
        raise TripConflictError(_blocking_message(status["blocking_reason"]))

    route = db.scalar(
        select(Route).where(
            Route.id == route_id,
            Route.assigned_driver_id == driver.id,
            Route.status == "activa",
        )
    )
    if route is None:
        raise TripValidationError("La ruta no existe o no te pertenece")

    truck = _get_truck(db, driver)
    if truck is None:
        raise TripValidationError("No tienes un camión asignado")

    # Verificar que la ruta sea la de hoy (o la única activa).
    today = _today_route(db, driver)
    if today is None or today.id != route.id:
        raise TripValidationError("Esa ruta no está programada para hoy")

    trip = Trip(
        driver_id=driver.id,
        truck_id=truck.id,
        route_id=route.id,
        state=TRIP_STATE_IN_PROGRESS,
        started_at=utcnow(),
    )
    db.add(trip)
    db.flush()

    for index, point in enumerate(sorted(route.points, key=lambda p: p.order_index)):
        order = TripOrder(
            trip_id=trip.id,
            delivery_point_id=point.id,
            store_id=point.store_id,
            order_index=index,
            name=point.name,
            address=point.address,
            latitude=point.latitude,
            longitude=point.longitude,
            state="pending",
        )
        db.add(order)
    db.flush()

    truck.status = "en_ruta"
    db.add(truck)
    db.add(truck)

    db.add(
        TripLog(
            trip_id=trip.id,
            event="trip_started",
            detail=f"Ruta: {route.name}",
            actor_driver_id=driver.id,
        )
    )
    db.flush()
    logger.info(
        "trip_started id=%s driver_id=%s route_id=%s", trip.id, driver.id, route.id
    )
    return trip


def end_trip(
    db: Session,
    driver: Driver,
    trip_id: int,
    *,
    confirm_pending: bool = False,
    failure_reason: str | None = None,
) -> Trip:
    """Finaliza un viaje; las órdenes pendientes pasan a ``failed``."""
    trip = db.scalar(
        select(Trip).where(
            Trip.id == trip_id,
            Trip.driver_id == driver.id,
        )
    )
    if trip is None:
        raise TripNotFoundError("Viaje no encontrado")
    if trip.state != TRIP_STATE_IN_PROGRESS:
        raise TripConflictError("El viaje ya está finalizado")

    pending = [
        order for order in trip.orders if order.state in ("pending", "in_delivery")
    ]

    if pending and not confirm_pending:
        raise TripConflictError(
            f"Tienes {len(pending)} orden(es) sin entregar. "
            "Confirma con confirm_pending=true para marcarlas como no entregadas."
        )

    for order in pending:
        order.state = "failed"
        order.failure_reason = (
            failure_reason or ""
        ).strip() or "Finalizó el viaje sin entregar esta orden"
        db.add(order)
        db.add(
            TripLog(
                trip_id=trip.id,
                order_id=order.id,
                event="order_failed",
                detail=f"Motivo: {order.failure_reason}",
                actor_driver_id=driver.id,
            )
        )

    trip.state = TRIP_STATE_COMPLETED
    trip.ended_at = utcnow()
    db.add(trip)

    truck = db.get(Truck, trip.truck_id)
    if truck is not None:
        truck.status = "disponible"
        db.add(truck)

    db.add(
        TripLog(
            trip_id=trip.id,
            event="trip_ended",
            detail=f"Órdenes: {len(trip.orders)} total, "
            f"{len([o for o in trip.orders if o.state == 'delivered'])} entregadas",
            actor_driver_id=driver.id,
        )
    )
    db.flush()
    logger.info("trip_ended id=%s driver_id=%s", trip.id, driver.id)
    return trip


def start_order(db: Session, driver: Driver, trip_id: int, order_id: int) -> TripOrder:
    """Marca una orden como «en entrega»."""
    trip, order = _get_own_order(db, driver, trip_id, order_id)
    _ensure_trip_in_progress(trip)

    if order.state != "pending":
        raise TripConflictError(
            f"La orden está en estado «{order.state}», no se puede iniciar"
        )

    in_delivery = [o for o in trip.orders if o.state == "in_delivery"]
    if in_delivery:
        raise TripConflictError("Ya tienes una entrega en curso; termínala primero")

    order.state = "in_delivery"
    order.started_at = utcnow()
    db.add(order)
    db.add(
        TripLog(
            trip_id=trip.id,
            order_id=order.id,
            event="order_started",
            actor_driver_id=driver.id,
        )
    )
    db.flush()
    return order


def deliver_order(
    db: Session, driver: Driver, trip_id: int, order_id: int
) -> TripOrder:
    """Marca una orden como entregada."""
    trip, order = _get_own_order(db, driver, trip_id, order_id)
    _ensure_trip_in_progress(trip)

    if order.state != "in_delivery":
        raise TripConflictError(
            f"La orden está en estado «{order.state}»; inicia la entrega primero"
        )

    order.state = "delivered"
    order.delivered_at = utcnow()
    db.add(order)
    db.add(
        TripLog(
            trip_id=trip.id,
            order_id=order.id,
            event="order_delivered",
            actor_driver_id=driver.id,
        )
    )
    db.flush()
    return order


def fail_order(
    db: Session,
    driver: Driver,
    trip_id: int,
    order_id: int,
    reason: str,
) -> TripOrder:
    """Marca una orden como fallida (motivo de texto libre obligatorio)."""
    trip, order = _get_own_order(db, driver, trip_id, order_id)
    _ensure_trip_in_progress(trip)

    if order.state not in ("pending", "in_delivery"):
        raise TripConflictError(f"La orden ya está en estado «{order.state}»")

    normalized = (reason or "").strip()
    if not normalized:
        raise TripValidationError("El motivo de fallo es obligatorio")

    order.state = "failed"
    order.failure_reason = normalized
    db.add(order)
    db.add(
        TripLog(
            trip_id=trip.id,
            order_id=order.id,
            event="order_failed",
            detail=f"Motivo: {normalized}",
            actor_driver_id=driver.id,
        )
    )
    db.flush()
    return order


def get_current_trip(db: Session, driver: Driver) -> Trip | None:
    return db.scalar(
        select(Trip).where(
            Trip.driver_id == driver.id,
            Trip.state == TRIP_STATE_IN_PROGRESS,
        )
    )


def list_trips(
    db: Session, driver: Driver, *, page: int = 1, page_size: int = 20
) -> tuple[list[Trip], int]:
    total = db.scalar(select(func.count(Trip.id)).where(Trip.driver_id == driver.id))
    trips = db.scalars(
        select(Trip)
        .where(Trip.driver_id == driver.id)
        .order_by(Trip.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(trips), int(total or 0)


def get_trip_detail(db: Session, driver: Driver, trip_id: int) -> Trip:
    trip = db.scalar(
        select(Trip).where(Trip.id == trip_id, Trip.driver_id == driver.id)
    )
    if trip is None:
        raise TripNotFoundError("Viaje no encontrado")
    return trip


def _get_own_order(
    db: Session, driver: Driver, trip_id: int, order_id: int
) -> tuple[Trip, TripOrder]:
    trip = db.scalar(
        select(Trip).where(Trip.id == trip_id, Trip.driver_id == driver.id)
    )
    if trip is None:
        raise TripNotFoundError("Viaje no encontrado")
    order = db.scalar(
        select(TripOrder).where(TripOrder.id == order_id, TripOrder.trip_id == trip.id)
    )
    if order is None:
        raise TripNotFoundError("Orden no encontrada en este viaje")
    return trip, order


def _ensure_trip_in_progress(trip: Trip) -> None:
    if trip.state != TRIP_STATE_IN_PROGRESS:
        raise TripConflictError("El viaje ya está finalizado")


def _blocking_message(reason: str) -> str:
    messages = {
        BLOCKING_NO_TRUCK: "No tienes un camión asignado",
        BLOCKING_NO_ROUTE_TODAY: "No tienes ruta programada para hoy",
        BLOCKING_TRUCK_UNAVAILABLE: "Tu camión no está disponible",
        BLOCKING_TRIP_IN_PROGRESS: "Ya tienes un viaje en curso",
    }
    return messages.get(reason, "No puedes iniciar un viaje en este momento")
