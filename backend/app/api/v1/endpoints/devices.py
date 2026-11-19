from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from app.api.deps import CurrentAdmin, DbSession
from app.core.ratelimit import RateLimit
from app.schemas.common import Page
from app.schemas.device import DeviceCreate, DeviceCreatedOut, DeviceOut, DeviceUpdate
from app.services import device_service

router = APIRouter(prefix="/devices", tags=["Dispositivos IoT"])

_rotate_key_limiter = RateLimit("devices:rotate", limit=10, window_seconds=3600)


@router.get("", response_model=Page[DeviceOut])
def list_devices(
    db: DbSession,
    _: CurrentAdmin,
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[DeviceOut]:
    return device_service.list_devices(
        db, search=search, page=page, page_size=page_size
    )


@router.get("/all", response_model=list[DeviceOut])
def list_all_devices(db: DbSession, _: CurrentAdmin) -> list[DeviceOut]:
    return device_service.list_all_devices(db)


@router.get("/unassigned", response_model=list[DeviceOut])
def list_unassigned_devices(db: DbSession, _: CurrentAdmin) -> list[DeviceOut]:
    return device_service.list_unassigned_devices(db)


@router.post("", response_model=DeviceCreatedOut, status_code=status.HTTP_201_CREATED)
def create_device(
    payload: DeviceCreate, db: DbSession, _: CurrentAdmin
) -> DeviceCreatedOut:
    try:
        return device_service.create_device(db, payload)
    except device_service.DeviceConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except device_service.DeviceValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/{device_pk}", response_model=DeviceOut)
def get_device(device_pk: int, db: DbSession, _: CurrentAdmin) -> DeviceOut:
    try:
        return device_service.get_device(db, device_pk)
    except device_service.DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{device_pk}", response_model=DeviceOut)
def update_device(
    device_pk: int, payload: DeviceUpdate, db: DbSession, _: CurrentAdmin
) -> DeviceOut:
    try:
        return device_service.update_device(db, device_pk, payload)
    except device_service.DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except device_service.DeviceValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.post("/{device_pk}/rotate-key", response_model=DeviceCreatedOut)
def rotate_key(
    device_pk: int,
    request: Request,
    response: Response,
    db: DbSession,
    admin: CurrentAdmin,
) -> DeviceCreatedOut:
    _rotate_key_limiter.check(request, response, extra=str(admin.id))
    try:
        return device_service.rotate_key(db, device_pk)
    except device_service.DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
