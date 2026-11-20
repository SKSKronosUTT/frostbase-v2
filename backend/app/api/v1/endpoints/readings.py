from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentAdmin, DbSession
from app.schemas.common import Page
from app.schemas.reading import ReadingOut
from app.services import reading_service
from app.utils.pagination import decode_cursor

router = APIRouter(prefix="/readings", tags=["Lecturas"])


def _parse_cursor(cursor: str | None) -> tuple[datetime, int] | None:
    if not cursor:
        return None
    parsed = decode_cursor(cursor)
    if parsed is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="cursor inválido",
        )
    return parsed


@router.get("", response_model=Page[ReadingOut])
def list_readings(
    db: DbSession,
    _: CurrentAdmin,
    truck_id: int | None = Query(default=None),
    device_id: int | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=50, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=256),
) -> Page[ReadingOut]:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha inicial no puede ser posterior a la final",
        )
    return reading_service.list_readings(
        db,
        truck_id=truck_id,
        device_id=device_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        cursor=_parse_cursor(cursor),
    )


@router.get("/truck/{truck_id}", response_model=Page[ReadingOut])
def list_truck_readings(
    truck_id: int,
    db: DbSession,
    _: CurrentAdmin,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=50, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=256),
) -> Page[ReadingOut]:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha inicial no puede ser posterior a la final",
        )
    return reading_service.list_readings(
        db,
        truck_id=truck_id,
        device_id=None,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        cursor=_parse_cursor(cursor),
    )
