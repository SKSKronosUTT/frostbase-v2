from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentAdmin, DbSession
from app.schemas.common import Page
from app.schemas.truck import TruckCreate, TruckDetailOut, TruckOut, TruckUpdate
from app.services import truck_service

router = APIRouter(prefix="/trucks", tags=["Camiones"])

TruckStatusFilter = Literal["en_ruta", "disponible", "mantenimiento"]


@router.get("", response_model=Page[TruckOut])
def list_trucks(
    db: DbSession,
    _: CurrentAdmin,
    search: str | None = Query(default=None, max_length=100),
    status_filter: TruckStatusFilter | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[TruckOut]:
    return truck_service.list_trucks(
        db,
        search=search,
        status=status_filter,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TruckOut, status_code=status.HTTP_201_CREATED)
def create_truck(
    payload: TruckCreate, db: DbSession, _: CurrentAdmin
) -> TruckOut:
    try:
        return truck_service.create_truck(db, payload)
    except truck_service.TruckConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except truck_service.TruckValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/{truck_id}", response_model=TruckDetailOut)
def get_truck(truck_id: int, db: DbSession, _: CurrentAdmin) -> TruckDetailOut:
    try:
        return truck_service.get_truck_detail(db, truck_id)
    except truck_service.TruckNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{truck_id}", response_model=TruckOut)
def update_truck(
    truck_id: int, payload: TruckUpdate, db: DbSession, _: CurrentAdmin
) -> TruckOut:
    try:
        return truck_service.update_truck(db, truck_id, payload)
    except truck_service.TruckNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except truck_service.TruckConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except truck_service.TruckValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.delete("/{truck_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_truck(truck_id: int, db: DbSession, _: CurrentAdmin) -> None:
    try:
        truck_service.delete_truck(db, truck_id)
    except truck_service.TruckNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
