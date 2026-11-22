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
from app.services import driver_portal

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
