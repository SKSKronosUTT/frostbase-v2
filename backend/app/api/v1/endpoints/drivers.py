"""CRUD administrativo de conductores (G3). Requiere rol administrador."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentAdmin, DbSession
from app.models.driver import Driver
from app.models.trip import Trip
from app.repositories import driver as driver_repo
from app.schemas.common import Page
from app.schemas.driver import (
    DriverAdminOut,
    DriverCreate,
    DriverCreatedOut,
    DriverDeactivationOut,
    DriverDetailOut,
    DriverOptionOut,
    DriverRouteBrief,
    DriverTripOut,
    DriverTruckIn,
    DriverUpdate,
)
from app.services import driver_service

router = APIRouter(prefix="/drivers", tags=["Conductores"])

ActiveFilter = Literal["true", "false", "all"]


def _get_or_fail(db: DbSession, driver_id: int) -> Driver:
    driver = driver_repo.get_by_id(db, driver_id)
    if driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conductor no encontrado"
        )
    return driver


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _validation(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
    )


@router.get("", response_model=Page[DriverAdminOut])
def list_drivers(
    db: DbSession,
    _: CurrentAdmin,
    search: str | None = Query(default=None, max_length=100),
    active: ActiveFilter = Query(default="true"),
    has_truck: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[DriverAdminOut]:
    active_flag = None if active == "all" else (active == "true")
    drivers, total = driver_repo.list_paginated(
        db,
        search=search,
        active=active_flag,
        has_truck=has_truck,
        page=page,
        page_size=page_size,
    )
    return Page(
        items=[
            DriverAdminOut(**driver_service.admin_payload(db, driver))
            for driver in drivers
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/options", response_model=list[DriverOptionOut])
def list_driver_options(db: DbSession, _: CurrentAdmin) -> list[DriverOptionOut]:
    """Conductores activos, con o sin camión (la etiqueta indica la placa)."""
    return [
        DriverOptionOut(id=driver_id, label=label)
        for driver_id, label in driver_repo.list_options(db)
    ]


@router.post("", response_model=DriverCreatedOut, status_code=status.HTTP_201_CREATED)
def create_driver(
    payload: DriverCreate, db: DbSession, admin: CurrentAdmin
) -> DriverCreatedOut:
    try:
        driver, temporary_password = driver_service.create_driver(
            db, payload, admin_id=admin.id
        )
    except driver_service.DriverConflictError as exc:
        raise _conflict(exc) from exc
    except driver_service.DriverValidationError as exc:
        raise _validation(exc) from exc

    body = driver_service.admin_payload(db, driver)
    return DriverCreatedOut(**body, temporary_password=temporary_password)


@router.get("/{driver_id}", response_model=DriverDetailOut)
def get_driver(driver_id: int, db: DbSession, _: CurrentAdmin) -> DriverDetailOut:
    driver = _get_or_fail(db, driver_id)
    return DriverDetailOut(**driver_service.detail_payload(db, driver))


@router.patch("/{driver_id}", response_model=DriverAdminOut)
def update_driver(
    driver_id: int, payload: DriverUpdate, db: DbSession, _: CurrentAdmin
) -> DriverAdminOut:
    driver = _get_or_fail(db, driver_id)
    try:
        updated = driver_service.update_driver(db, driver, payload)
    except driver_service.DriverConflictError as exc:
        raise _conflict(exc) from exc
    except driver_service.DriverValidationError as exc:
        raise _validation(exc) from exc
    return DriverAdminOut(**driver_service.admin_payload(db, updated))


@router.delete("/{driver_id}", response_model=DriverDeactivationOut)
def deactivate_driver(
    driver_id: int, db: DbSession, _: CurrentAdmin
) -> DriverDeactivationOut:
    """Baja lógica: libera el camión y revoca las sesiones del conductor."""
    driver = _get_or_fail(db, driver_id)
    try:
        affected = driver_service.deactivate_driver(db, driver)
    except driver_service.DriverConflictError as exc:
        raise _conflict(exc) from exc
    return DriverDeactivationOut(
        id=driver.id,
        affected_routes=[
            DriverRouteBrief(id=route.id, name=route.name, status=route.status)
            for route in affected
        ],
    )


@router.post("/{driver_id}/restore", response_model=DriverAdminOut)
def restore_driver(driver_id: int, db: DbSession, _: CurrentAdmin) -> DriverAdminOut:
    driver = _get_or_fail(db, driver_id)
    restored = driver_service.restore_driver(db, driver)
    return DriverAdminOut(**driver_service.admin_payload(db, restored))


@router.post("/{driver_id}/reset-password", response_model=DriverCreatedOut)
def reset_password(driver_id: int, db: DbSession, _: CurrentAdmin) -> DriverCreatedOut:
    """Genera una contraseña temporal visible una sola vez."""
    driver = _get_or_fail(db, driver_id)
    temporary_password = driver_service.reset_password(db, driver)
    body = driver_service.admin_payload(db, driver)
    return DriverCreatedOut(**body, temporary_password=temporary_password)


@router.put("/{driver_id}/truck", response_model=DriverAdminOut)
def assign_truck(
    driver_id: int, payload: DriverTruckIn, db: DbSession, admin: CurrentAdmin
) -> DriverAdminOut:
    driver = _get_or_fail(db, driver_id)
    try:
        driver_service.assign_truck(db, driver, payload.truck_id, admin_id=admin.id)
    except driver_service.DriverConflictError as exc:
        raise _conflict(exc) from exc
    except driver_service.DriverValidationError as exc:
        raise _validation(exc) from exc
    return DriverAdminOut(**driver_service.admin_payload(db, driver))


@router.delete("/{driver_id}/truck", response_model=DriverAdminOut)
def remove_truck(driver_id: int, db: DbSession, _: CurrentAdmin) -> DriverAdminOut:
    driver = _get_or_fail(db, driver_id)
    try:
        driver_service.remove_truck(db, driver)
    except driver_service.DriverConflictError as exc:
        raise _conflict(exc) from exc
    return DriverAdminOut(**driver_service.admin_payload(db, driver))


@router.get("/{driver_id}/trips", response_model=Page[DriverTripOut])
def list_driver_trips(
    driver_id: int,
    db: DbSession,
    _: CurrentAdmin,
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[DriverTripOut]:
    _get_or_fail(db, driver_id)
    stmt = select(Trip).where(Trip.driver_id == driver_id)
    total = db.scalar(select(func.count(Trip.id)).where(Trip.driver_id == driver_id))
    rows = db.scalars(
        stmt.order_by(Trip.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return Page(
        items=[
            DriverTripOut(
                id=trip.id,
                state=trip.state,
                started_at=trip.started_at,
                ended_at=trip.ended_at,
                truck_id=trip.truck_id,
            )
            for trip in rows
        ],
        total=total or 0,
        page=page,
        page_size=page_size,
    )
