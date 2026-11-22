"""Portal del conductor (G5): perfil, dashboard, contenedor, rutas y alertas.

El ID del conductor siempre viene del token: nunca se acepta por parámetro.
Los recursos ajenos responden ``404`` para no revelar su existencia.
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentDriver, DbSession
from app.models.driver import DriverTruckAssignment
from app.models.truck import Truck
from app.schemas.common import Page
from app.schemas.driver import DriverMeOut, DriverTruckBrief
from app.schemas.driver_portal import (
    DriverAlertOut,
    DriverContainerOut,
    DriverDashboardOut,
    DriverReadingOut,
    DriverRouteCard,
    DriverRouteDetail,
)
from app.schemas.trip import (
    CanStartTripOut,
    OrderFailIn,
    TripEndIn,
    TripOrderOut,
    TripOut,
    TripStartIn,
)
from app.services import door_service, driver_portal, trip_service

router = APIRouter(prefix="/driver", tags=["Conductor"])


@router.get("/me", response_model=DriverMeOut)
def me(driver: CurrentDriver, db: DbSession) -> DriverMeOut:
    assignment = db.scalar(
        select(DriverTruckAssignment).where(
            DriverTruckAssignment.driver_id == driver.id,
            DriverTruckAssignment.unassigned_at.is_(None),
        )
    )
    truck = db.get(Truck, assignment.truck_id) if assignment is not None else None
    out = DriverMeOut.model_validate(driver)
    out.truck = DriverTruckBrief(id=truck.id, plate=truck.plate) if truck else None
    return out


@router.get("/dashboard", response_model=DriverDashboardOut)
def dashboard(driver: CurrentDriver, db: DbSession) -> DriverDashboardOut:
    """Resumen de la pantalla principal en una sola llamada (G5)."""
    return driver_portal.get_dashboard(db, driver)


@router.get("/container/live", response_model=DriverContainerOut)
def container_live(driver: CurrentDriver, db: DbSession) -> DriverContainerOut:
    """Última lectura del contenedor con umbrales efectivos."""
    return driver_portal.get_container_live(db, driver)


@router.get("/container/readings", response_model=list[DriverReadingOut])
def container_readings(
    driver: CurrentDriver,
    db: DbSession,
    limit: int = Query(default=60, ge=1, le=500),
) -> list[DriverReadingOut]:
    return driver_portal.get_container_readings(db, driver, limit=limit)


@router.get("/routes", response_model=list[DriverRouteCard])
def list_routes(driver: CurrentDriver, db: DbSession) -> list[DriverRouteCard]:
    """Rutas asignadas al conductor con sus días de entrega."""
    return driver_portal.list_routes(db, driver)


@router.get("/routes/today", response_model=DriverRouteCard | None)
def route_today(driver: CurrentDriver, db: DbSession) -> DriverRouteCard | None:
    """Ruta del día según el calendario semanal (America/Tijuana)."""
    return driver_portal.get_route_today(db, driver)


@router.get("/routes/{route_id}", response_model=DriverRouteDetail)
def route_detail(
    route_id: int, driver: CurrentDriver, db: DbSession
) -> DriverRouteDetail:
    """Detalle de una ruta propia; la de otro conductor da ``404``."""
    detail = driver_portal.get_route_detail(db, driver, route_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ruta no encontrada",
        )
    return detail


@router.get("/alerts", response_model=Page[DriverAlertOut])
def alerts(
    driver: CurrentDriver,
    db: DbSession,
    status_filter: Literal["activa", "resuelta"] | None = Query(
        default=None, alias="status"
    ),
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[DriverAlertOut]:
    items, total = driver_portal.list_alerts(
        db, driver, status=status_filter, page=page, page_size=page_size
    )
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("/alerts/{alert_id}/ack", response_model=DriverAlertOut)
def ack_alert(alert_id: int, driver: CurrentDriver, db: DbSession) -> DriverAlertOut:
    """Reconoce una alerta propia (G7); la ajena responde ``404``."""
    alert = door_service.ack_alert(db, driver, alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerta no encontrada",
        )
    return DriverAlertOut(
        id=alert.id,
        alert_type=alert.alert_type,
        value=alert.value,
        min_value=alert.min_value,
        max_value=alert.max_value,
        message=alert.message,
        started_at=alert.started_at,
        resolved_at=alert.resolved_at,
        status=alert.status,
        acknowledged_at=alert.acknowledged_at,
    )


# ===== Viajes y entregas (G6) =====


@router.get("/trips/can-start", response_model=CanStartTripOut)
def can_start(driver: CurrentDriver, db: DbSession) -> CanStartTripOut:
    """Dice si el conductor puede iniciar un viaje y por qué no."""
    return CanStartTripOut(**trip_service.can_start_trip(db, driver))


@router.get("/trips/current", response_model=TripOut | None)
def current_trip(driver: CurrentDriver, db: DbSession) -> TripOut | None:
    """Viaje en curso, o ``null``."""
    trip = trip_service.get_current_trip(db, driver)
    return TripOut.from_trip(trip) if trip else None


@router.post("/trips/start", response_model=TripOut, status_code=201)
def start_trip(payload: TripStartIn, driver: CurrentDriver, db: DbSession) -> TripOut:
    """Inicia un viaje creando las órdenes desde la ruta de hoy."""
    try:
        trip = trip_service.start_trip(db, driver, payload.route_id)
    except trip_service.TripConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except trip_service.TripValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return TripOut.from_trip(trip)


@router.post("/trips/{trip_id}/end", response_model=TripOut)
def end_trip(
    trip_id: int,
    payload: TripEndIn,
    driver: CurrentDriver,
    db: DbSession,
) -> TripOut:
    """Finaliza un viaje; las órdenes pendientes requieren ``confirm_pending``."""
    try:
        trip = trip_service.end_trip(
            db,
            driver,
            trip_id,
            confirm_pending=payload.confirm_pending,
            failure_reason=payload.failure_reason,
        )
    except trip_service.TripNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except trip_service.TripConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return TripOut.from_trip(trip)


@router.post("/trips/{trip_id}/orders/{order_id}/start", response_model=TripOrderOut)
def start_order(
    trip_id: int, order_id: int, driver: CurrentDriver, db: DbSession
) -> TripOrderOut:
    """Marca una orden como «en entrega»."""
    try:
        order = trip_service.start_order(db, driver, trip_id, order_id)
    except trip_service.TripNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except trip_service.TripConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return TripOrderOut.from_order(order)


@router.post("/trips/{trip_id}/orders/{order_id}/deliver", response_model=TripOrderOut)
def deliver_order(
    trip_id: int, order_id: int, driver: CurrentDriver, db: DbSession
) -> TripOrderOut:
    """Marca una orden como entregada."""
    try:
        order = trip_service.deliver_order(db, driver, trip_id, order_id)
    except trip_service.TripNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except trip_service.TripConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return TripOrderOut.from_order(order)


@router.post("/trips/{trip_id}/orders/{order_id}/fail", response_model=TripOrderOut)
def fail_order(
    trip_id: int,
    order_id: int,
    payload: OrderFailIn,
    driver: CurrentDriver,
    db: DbSession,
) -> TripOrderOut:
    """Marca una orden como fallida (motivo de texto libre obligatorio)."""
    try:
        order = trip_service.fail_order(db, driver, trip_id, order_id, payload.reason)
    except trip_service.TripNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except (trip_service.TripConflictError, trip_service.TripValidationError) as exc:
        code = (
            status.HTTP_409_CONFLICT
            if isinstance(exc, trip_service.TripConflictError)
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return TripOrderOut.from_order(order)


@router.get("/trips", response_model=Page[TripOut])
def list_trips(
    driver: CurrentDriver,
    db: DbSession,
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[TripOut]:
    """Historial de viajes del conductor, paginado."""
    trips, total = trip_service.list_trips(db, driver, page=page, page_size=page_size)
    return Page(
        items=[TripOut.from_trip(trip) for trip in trips],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/trips/{trip_id}", response_model=TripOut)
def trip_detail(trip_id: int, driver: CurrentDriver, db: DbSession) -> TripOut:
    """Detalle de un viaje propio; el de otro conductor da ``404``."""
    try:
        trip = trip_service.get_trip_detail(db, driver, trip_id)
    except trip_service.TripNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return TripOut.from_trip(trip)
