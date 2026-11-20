from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentAdmin, DbSession
from app.schemas.common import Page
from app.schemas.route import AssignTruckIn, RouteCreate, RouteOut, RouteUpdate
from app.services import route_service

router = APIRouter(prefix="/routes", tags=["Rutas"])

RouteStatusFilter = Literal["activa", "inactiva"]


@router.get("", response_model=Page[RouteOut])
def list_routes(
    db: DbSession,
    _: CurrentAdmin,
    search: str | None = Query(default=None, max_length=100),
    status_filter: RouteStatusFilter | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[RouteOut]:
    return route_service.list_routes(
        db, search=search, status=status_filter, page=page, page_size=page_size
    )


@router.post("", response_model=RouteOut, status_code=status.HTTP_201_CREATED)
def create_route(
    payload: RouteCreate, db: DbSession, _: CurrentAdmin
) -> RouteOut:
    try:
        return route_service.create_route(db, payload)
    except route_service.RouteValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/{route_id}", response_model=RouteOut)
def get_route(route_id: int, db: DbSession, _: CurrentAdmin) -> RouteOut:
    try:
        return route_service.get_route(db, route_id)
    except route_service.RouteNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{route_id}", response_model=RouteOut)
def update_route(
    route_id: int, payload: RouteUpdate, db: DbSession, _: CurrentAdmin
) -> RouteOut:
    try:
        return route_service.update_route(db, route_id, payload)
    except route_service.RouteNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route(route_id: int, db: DbSession, _: CurrentAdmin) -> None:
    try:
        route_service.delete_route(db, route_id)
    except route_service.RouteNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{route_id}/calculate", response_model=RouteOut)
def calculate_route(route_id: int, db: DbSession, _: CurrentAdmin) -> RouteOut:
    try:
        return route_service.calculate_route(db, route_id)
    except route_service.RouteNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except route_service.RouteValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.post("/{route_id}/assign", response_model=RouteOut)
def assign_route(
    route_id: int, payload: AssignTruckIn, db: DbSession, _: CurrentAdmin
) -> RouteOut:
    try:
        return route_service.assign_route(db, route_id, payload.truck_id)
    except route_service.RouteNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except route_service.RouteValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
